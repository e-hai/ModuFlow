import uuid
import asyncio
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.entities import (
    CollaborationSession,
    SessionMessage,
    ModuleInstance,
    Artifact,
    Issue
)
from backend.app.services.context_assembler import assemble_module_context
from backend.app.adapters.factory import get_agent_adapter
from backend.app.adapters.base import AgentEventType, AgentStreamEvent
from backend.app.services.workflow_engine import calculate_sha256
from backend.app.services.workspace_sync import sync_run_workspace

_session_locks: Dict[str, asyncio.Lock] = {}

def get_session_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


async def release_db_while_waiting(db: AsyncSession) -> None:
    """结束当前事务，把连接还回连接池。长耗时的 CLI 不能占着 SQLite 连接。"""
    if db.in_transaction():
        await db.commit()

async def execute_agent_for_session(
    db: AsyncSession,
    session: CollaborationSession,
    user_message: SessionMessage,
    adapter_type: Optional[str] = None
) -> Optional[SessionMessage]:
    """
    Executes the configured Agent Adapter for a given collaboration session message:
    1. Enforces single-concurrency lock per session to prevent duplicate runs & artifact collisions.
    2. Assembles multi-layered strategic context (Mother blueprint + upstream baselines).
    3. Invokes the Agent Adapter (CLI Subprocess or Simulator) inside the physical module workspace.
    4. Captures output events, persists Artifact / SessionMessage in DB, and synchronizes workspace.
    """
    lock = get_session_lock(session.id)
    if lock.locked():
        err_msg = SessionMessage(
            session_id=session.id,
            sender="系统互斥网关",
            sender_role="agent",
            message_type="error",
            content="当前模块会话已有正在运行中的 Agent 任务，请等待前序推演结束或超时后再发送新指令。"
        )
        db.add(err_msg)
        await db.commit()
        await db.refresh(err_msg)
        return err_msg

    async with lock:
        mod_stmt = select(ModuleInstance).where(ModuleInstance.id == session.module_id)
        mod_res = await db.execute(mod_stmt)
        module = mod_res.scalar_one_or_none()
        if not module:
            return None

        # 0. Deterministic Authorization & Guardrail Checks (Zero LLM)
        from backend.app.models.entities import WorkflowRun, Product
        from backend.app.services.authorization_engine import (
            load_product_authorization,
            check_time_limits,
            execute_circuit_breaker
        )

        run_stmt = select(WorkflowRun).where(WorkflowRun.id == module.run_id)
        run_res = await db.execute(run_stmt)
        run_obj = run_res.scalar_one_or_none()

        if run_obj and run_obj.product_id:
            p_stmt = select(Product).where(Product.id == run_obj.product_id)
            p_res = await db.execute(p_stmt)
            product = p_res.scalar_one_or_none()
            if product:
                # A. Block if product is paused
                if product.stage == "paused":
                    pause_msg = SessionMessage(
                        session_id=session.id,
                        sender="确定性熔断守门人",
                        sender_role="system",
                        role_code="system",
                        message_type="error",
                        content=f"🔴 项目当前处于确定性熔断暂停状态 (paused): {product.key_risk or '触发安全熔断'}。\n系统已强制阻断所有 Agent 派活。请人类负责人在控制台或 decisions/ 审计核准后再恢复运行。"
                    )
                    db.add(pause_msg)
                    await db.commit()
                    await db.refresh(pause_msg)
                    return pause_msg

                # B. Stage 01 hard requirement for valid authorization package
                if module.module_code == "01" and product.initiative_id:
                    auth_status, auth_data, auth_errors = load_product_authorization(product.initiative_id, product.code)
                    if auth_status != "authorized":
                        err_detail = f"错误: {', '.join(auth_errors)}" if auth_errors else "缺少 authorization.yaml"
                        auth_err_msg = SessionMessage(
                            session_id=session.id,
                            sender="授权门禁检查器",
                            sender_role="system",
                            role_code="system",
                            message_type="error",
                            content=f"❌ 项目「{product.name}」尚未配置合规授权包 (authorization.yaml)，禁止进入工序 01 开工。\n{err_detail}\n请人类负责人在项目配置中上传合规授权包 (或执行 scripts/migrate_legacy_project_auth.py)。"
                        )
                        db.add(auth_err_msg)
                        await db.commit()
                        await db.refresh(auth_err_msg)
                        return auth_err_msg

                # C. Check time budget deadline
                if product.initiative_id:
                    auth_status, auth_data, _ = load_product_authorization(product.initiative_id, product.code)
                    if auth_status == "authorized" and auth_data:
                        is_expired, time_reason = check_time_limits(auth_data)
                        if is_expired:
                            await execute_circuit_breaker(
                                product.initiative_id,
                                product.code,
                                "time_expired",
                                {"reason": time_reason},
                                db
                            )
                            time_err_msg = SessionMessage(
                                session_id=session.id,
                                sender="确定性时限守门人",
                                sender_role="system",
                                role_code="system",
                                message_type="error",
                                content=f"🔴 项目时限超期熔断: {time_reason}。\n项目已自动置为 paused，已阻断派活。需人类负责人调整项目授权包期限。"
                            )
                            db.add(time_err_msg)
                            await db.commit()
                            await db.refresh(time_err_msg)
                            return time_err_msg

        msg_type = user_message.message_type
        content = user_message.content

        # 1. Assemble Strategic Context & Physical Workspace
        try:
            system_context, workspace_path, meta = await assemble_module_context(
                db=db,
                module_id=module.id,
                user_instruction=content
            )
        except Exception as e:
            system_context = f"# 上下文装配异常: {e}"
            workspace_path = None
            meta = {"module_code": module.module_code, "module_name": module.name}

        # 2. Obtain Adapter instance
        adapter = get_agent_adapter(adapter_type)
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        # 3. Stream/Execute Adapter Task
        await release_db_while_waiting(db)
        produced_artifact_content = None
        produced_artifact_event_type = None
        produced_answer_content = None
        error_event = None
        logs: List[str] = []

        async for event in adapter.execute_task(
            task_id=task_id,
            workspace_dir=workspace_path,
            system_context=system_context,
            user_instruction=content,
            message_type=msg_type,
            metadata=meta
        ):
            if event.event_type in (AgentEventType.ARTIFACT_DRAFT, AgentEventType.ARTIFACT_REVISED):
                produced_artifact_content = event.content
                produced_artifact_event_type = event.event_type
            elif event.event_type == AgentEventType.ANSWER:
                produced_answer_content = event.content
            elif event.event_type == AgentEventType.ERROR:
                error_event = event
            elif event.event_type == AgentEventType.LOG:
                logs.append(event.content)

        adapter_cmd = getattr(adapter, "cli_command", "CLI")
        role_name = (meta or {}).get("role_name", "AI Agent")
        role_code = (meta or {}).get("role_code", "pm")
        sender_label = f"{role_name} ({adapter_cmd})"

        # 4. Handle Explicit Execution Error (当 agent 出错时，绝不伪造正常回答，直接报告失败)
        if error_event:
            from backend.app.services.security_guard import intercept_agent_write_attempt
            for violated_path in ((error_event.metadata or {}).get("sandbox_violations") or [])[:5]:
                await intercept_agent_write_attempt(
                    violated_path,
                    actor=f"agent:{role_code}",
                    actor_role=role_code,
                    db=db,
                    initiative_id=(meta or {}).get("initiative_id"),
                    product_code=(meta or {}).get("product_code"),
                )
            agent_msg = SessionMessage(
                session_id=session.id,
                sender=sender_label,
                sender_role="agent",
                role_code=role_code,
                message_type="error",
                content=error_event.content,
                metadata_json={
                    "logs_preview": logs[-5:] if logs else [],
                    "error_meta": error_event.metadata or {},
                    "role_code": role_code,
                    "role_name": role_name
                }
            )
            db.add(agent_msg)
            await db.commit()
            await db.refresh(agent_msg)
            return agent_msg

        # 5. Handle Question Discussion (疑问讨论 / Answer)
        if msg_type == "question":
            if produced_answer_content:
                agent_msg = SessionMessage(
                    session_id=session.id,
                    sender=sender_label,
                    sender_role="agent",
                    role_code=role_code,
                    message_type="answer",
                    content=produced_answer_content,
                    metadata_json={"logs_preview": logs[-3:] if logs else [], "role_code": role_code, "role_name": role_name}
                )
                db.add(agent_msg)
                await db.commit()
                await db.refresh(agent_msg)
                return agent_msg
            else:
                agent_msg = SessionMessage(
                    session_id=session.id,
                    sender=sender_label,
                    sender_role="agent",
                    role_code=role_code,
                    message_type="error",
                    content=f"Agent ({adapter_cmd}) 执行完毕，但未能在标准输出中返回有效回答内容。",
                    metadata_json={"logs_preview": logs[-3:] if logs else [], "role_code": role_code}
                )
                db.add(agent_msg)
                await db.commit()
                await db.refresh(agent_msg)
                return agent_msg

        # 6. Handle Deliverable Generation/Revision (指令生成与反馈修订)
        if produced_artifact_content:
            art_stmt = select(Artifact).where(Artifact.module_id == module.id).order_by(Artifact.version.desc())
            art_res = await db.execute(art_stmt)
            latest_art = art_res.scalars().first()
            next_version = (latest_art.version + 1) if latest_art else 1

            artifact_type = "markdown"
            storage_rel_path = None
            entry_file = "index.html"

            if workspace_path:
                try:
                    from backend.app.core.config import settings
                    storage_rel_path = str(workspace_path.relative_to(settings.WORKSPACE_DIR))
                except Exception:
                    storage_rel_path = None
                if (workspace_path / "index.html").exists():
                    artifact_type = "html_bundle"

            change_summary = None
            if user_message.issue_ref_id:
                issue_stmt = select(Issue).where(Issue.id == user_message.issue_ref_id)
                issue_res = await db.execute(issue_stmt)
                referenced_issue = issue_res.scalar_one_or_none()
                if referenced_issue:
                    change_summary = f"采纳并解决问题单 [{referenced_issue.id}]: {referenced_issue.title}"
                    referenced_issue.status = "closed"
                    referenced_issue.resolution = f"已采纳并在 {module.name} 交付物 (V{next_version}) 中完成修订"
                    db.add(referenced_issue)

            new_artifact = Artifact(
                module_id=module.id,
                version=next_version,
                title=f"{module.name} 交付物 (V{next_version})",
                content=produced_artifact_content,
                content_hash=calculate_sha256(produced_artifact_content),
                artifact_type=artifact_type,
                storage_rel_path=storage_rel_path,
                entry_file=entry_file,
                change_summary=change_summary,
                is_baseline=False
            )
            db.add(new_artifact)
            await db.flush()

            module.baseline_artifact_id = new_artifact.id
            if module.phase in ("draft", "baselined"):
                module.phase = "discussing"
            db.add(module)

            msg_kind = "draft_artifact" if msg_type == "instruction" else "revised_artifact"
            status_text = "生成交付物初稿" if msg_type == "instruction" else "完成交付物迭代修订"

            agent_msg = SessionMessage(
                session_id=session.id,
                sender=sender_label,
                sender_role="agent",
                role_code=role_code,
                message_type=msg_kind,
                content=f"已成功{status_text}，已归档至物理工作区并创建版本基准 **V{next_version}**。",
                artifact_ref_id=new_artifact.id,
                metadata_json={
                    "version": next_version,
                    "filename": f"交付物_{module.module_code}_{module.name}.md",
                    "logs_preview": logs[-3:] if logs else [],
                    "role_code": role_code,
                    "role_name": role_name
                }
            )
            db.add(agent_msg)
            await db.commit()
            await db.refresh(agent_msg)

            # Trigger physical file sync
            try:
                await sync_run_workspace(db, module.run_id)
            except Exception:
                pass

            return agent_msg

        # If neither error nor artifact was produced for an instruction
        agent_msg = SessionMessage(
            session_id=session.id,
            sender=sender_label,
            sender_role="agent",
            role_code=role_code,
            message_type="error",
            content=f"Agent ({adapter_cmd}) 执行完毕，但未在工作区生成交付物文件。",
            metadata_json={"logs_preview": logs[-3:] if logs else [], "role_code": role_code}
        )
        db.add(agent_msg)
        await db.commit()
        await db.refresh(agent_msg)
        return agent_msg


