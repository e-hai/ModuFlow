import asyncio
from typing import AsyncIterator, Optional, Dict, Any
from pathlib import Path
from backend.app.adapters.base import BaseAgentAdapter, AgentStreamEvent, AgentEventType
from backend.app.services.agent_simulator import MODULE_TEMPLATES_CONTENT
from backend.app.services.simulator_deliverables import SIMULATION_BANNER, build_simulated_deliverable

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

        if message_type == "review":
            from backend.app.services.collaboration import simulated_review
            spec = (metadata or {}).get("review_spec") or {"reviewer": "agent", "focus": "协作评审"}
            yield AgentStreamEvent(event_type=AgentEventType.ANSWER, content=simulated_review(spec, mod_code))
            yield AgentStreamEvent(event_type=AgentEventType.DONE, content="[Simulator] 协作评审完成")
            return

        if message_type == "question":
            from backend.app.services.domain_qa import generate_domain_qa_answer
            yield AgentStreamEvent(
                event_type=AgentEventType.LOG,
                content=f"[Simulator] 收到讨论提问: {user_instruction}"
            )
            yield AgentStreamEvent(
                event_type=AgentEventType.THINKING,
                content=f"已读取母战略工程底稿，正在为工序【{mod_name}】推演业务问题: '{user_instruction}'..."
            )
            answer = generate_domain_qa_answer(
                question=user_instruction,
                module_name=mod_name,
                system_context=system_context,
                metadata=metadata
            )
            yield AgentStreamEvent(
                event_type=AgentEventType.ANSWER,
                content=answer,
                metadata={"source": "simulator"}
            )
            yield AgentStreamEvent(
                event_type=AgentEventType.DONE,
                content="[Simulator] 问答推演完成"
            )
            return

        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Simulator] 收到任务指令: {user_instruction}"
        )

        yield AgentStreamEvent(
            event_type=AgentEventType.THINKING,
            content=f"已读取战略底稿，正在为工序 {mod_code} ({mod_name}) 生成规范草案..."
        )

        extra_files: Dict[str, str] = {}
        if mod_code == "01":
            from backend.app.services.market_research_engine import generate_comprehensive_market_report
            from backend.app.services.delivery_contract import MANIFEST_FILENAME, build_stage_manifest

            product_name = (metadata or {}).get("product_name") or "当前产品"
            product_code = (metadata or {}).get("product_code") or "PRD"
            target_market = (metadata or {}).get("target_market") or "目标细分市场"
            strategic_intent = (metadata or {}).get("strategic_intent") or ""
            template_content = generate_comprehensive_market_report(
                product_name=product_name,
                product_code=product_code,
                target_market=target_market,
                strategic_intent=strategic_intent,
                user_instruction=user_instruction
            )
            template_content = SIMULATION_BANNER + template_content
            extra_files[MANIFEST_FILENAME] = build_stage_manifest("01", f"交付物_{mod_code}_{mod_name}.md")
        else:
            template_content, extra_files = build_simulated_deliverable(mod_code, metadata)
            if not template_content:
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

        filename = f"交付物_{mod_code}_{mod_name}.md"
        (workspace_dir / filename).write_text(content, encoding="utf-8")
        from backend.app.services.delivery_contract import MANIFEST_FILENAME, bind_manifest_report_path

        for rel_name, file_content in extra_files.items():
            if rel_name == MANIFEST_FILENAME:
                file_content = bind_manifest_report_path(file_content, filename)
            target = workspace_dir / rel_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file_content, encoding="utf-8")

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
