import hashlib
import os
import stat
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.app.adapters.base import AgentEventType
from backend.app.adapters.cli_adapter import CliSubprocessAdapter
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.mcp.role_mcp_server import ROLE_MCP_TOOLS, call_tool, visible_tools
from backend.app.models.entities import (
    Artifact,
    ExecutiveRisk,
    GateApplication,
    ModuleInstance,
    Product,
    StrategicInitiative,
)
from backend.app.services import orchestrator
from backend.app.services.agent_roles import DEFAULT_AGENT_ROLES, render_persona, seed_agent_roles_if_empty
from backend.app.services.context_assembler import assemble_module_context
from backend.app.services.deliverable_audit import audit_stage, find_unbaselined_prices
from backend.app.services.gate_keeper import create_or_update_gate_application, review_gate_application
from backend.app.services.lead_service import evaluate_gate_by_lead
from backend.app.services.simulator_deliverables import build_simulated_deliverable
from backend.app.services.workflow_engine import (
    can_baseline_module,
    create_workflow_run_from_template,
    load_price_baseline,
    seed_templates_if_empty,
)
from backend.app.services.workspace_sandbox import (
    build_sandbox_profile,
    take_integrity_snapshot,
    verify_and_restore,
)
from backend.tests.conftest import TestingSessionLocal as AsyncSessionLocal
from backend.tests.conftest import ensure_test_product_authorization
from backend.tests.conftest import test_engine as engine
from backend.tests.test_gate_system import _PASSING_PRD


@pytest_asyncio.fixture(autouse=True)
async def setup_env():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


async def _make_run(db, suffix: str, shadow_mode: bool = False, platform: str = "ios"):
    init = StrategicInitiative(id=f"rb-init-{suffix}", name="角色边界测试")
    prod = Product(
        id=f"rb-p-{suffix}", initiative_id=init.id, name="边界产品",
        code=f"RB-{suffix.upper()}", stage="growth", shadow_mode=shadow_mode, platform=platform,
    )
    db.add_all([init, prod])
    await db.commit()
    ensure_test_product_authorization(init.id, prod.code)
    run = await create_workflow_run_from_template(db, prod.id, "full-product-launch", f"Sprint-{suffix}")
    return prod, run


async def _module(db, run_id: str, code: str) -> ModuleInstance:
    return (await db.execute(select(ModuleInstance).where(
        ModuleInstance.run_id == run_id, ModuleInstance.module_code == code
    ).execution_options(populate_existing=True))).scalar_one()


async def _add_artifact(db, mod: ModuleInstance, content: str, version: int = 1) -> Artifact:
    art = Artifact(
        module_id=mod.id, version=version, title=f"工序 {mod.module_code} 交付物", content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    db.add(art)
    await db.commit()
    await db.refresh(art)
    return art


# ---------------------------------------------------------------------------
# G3 belongs to qa
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lead_cannot_release_g3_and_qa_can():
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "g3")
        m08 = await _module(db, run.id, "08")
        gate = await create_or_update_gate_application(
            db=db, module_id=m08.id, recommendation="质量门申请", evidence=[],
            risk_assessment="确定性检查全部通过", submitted_by="agent:qa",
        )
        assert gate.effective_level == "green"

        gate, _ = await evaluate_gate_by_lead(db=db, gate_id=gate.id)
        assert gate.status == "pending"

        with pytest.raises(PermissionError):
            await review_gate_application(db, gate.id, "approve", "lead 代批", actor="agent:lead", actor_role="lead")

        gate = await review_gate_application(db, gate.id, "approve", "P0/P1 清零", actor="agent:qa", actor_role="qa")
        assert gate.status == "approved" and gate.reviewer_role == "qa"


@pytest.mark.asyncio
async def test_qa_cannot_release_lead_owned_green_gate():
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "qa-01")
        m01 = await _module(db, run.id, "01")
        gate = await create_or_update_gate_application(
            db=db, module_id=m01.id, recommendation="门禁自检", evidence=[],
            risk_assessment="确定性检查全部通过", submitted_by="agent:mr",
        )
        with pytest.raises(PermissionError):
            await review_gate_application(db, gate.id, "approve", "越权", actor="agent:qa", actor_role="qa")


# ---------------------------------------------------------------------------
# cmp checkpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmp_needs_fix_blocks_lead_baseline_but_not_human():
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "cmp05")
        m05 = await _module(db, run.id, "05")
        await _add_artifact(db, m05, _PASSING_PRD + "\n会员订阅按月自动续费。\n")
        gate = await create_or_update_gate_application(
            db=db, module_id=m05.id, recommendation="PRD 放行", evidence=[],
            risk_assessment="确定性检查全部通过", submitted_by="agent:pm",
        )
        await review_gate_application(db, gate.id, "approve", "lead 放行", actor="agent:lead", actor_role="lead")

        ok, reason = await can_baseline_module(db, m05.id)
        assert not ok and "合规风控" in reason and "needs_fix" in reason

        await review_gate_application(db, gate.id, "approve", "人类知悉并放行", actor="human:sponsor", actor_role="human")
        ok, reason = await can_baseline_module(db, m05.id)
        assert ok, reason


