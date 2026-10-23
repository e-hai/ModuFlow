import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.entities import (
    CollaborationSession,
    SessionMessage,
    ModuleInstance,
    Artifact
)
from backend.app.services.context_assembler import assemble_module_context
from backend.app.adapters.factory import get_agent_adapter
from backend.app.adapters.base import AgentEventType, AgentStreamEvent
from backend.app.services.workflow_engine import calculate_sha256
from backend.app.services.workspace_sync import sync_run_workspace

async def execute_agent_for_session(
    db: AsyncSession,
    session: CollaborationSession,
    user_message: SessionMessage,
    adapter_type: Optional[str] = None
) -> Optional[SessionMessage]:
    """
    Executes the configured Agent Adapter for a given collaboration session message:
    1. Assembles multi-layered strategic context (Mother blueprint + upstream baselines).
    2. Invokes the Agent Adapter (CLI Subprocess or Simulator) inside the physical module workspace.
    3. Captures output events, persists Artifact / SessionMessage in DB, and synchronizes workspace.
    """
    mod_stmt = select(ModuleInstance).where(ModuleInstance.id == session.module_id)
    mod_res = await db.execute(mod_stmt)
    module = mod_res.scalar_one_or_none()
    if not module:
        return None

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

    # 6. Handle Artifact Persistence if generated (指令/反馈产出交付物)
    if produced_artifact_content:
        # Determine next version
        art_stmt = (
            select(Artifact)
            .where(Artifact.module_id == module.id)
            .order_by(Artifact.version.desc())
        )
        art_res = await db.execute(art_stmt)
        existing = art_res.scalars().all()
        next_ver = (existing[0].version + 1) if existing else 1

        artifact = Artifact(
            module_id=module.id,
            title=f"{module.name} 规范文档 v{next_ver}",
            version=next_ver,
            content=produced_artifact_content,
            content_hash=calculate_sha256(produced_artifact_content),
            is_baseline=False
        )
        db.add(artifact)
        await db.flush()

        # Advance module phase if still draft
        if module.phase == "draft":
            module.phase = "discussing"
            db.add(module)

        msg_title = "初稿" if produced_artifact_event_type == AgentEventType.ARTIFACT_DRAFT else "修订版"
        agent_msg = SessionMessage(
            session_id=session.id,
            sender=sender_label,
            sender_role="agent",
            role_code=role_code,
            message_type="draft_artifact" if msg_title == "初稿" else "revised_artifact",
            content=f"已由【{role_name}】通过 Agent 适配器在物理工作区完成推演，产出了交付物【{artifact.title}】。相关文件已同步，请在右侧查阅并审阅。",
            artifact_ref_id=artifact.id,
            metadata_json={"logs_preview": logs[-3:] if logs else [], "role_code": role_code, "role_name": role_name}
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
