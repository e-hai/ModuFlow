import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.main import app
from backend.app.core.database import engine, Base, AsyncSessionLocal
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowRun,
    ModuleInstance,
    CollaborationSession,
    SessionMessage,
    Artifact
)
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.context_assembler import assemble_module_context
from backend.app.adapters.cli_adapter import CliSubprocessAdapter
from backend.app.adapters.simulator_adapter import SimulatorAdapter
from backend.app.adapters.factory import get_agent_adapter
from backend.app.services.agent_runner import execute_agent_for_session

@pytest_asyncio.fixture(autouse=True)
async def setup_test_data():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        init = StrategicInitiative(
            id="test-init",
            name="测试出海战略工程",
            strategic_intent="以工具高频获客，以支付变现。",
            target_market="东南亚中小微商户",
            business_model_hypothesis="CAC < 15, LTV/CAC > 3.0"
        )
        db.add(init)
        await db.flush()

        prod = Product(
            id="test-prod",
            initiative_id=init.id,
            name="测试记账本",
            code="T-ACC",
            strategic_role="acquisition",
            stage="growth"
        )
        db.add(prod)
        await db.commit()

        await create_workflow_run_from_template(
            db=db,
            product_id=prod.id,
            template_id="full-product-launch",
            run_name="v1.0-alpha"
        )

@pytest.mark.asyncio
async def test_context_assembler():
    async with AsyncSessionLocal() as db:
        # Find first module
        m_stmt = select(ModuleInstance).join(WorkflowRun).where(WorkflowRun.product_id == "test-prod").order_by(ModuleInstance.order_index.asc())
        res = await db.execute(m_stmt)
        first_mod = res.scalars().first()
        assert first_mod is not None

        context, ws_path, meta = await assemble_module_context(
            db=db,
            module_id=first_mod.id,
            user_instruction="请生成第一阶段市场调研报告"
        )
        assert "测试出海战略工程" in context
        assert "以工具高频获客，以支付变现。" in context
        assert "东南亚中小微商户" in context
        assert "T-ACC" in context
        assert "请生成第一阶段市场调研报告" in context
        assert ws_path.exists()
        assert meta["module_code"] == first_mod.module_code

@pytest.mark.asyncio
async def test_cli_adapter_execution(tmp_path: Path):
    adapter = CliSubprocessAdapter(cli_command="mock-agent-cli", timeout=2)
    events = []
    async for event in adapter.execute_task(
        task_id="test-t1",
        workspace_dir=tmp_path,
        system_context="# Context header",
        user_instruction="制定产品架构方案",
        message_type="instruction",
        metadata={"module_code": "01", "module_name": "市场调研"}
    ):
        events.append(event)

    types = [e.event_type.value for e in events]
    assert "log" in types
    assert "artifact_draft" in types
    assert "done" in types

    # Check that context file and artifact file were written
    assert (tmp_path / ".moduflow_agent_context.md").exists()
    assert (tmp_path / "交付物_01_市场调研.md").exists()

@pytest.mark.asyncio
async def test_agent_runner_with_session():
    async with AsyncSessionLocal() as db:
        # Get module
        m_stmt = select(ModuleInstance).join(WorkflowRun).where(WorkflowRun.product_id == "test-prod").order_by(ModuleInstance.order_index.asc())
        res = await db.execute(m_stmt)
        mod = res.scalars().first()

        # Create session
        session = CollaborationSession(
            module_id=mod.id,
            title="主协作会话",
            participants=[{"role": "human", "name": "PM"}]
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        # Human message
        user_msg = SessionMessage(
            session_id=session.id,
            sender="产品负责人",
            sender_role="human",
            message_type="instruction",
            content="请依据战略底稿，输出东南亚市场用户画像与调研规范"
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # Execute agent runner (with simulator or cli fallback)
        agent_msg = await execute_agent_for_session(db, session, user_msg, adapter_type="simulator")
        assert agent_msg is not None
        assert agent_msg.sender_role == "agent"
        assert agent_msg.artifact_ref_id is not None
        assert agent_msg.message_type == "draft_artifact"

        # Verify artifact in DB
        art_stmt = select(Artifact).where(Artifact.id == agent_msg.artifact_ref_id)
        art_res = await db.execute(art_stmt)
        artifact = art_res.scalar_one_or_none()
        assert artifact is not None
        assert artifact.version == 1

        # Verify module phase advanced to discussing
        await db.refresh(mod)
        assert mod.phase == "discussing"

@pytest.mark.asyncio
async def test_agent_settings_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. GET settings
        res = await ac.get("/api/v1/settings/agent")
        assert res.status_code == 200
        data = res.json()
        assert "adapter_type" in data
        assert "available_presets" in data
        assert len(data["available_presets"]) >= 3

        # 2. PATCH settings
        res_patch = await ac.patch(
            "/api/v1/settings/agent",
            json={"adapter_type": "cli", "cli_command": "claude", "timeout": 60}
        )
        assert res_patch.status_code == 200
        patched = res_patch.json()
        assert patched["adapter_type"] == "cli"
        assert patched["cli_command"] == "claude"
        assert patched["timeout"] == 60

        # 3. Dry-run test endpoint
        res_test = await ac.post("/api/v1/settings/agent/test")
        assert res_test.status_code == 200
        test_data = res_test.json()
        assert test_data["success"] is True

