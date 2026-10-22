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
        elif event.event_type == AgentEventType.LOG:
            logs.append(event.content)

    # 4. Handle Artifact Persistence if generated
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
            sender="AI Agent (CLI)",
            sender_role="agent",
            message_type="draft_artifact" if msg_title == "初稿" else "revised_artifact",
            content=f"已通过 Agent 适配器在工作区完成推演，产出了交付物【{artifact.title}】。相关文件已同步至物理工作区，请在右侧查阅并审阅。",
            artifact_ref_id=artifact.id,
            metadata_json={"logs_preview": logs[-3:] if logs else []}
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

    elif msg_type == "question":
        # Human asked a general question
        reply_content = (
            f"根据母战略工程《{meta.get('initiative_id', '当前工程')}》顶层底稿与当前工序【{module.name}】的基线规范：\n\n"
            f"关于您提出的问题：**{content}**\n\n"
            f"1. **战略原则对齐**：必须符合母工程商业闭环与单位经济约束。\n"
            f"2. **执行建议**：建议在当前工序下明确具体验收标准后，再触发下一轮设计或开发工序。\n"
            f"如有明确变更需求，请直接下达修订指令。"
        )
        agent_msg = SessionMessage(
            session_id=session.id,
            sender="AI Agent (CLI)",
            sender_role="agent",
            message_type="answer",
            content=reply_content
        )
        db.add(agent_msg)
        await db.commit()
        await db.refresh(agent_msg)
        return agent_msg

    return None