@pytest.mark.asyncio
async def test_cmp_legal_review_escalates_release_gate_to_red_g5():
    async with AsyncSessionLocal() as db:
        prod, run = await _make_run(db, "cmp09")
        m09 = await _module(db, run.id, "09")
        content, _ = build_simulated_deliverable("09", {"product_name": "边界产品", "platform": "ios"})
        no_privacy = "\n".join(line for line in content.splitlines() if "隐私" not in line)
        await _add_artifact(db, m09, no_privacy)

        status = await orchestrator.on_artifact_created(db, m09.id, origin="human_confirmed")
        assert status == "awaiting_gate"

        gate = (await db.execute(select(GateApplication).where(GateApplication.module_id == m09.id))).scalar_one()
        assert gate.effective_level == "red"
        assert "compliance_high_risk" in (gate.escalation_reasons or [])
        assert gate.status == "pending"
        assert any(e.get("checker") == "compliance_engine" and e.get("status") == "legal_review" for e in gate.evidence)

        risks = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code == "COMPLIANCE_G5_09"
        ))).scalars().all()
        assert len(risks) == 1


# ---------------------------------------------------------------------------
# ba is the only pricing source
# ---------------------------------------------------------------------------

def test_price_lines_outside_baseline_are_detected():
    baseline = [2.99, 29.99]
    assert find_unbaselined_prices(["| 周卡订阅 | $2.99/周 |"], baseline) == []
    assert find_unbaselined_prices(["测试预算 $200", "预估 eCAC $1.10", "竞品月卡 $9.99"], baseline) == []
    assert find_unbaselined_prices(["年订阅 ¥128 起"], baseline) == ["年订阅 ¥128 起"]
    assert find_unbaselined_prices(["订阅价格 4.99 美元/月"], baseline) == ["订阅价格 4.99 美元/月"]


@pytest.mark.asyncio
async def test_downstream_stage_cannot_change_stage_02_prices():
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "price")
        m02 = await _module(db, run.id, "02")
        art02 = await _add_artifact(db, m02, "| 周卡订阅 | $2.99/周 |\n| 年订阅 | $29.99/年 |\n")
        m02.baseline_artifact_id = art02.id
        m02.phase = "baselined"
        await db.commit()

        m10 = await _module(db, run.id, "10")
        baseline = await load_price_baseline(db, m10)
        assert set(baseline) == {2.99, 29.99}

        doc, _ = build_simulated_deliverable("10", {"product_name": "边界产品"})
        assert audit_stage("10", [doc], price_baseline=baseline)["passed"]

        repriced = audit_stage("10", [doc + "\n- 首发限时：年订阅 $19.99/年\n"], price_baseline=baseline)
        assert not repriced["passed"]
        assert any("价格唯一来源是 ba" in r for r in repriced["reasons"])

        assert audit_stage("01", ["竞品年订阅 $19.99/年"], price_baseline=baseline)["pricing"]["passed"]


# ---------------------------------------------------------------------------
# Personas follow the project Profile
# ---------------------------------------------------------------------------

def _role(code: str) -> dict:
    return next(r for r in DEFAULT_AGENT_ROLES if r["role_code"] == code)


def test_static_personas_do_not_hardcode_one_platform():
    assert "71pt" not in _role("ux")["system_persona"]
    assert "零推理成本”红线" not in _role("eng")["system_persona"]


def test_rendered_persona_matches_profile():
    ux = _role("ux")["system_persona"]
    android = render_persona("ux", ux, "android", True)
    assert "48×48dp" in android and "≥71pt" not in android
    assert "≥71pt" in render_persona("ux", ux, "ios", True)

    eng = _role("eng")["system_persona"]
    assert "client_zero_inference=true" in render_persona("eng", eng, "ios", True)
    edge = render_persona("eng", eng, "android", False)
    assert "client_zero_inference=false" in edge and "ONNX Runtime" in edge


@pytest.mark.asyncio
async def test_context_for_android_design_stage_uses_material_rules():
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "ctx", platform="android")
        m06 = await _module(db, run.id, "06")
        context, _path, _meta = await assemble_module_context(db=db, module_id=m06.id, user_instruction="出设计规范")
        assert "Material Design 3" in context
        assert "灵动岛顶部安全区 ≥71pt" not in context


# ---------------------------------------------------------------------------
# Real tool names and MCP scoping
# ---------------------------------------------------------------------------

def test_allowed_tools_are_real_mcp_tools():
    for role in DEFAULT_AGENT_ROLES:
        real = {t["name"] for t in ROLE_MCP_TOOLS.get(role["role_code"], [])}
        assert set(role["allowed_tools"]) == real, role["role_code"]
    assert _role("lead")["allowed_tools"] == [] and _role("cmp")["allowed_tools"] == []


