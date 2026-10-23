import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.main import app
from backend.tests.conftest import test_engine as engine, TestingSessionLocal as AsyncSessionLocal
from backend.app.core.database import Base
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
from backend.app.adapters.cli_adapter import (
    CliSubprocessAdapter,
    build_cli_arguments,
    find_cli_binary
)
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

def test_cli_argument_builders():
    # Claude syntax
    claude_args = build_cli_arguments("/usr/local/bin/claude", "test prompt")
    assert claude_args == ["/usr/local/bin/claude", "-p", "test prompt", "--dangerously-skip-permissions"]

    # agy syntax
    agy_args = build_cli_arguments("/Users/a/.local/bin/agy", "test prompt")
    assert agy_args == ["/Users/a/.local/bin/agy", "-p", "test prompt", "--dangerously-skip-permissions"]

    # codex syntax
    codex_args = build_cli_arguments("/opt/homebrew/bin/codex", "test prompt")
    assert codex_args == [
        "/opt/homebrew/bin/codex",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "test prompt"
    ]

    # custom syntax
    custom_args = build_cli_arguments("/usr/bin/custom-cli", "test prompt")
    assert custom_args == ["/usr/bin/custom-cli", "-p", "test prompt"]

@pytest.mark.asyncio
async def test_cli_adapter_missing_binary_reports_error(tmp_path: Path):
    """When the configured CLI command does not exist, it must report error, never fake artifacts."""
    adapter = CliSubprocessAdapter(cli_command="nonexistent-mock-agent-cli", timeout=2)
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
    assert "error" in types
    assert "artifact_draft" not in types
    assert "answer" not in types

@pytest.mark.asyncio
async def test_cli_adapter_execution(tmp_path: Path):
    """Test real CLI subprocess execution with an executable script."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cli_script = bin_dir / "test-agent-cli"
    cli_script.write_text(
        "#!/bin/sh\n"
        "echo '[Subprocess] Running Agent task'\n"
        "echo '# 市场调研 交付物' > \"$MODUFLOW_WORKSPACE/交付物_01_市场调研.md\"\n"
        "echo '# 市场调研 交付物全文内容'\n"
    )
    cli_script.chmod(0o755)

    # Put bin_dir on PATH
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{old_path}"

    try:
        adapter = CliSubprocessAdapter(cli_command="test-agent-cli", timeout=5)
        events = []
        async for event in adapter.execute_task(
            task_id="test-t2",
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
    finally:
        os.environ["PATH"] = old_path

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

        # Now test Question flow (should NOT create a new artifact, but return answer message)
        question_msg = SessionMessage(
            session_id=session.id,
            sender="产品负责人",
            sender_role="human",
            message_type="question",
            content="壁纸应用，应该有什么功能"
        )
        db.add(question_msg)
        await db.commit()
        await db.refresh(question_msg)

        answer_msg = await execute_agent_for_session(db, session, question_msg, adapter_type="simulator")
        assert answer_msg is not None
        assert answer_msg.sender_role == "agent"
        assert answer_msg.message_type == "answer"
        assert answer_msg.artifact_ref_id is None
        assert "壁纸" in answer_msg.content or "功能" in answer_msg.content

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
            json={"adapter_type": "cli", "cli_command": "mock-agent-cli", "timeout": 1}
        )
        assert res_patch.status_code == 200
        patched = res_patch.json()
        assert patched["adapter_type"] == "cli"
        assert patched["cli_command"] == "mock-agent-cli"
        assert patched["timeout"] == 1

        # 3. Dry-run test endpoint
        res_test = await ac.post("/api/v1/settings/agent/test")
        assert res_test.status_code == 200
        test_data = res_test.json()
        assert test_data["success"] is True

        # 4. Clean up: restore simulator
        await ac.patch(
            "/api/v1/settings/agent",
            json={"adapter_type": "simulator"}
        )

@pytest.mark.asyncio
async def test_agent_runner_cli_failure_reports_error_without_mock_data():
    """Ensure that when CLI fails, runner reports message_type='error' and creates NO artifact."""
    async with AsyncSessionLocal() as db:
        m_stmt = select(ModuleInstance).join(WorkflowRun).where(WorkflowRun.product_id == "test-prod").order_by(ModuleInstance.order_index.asc())
        res = await db.execute(m_stmt)
        mod = res.scalars().first()

        session = CollaborationSession(
            module_id=mod.id,
            title="异常测试协作会话",
            participants=[{"role": "human", "name": "PM"}]
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        # Count artifacts before
        count_before = len((await db.execute(select(Artifact).where(Artifact.module_id == mod.id))).scalars().all())

        # Send a question using nonexistent CLI
        q_msg = SessionMessage(
            session_id=session.id,
            sender="业务负责人",
            sender_role="human",
            message_type="question",
            content="询问异常情况"
        )
        db.add(q_msg)
        await db.commit()
        await db.refresh(q_msg)

        from backend.app.adapters.cli_adapter import CliSubprocessAdapter
        # Temporarily mock adapter to use nonexistent CLI
        runner_msg = await execute_agent_for_session(db, session, q_msg, adapter_type="cli")
        assert runner_msg is not None
        assert runner_msg.message_type == "error"
        assert runner_msg.artifact_ref_id is None
        assert "未找到命令行工具" in runner_msg.content or "异常" in runner_msg.content or "未在" in runner_msg.content

        # Count artifacts after -> MUST NOT have increased
        count_after = len((await db.execute(select(Artifact).where(Artifact.module_id == mod.id))).scalars().all())
        assert count_after == count_before

