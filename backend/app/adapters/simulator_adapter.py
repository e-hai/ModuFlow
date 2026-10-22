import asyncio
from typing import AsyncIterator, Optional, Dict, Any
from pathlib import Path
from backend.app.adapters.base import BaseAgentAdapter, AgentStreamEvent, AgentEventType
from backend.app.services.agent_simulator import MODULE_TEMPLATES_CONTENT

class SimulatorAdapter(BaseAgentAdapter):
    """
    Lightweight rule-based simulator adapter.
    Useful for instant local integration tests and offline demos without external dependencies.
    """

    def __init__(self):
        self._cancelled_tasks = set()

    async def execute_task(
        self,
        task_id: str,
        workspace_dir: Path,
        system_context: str,
        user_instruction: str,
        message_type: str = "instruction",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[AgentStreamEvent]:
        mod_code = (metadata or {}).get("module_code", "01")
        mod_name = (metadata or {}).get("module_name", "工序交付物")

        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Simulator] 收到任务指令: {user_instruction}"
        )

        yield AgentStreamEvent(
            event_type=AgentEventType.THINKING,
            content=f"已读取战略底稿，正在为工序 {mod_code} ({mod_name}) 生成规范草案..."
        )

        template_content = MODULE_TEMPLATES_CONTENT.get(
            mod_code,
            f"# {mod_name} 交付物初稿\n\n基于指令生成：{user_instruction}\n\n已完成基础框架搭建与核心要素梳理。"
        )

        if message_type == "feedback":
            content = f"{template_content}\n\n---\n### 依据反馈修订说明\n- **反馈要点**：{user_instruction}\n- **调整说明**：已完成补充与闭环。"
            event_type = AgentEventType.ARTIFACT_REVISED
        else:
            content = template_content
            event_type = AgentEventType.ARTIFACT_DRAFT

        # Write to workspace
        (workspace_dir / f"交付物_{mod_code}_{mod_name}.md").write_text(content, encoding="utf-8")

        yield AgentStreamEvent(
            event_type=event_type,
            content=content,
            metadata={"source": "simulator"}
        )

        yield AgentStreamEvent(
            event_type=AgentEventType.DONE,
            content="[Simulator] 执行完成"
        )

    async def cancel_task(self, task_id: str) -> bool:
        self._cancelled_tasks.add(task_id)
        return True