async def execute_collaborator_review(
    db: AsyncSession,
    session: CollaborationSession,
    module: ModuleInstance,
    spec: Dict[str, Any],
    artifact: Artifact,
    adapter_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs one collaborator review of the primary deliverable; the reviewer writes no files and cannot release gates."""
    from backend.app.services.collaboration import (
        REVIEW_MESSAGE_TYPE,
        build_review_instruction,
        parse_verdict,
    )

    reviewer = spec["reviewer"]
    instruction = build_review_instruction(spec, module.module_code, module.name, artifact.content or "")
    async with get_session_lock(session.id):
        system_context, workspace_path, meta = await assemble_module_context(
            db=db, module_id=module.id, user_instruction=instruction, role_override=reviewer,
        )
        meta = {**(meta or {}), "review_spec": spec}
        adapter = get_agent_adapter(adapter_type)
        await release_db_while_waiting(db)
        review_text = ""
        error_text = None
        async for event in adapter.execute_task(
            task_id=f"review-{uuid.uuid4().hex[:8]}",
            workspace_dir=workspace_path,
            system_context=system_context,
            user_instruction=instruction,
            message_type=REVIEW_MESSAGE_TYPE,
            metadata=meta,
        ):
            if event.event_type in (AgentEventType.ANSWER, AgentEventType.ARTIFACT_DRAFT, AgentEventType.ARTIFACT_REVISED):
                review_text = event.content or ""
            elif event.event_type == AgentEventType.ERROR:
                error_text = event.content

    verdict = parse_verdict(review_text) if not error_text else {
        "verdict": "request_changes",
        "findings": [f"评审执行失败：{error_text[:300]}"],
        "parse_error": True,
    }
    result = {
        "reviewer": reviewer,
        "kind": "llm",
        "focus": spec["focus"],
        "artifact_version": artifact.version,
        **verdict,
    }
    db.add(SessionMessage(
        session_id=session.id,
        sender=f"{(meta or {}).get('role_name', reviewer)} (协作评审)",
        sender_role="agent",
        role_code=reviewer,
        message_type=REVIEW_MESSAGE_TYPE,
        content=review_text or (error_text or "评审未产出内容"),
        metadata_json={"orchestrator": "review", "review": result},
    ))
    await db.commit()
    return result