def test_mcp_tools_are_scoped_by_role_platform_and_primary(tmp_path):
    assert [t["name"] for t in visible_tools("ux", "android")] == ["audit_material_spec"]
    assert [t["name"] for t in visible_tools("ux", "ios")] == ["audit_hig_safe_area"]

    foreign = call_tool("mr", tmp_path, "simulate_unit_economics", {})
    assert foreign["passed"] is False and "不属于角色 mr" in foreign["error"]

    wrong_platform = call_tool("ux", tmp_path, "audit_hig_safe_area", {}, platform="android")
    assert "error" in wrong_platform

    advisory = call_tool("ba", tmp_path, "simulate_unit_economics", {}, is_primary=False)
    assert advisory["advisory_only"] is True and advisory["caller_is_primary"] is False
    assert all("仅供参考" in t["description"] for t in visible_tools("ba", is_primary=False))


# ---------------------------------------------------------------------------
# CLI filesystem sandbox
# ---------------------------------------------------------------------------

def _stage_layout(root: Path):
    product_dir = root / "init" / "products" / "APP"
    workspace = product_dir / "Sprint-1" / "06_设计实现"
    (workspace / ".agents" / "skills" / "ux").mkdir(parents=True)
    (product_dir / "decisions").mkdir(parents=True)
    auth = product_dir / "authorization.yaml"
    auth.write_text("budget: 100\n", encoding="utf-8")
    os.chmod(auth, 0o444)
    (product_dir / "decisions" / "old.json").write_text("{}", encoding="utf-8")
    (workspace / ".agents" / "skills" / "ux" / "check_hig.py").write_text("THRESHOLD = 71\n", encoding="utf-8")
    return product_dir, workspace, auth


def test_integrity_check_restores_protected_files(tmp_path):
    product_dir, workspace, auth = _stage_layout(tmp_path)
    snap = take_integrity_snapshot(workspace)

    os.chmod(auth, 0o644)
    auth.write_text("budget: 999999\n", encoding="utf-8")
    (product_dir / "decisions" / "old.json").unlink()
    (product_dir / "decisions" / "new_backend_log.json").write_text("{}", encoding="utf-8")
    (workspace / ".agents" / "skills" / "ux" / "check_hig.py").write_text("THRESHOLD = 1\n", encoding="utf-8")
    (workspace / ".agents" / "skills" / "ux" / "bypass.py").write_text("", encoding="utf-8")
    (workspace / "交付物_06.md").write_text("ok", encoding="utf-8")

    violations = verify_and_restore(snap)
    names = sorted(Path(v).name for v in violations)
    assert names == ["authorization.yaml", "bypass.py", "check_hig.py", "old.json"]
    assert auth.read_text(encoding="utf-8") == "budget: 100\n"
    assert stat.S_IMODE(auth.stat().st_mode) == 0o444
    assert (product_dir / "decisions" / "old.json").exists()
    assert (product_dir / "decisions" / "new_backend_log.json").exists()
    assert not (workspace / ".agents" / "skills" / "ux" / "bypass.py").exists()
    assert (workspace / "交付物_06.md").exists()
    assert verify_and_restore(snap) == []


def test_sandbox_profile_limits_writes_to_stage_dir(tmp_path):
    _product_dir, workspace, _auth = _stage_layout(tmp_path)
    profile = build_sandbox_profile(workspace, home=tmp_path / "home")
    resolved = str(workspace.resolve())
    assert "(deny file-write*)" in profile
    assert f'(subpath "{resolved}")' in profile
    assert f'(subpath "{resolved}/.agents/skills")' in profile
    assert str((tmp_path / "home" / ".claude").resolve()) in profile
    assert str(_product_dir.resolve() / "decisions") not in profile


@pytest.mark.asyncio
async def test_cli_run_that_tampers_with_authorization_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "AGENT_FS_SANDBOX", "off")
    product_dir, workspace, auth = _stage_layout(tmp_path)
    fake_cli = tmp_path / "fakecli"
    fake_cli.write_text(
        "#!/bin/sh\n"
        f"chmod u+w '{auth}'\n"
        f"echo 'budget: 999999' > '{auth}'\n"
        "echo '# 交付物' > \"交付物_06_设计实现.md\"\n"
        "echo done\n",
        encoding="utf-8",
    )
    os.chmod(fake_cli, 0o755)

    adapter = CliSubprocessAdapter(cli_command=str(fake_cli), timeout=30)
    events = [e async for e in adapter.execute_task(
        task_id="t1", workspace_dir=workspace, system_context="ctx", user_instruction="出设计",
        metadata={"module_code": "06", "module_name": "设计实现", "role_code": "ux", "platform": "ios"},
    )]
    errors = [e for e in events if e.event_type == AgentEventType.ERROR]
    assert errors and "沙箱越权" in errors[0].content
    assert str(auth) in errors[0].metadata["sandbox_violations"]
    assert not any(e.event_type == AgentEventType.ARTIFACT_DRAFT for e in events)
    assert auth.read_text(encoding="utf-8") == "budget: 100\n"
