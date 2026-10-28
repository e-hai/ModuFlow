import asyncio
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.adapters.base import AgentEventType, AgentStreamEvent, BaseAgentAdapter
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.main import app
from backend.app.models.entities import (
    Artifact,
    ExecutiveRisk,
    GateApplication,
    LeadShadowDecision,
    ModuleInstance,
    Product,
    StrategicInitiative,
)
from backend.app.services import agent_runner, orchestrator
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.services.gate_keeper import review_gate_application
from backend.app.services.lead_service import (
    SHADOW_READY_MIN_RESOLVED,
    get_shadow_mode_stats,
    shadow_readiness,
)
from backend.app.services.workflow_engine import create_workflow_run_from_template, seed_templates_if_empty
from backend.tests.conftest import TestingSessionLocal as AsyncSessionLocal
from backend.tests.conftest import ensure_test_product_authorization
from backend.tests.conftest import test_engine as engine
from backend.tests.test_gate_system import _HEALTHY_UE

_SOM_DOC = (
    '{"monthly_search_volume": 120000, "target_capture_rate": 0.04, '
    '"blended_arpu_usd": 1.8, "source": "测试夹具：假设/待验证"}\n'
)
_THIN_DOC = "只有一句说明，没有任何可复核的数字。"


class ScriptedAdapter(BaseAgentAdapter):
    """Returns scripted deliverables per stage; unknown stages get a draft that fails the checks."""

    def __init__(self, outputs: Dict[str, str]):
        self.outputs = outputs
        self.calls: List[str] = []

    async def execute_task(self, task_id, workspace_dir, system_context, user_instruction,
                           message_type="instruction", metadata: Optional[Dict[str, Any]] = None):
        code = (metadata or {}).get("module_code", "")
        self.calls.append(code)
        event = AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED
        yield AgentStreamEvent(event_type=event, content=self.outputs.get(code, _THIN_DOC))
        yield AgentStreamEvent(event_type=AgentEventType.DONE, content="done")

    async def cancel_task(self, task_id: str) -> bool:
        return True


@pytest_asyncio.fixture(autouse=True)
async def setup_orchestrator_env():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


def _use_adapter(monkeypatch, outputs: Dict[str, str]) -> ScriptedAdapter:
    adapter = ScriptedAdapter(outputs)
    monkeypatch.setattr(agent_runner, "get_agent_adapter", lambda adapter_type=None: adapter)
    return adapter


async def _make_run(db, suffix: str, shadow_mode: bool, stage: str = "growth"):
    init = StrategicInitiative(id=f"orch-init-{suffix}", name="自动编排测试")
    prod = Product(
        id=f"orch-p-{suffix}", initiative_id=init.id, name="编排产品",
        code=f"ORCH-{suffix.upper()}", stage=stage, shadow_mode=shadow_mode,
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


async def _artifact_count(db, module_id: str) -> int:
    return len((await db.execute(select(Artifact).where(Artifact.module_id == module_id))).scalars().all())


@pytest.mark.asyncio
async def test_green_stage_auto_finalizes_and_dispatches_downstream(monkeypatch):
    adapter = _use_adapter(monkeypatch, {"01": _SOM_DOC, "02": _HEALTHY_UE})
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "green", shadow_mode=False)
        result = await orchestrator.advance_run(db, run.id)

        m01 = await _module(db, run.id, "01")
        m02 = await _module(db, run.id, "02")
        assert m01.phase == "baselined"
        assert m02.is_unlocked
        assert "01" in result["dispatched"] and "02" in result["dispatched"]
        assert adapter.calls[:2] == ["01", "02"]

        gate01 = (await db.execute(select(GateApplication).where(GateApplication.module_id == m01.id))).scalar_one()
        assert gate01.status == "approved" and gate01.reviewer_role == "lead"

        gate02 = (await db.execute(select(GateApplication).where(GateApplication.module_id == m02.id))).scalar_one()
        assert gate02.effective_level == "yellow"
        assert gate02.status == "pending"
        assert m02.phase != "baselined"


@pytest.mark.asyncio
async def test_yellow_gate_waits_for_human_then_auto_advances(monkeypatch):
    adapter = _use_adapter(monkeypatch, {"01": _SOM_DOC, "02": _HEALTHY_UE})
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "yellow", shadow_mode=False)
        await orchestrator.advance_run(db, run.id)
        m02 = await _module(db, run.id, "02")
        gate02 = (await db.execute(select(GateApplication).where(GateApplication.module_id == m02.id))).scalar_one()

        with pytest.raises(PermissionError):
            await review_gate_application(db, gate02.id, "approve", "lead 不能批", actor="agent:lead", actor_role="lead")

        again = await orchestrator.advance_run(db, run.id)
        assert again["dispatched"] == []
        assert (await _module(db, run.id, "02")).phase != "baselined"

        await review_gate_application(db, gate02.id, "approve", "同意", actor="human:sponsor", actor_role="human")
        status = await orchestrator.on_gate_reviewed(db, gate02.id)
        assert status == "baselined"

        assert (await _module(db, run.id, "02")).phase == "baselined"
        m03 = await _module(db, run.id, "03")
        assert m03.is_unlocked
        assert await _artifact_count(db, m03.id) >= 1
        assert "03" in adapter.calls


@pytest.mark.asyncio
async def test_two_failed_revisions_raise_risk_and_stop(monkeypatch):
    adapter = _use_adapter(monkeypatch, {"01": _THIN_DOC})
    async with AsyncSessionLocal() as db:
        prod, run = await _make_run(db, "stuck", shadow_mode=False)
        await orchestrator.advance_run(db, run.id)

        m01 = await _module(db, run.id, "01")
        assert m01.phase != "baselined"
        assert await _artifact_count(db, m01.id) == 1 + orchestrator.MAX_AUTO_REVISIONS
        assert adapter.calls == ["01"] * (1 + orchestrator.MAX_AUTO_REVISIONS)

        risk = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code == "ORCH_STUCK_01"
        ))).scalar_one()
        assert not risk.is_resolved

        gate = (await db.execute(select(GateApplication).where(GateApplication.module_id == m01.id))).scalar_one_or_none()
        assert gate is None

        again = await orchestrator.advance_run(db, run.id)
        assert again["dispatched"] == [] and again["processed"] == []

        status = await orchestrator.get_run_orchestration_status(db, run.id)
        assert status["current_stage"]["state"] == "revision_failed"


@pytest.mark.asyncio
async def test_advance_unlocks_downstream_missed_by_an_external_baseline(monkeypatch):
    adapter = _use_adapter(monkeypatch, {"02": _HEALTHY_UE})
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "relock", shadow_mode=False)
        m01 = await _module(db, run.id, "01")
        m02 = await _module(db, run.id, "02")
        art = Artifact(
            module_id=m01.id, version=1, title="工序 01", content=_SOM_DOC,
            content_hash="relock-01", is_baseline=True,
        )
        db.add(art)
        await db.flush()
        m01.phase = "baselined"
        m01.baseline_artifact_id = art.id
        m02.is_unlocked = False
        await db.commit()

        result = await orchestrator.advance_run(db, run.id)
        assert (await _module(db, run.id, "02")).is_unlocked
        assert "02" in result["dispatched"]
        assert adapter.calls[:1] == ["02"]


@pytest.mark.asyncio
async def test_paused_project_dispatches_nothing(monkeypatch):
    adapter = _use_adapter(monkeypatch, {"01": _SOM_DOC})
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "paused", shadow_mode=False, stage="paused")
        result = await orchestrator.advance_run(db, run.id)
        assert result["status"] == "paused"
        assert result["dispatched"] == []
        assert adapter.calls == []
        assert await _artifact_count(db, (await _module(db, run.id, "01")).id) == 0


@pytest.mark.asyncio
async def test_shadow_mode_keeps_green_gate_pending_for_human(monkeypatch):
    _use_adapter(monkeypatch, {"01": _SOM_DOC})
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "shadow", shadow_mode=True)
        await orchestrator.advance_run(db, run.id)

        m01 = await _module(db, run.id, "01")
        assert m01.phase != "baselined"
        gate = (await db.execute(select(GateApplication).where(GateApplication.module_id == m01.id))).scalar_one()
        assert gate.status == "pending"
        assert gate.lead_recommendation == "approved"

        status = await orchestrator.get_run_orchestration_status(db, run.id)
        assert status["current_stage"]["state"] == "awaiting_human_gate"


@pytest.mark.asyncio
async def test_auto_advance_switch_is_human_only_and_stops_dispatch(monkeypatch):
    adapter = _use_adapter(monkeypatch, {"01": _SOM_DOC})
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "switch", shadow_mode=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        denied = await ac.patch(
            f"/api/v1/runs/{run.id}/auto-advance",
            json={"enabled": False},
            headers={"X-ModuFlow-Actor": "agent:lead"},
        )
        assert denied.status_code == 403

        off = await ac.patch(
            f"/api/v1/runs/{run.id}/auto-advance",
            json={"enabled": False},
            headers={"X-ModuFlow-Actor": "human:sponsor"},
        )
        assert off.status_code == 200 and off.json()["auto_advance"] is False

        res = await ac.post(f"/api/v1/runs/{run.id}/advance")
        assert res.status_code == 200
        assert res.json()["status"] == "auto_advance_off"
        assert adapter.calls == []

        on = await ac.patch(
            f"/api/v1/runs/{run.id}/auto-advance",
            json={"enabled": True},
            headers={"X-ModuFlow-Actor": "human:sponsor"},
        )
        assert on.status_code == 200
        for _ in range(50):
            if adapter.calls[:1] == ["01"]:
                break
            await asyncio.sleep(0.02)
        assert adapter.calls[:1] == ["01"]

    for _ in range(50):
        async with AsyncSessionLocal() as db:
            if (await _module(db, run.id, "01")).phase == "baselined":
                break
        await asyncio.sleep(0.05)

    async with AsyncSessionLocal() as db:
        assert (await _module(db, run.id, "01")).phase == "baselined"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["ios", "android"])
async def test_simulator_runs_full_launch_with_only_required_human_steps(platform):
    async with AsyncSessionLocal() as db:
        prod, run = await _make_run(db, f"sim-{platform}", shadow_mode=False)
        prod.platform = platform
        await db.commit()

        await orchestrator.advance_run(db, run.id)
        signed: List[str] = []
        confirmed: List[str] = []
        for _ in range(30):
            modules = (await db.execute(select(ModuleInstance).where(
                ModuleInstance.run_id == run.id
            ).execution_options(populate_existing=True))).scalars().all()
            if all(m.phase == "baselined" for m in modules):
                break
            status = await orchestrator.get_run_orchestration_status(db, run.id)
            stage = status["current_stage"]
            assert stage is not None
            assert stage["state"] in ("awaiting_human_gate", "awaiting_human_confirm"), stage
            if stage["state"] == "awaiting_human_gate":
                await review_gate_application(db, stage["gate_id"], "approve", "同意", actor="human:sponsor", actor_role="human")
                signed.append(stage["module_code"])
                await orchestrator.on_gate_reviewed(db, stage["gate_id"])
            else:
                confirmed.append(stage["module_code"])
                await orchestrator.on_artifact_created(db, stage["module_id"], origin="human_confirmed")

        modules = (await db.execute(select(ModuleInstance).where(
            ModuleInstance.run_id == run.id
        ).execution_options(populate_existing=True))).scalars().all()
        assert all(m.phase == "baselined" for m in modules)
        assert signed == ["02", "03", "04", "09", "10"]
        assert confirmed == []

        gates = {
            g.module_code: g for g in (await db.execute(select(GateApplication).where(
                GateApplication.run_id == run.id
            ))).scalars().all()
        }
        assert gates["08"].reviewer_role == "qa"
        assert gates["05"].reviewer_role == "lead"
        for code in ("03", "05", "09"):
            assert any(e.get("checker") == "compliance_engine" and e.get("status") == "passed"
                       for e in gates[code].evidence), code
        for code in ("04", "05", "06", "07", "09", "10", "11"):
            review = next(e for e in gates[code].evidence if e.get("checker") == "collaboration_review")
            assert review["results"] and all(r["verdict"] == "approve" for r in review["results"]), code

        stuck = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code.like("ORCH_%")
        ))).scalars().all()
        assert stuck == []


def _decisions(pattern: List[bool]) -> List[LeadShadowDecision]:
    return [LeadShadowDecision(is_consistent=v, human_decision="approved") for v in pattern]


def test_shadow_readiness_thresholds():
    ready, reason = shadow_readiness(_decisions([True] * (SHADOW_READY_MIN_RESOLVED - 1)))
    assert not ready and "至少" in reason

    ready, _ = shadow_readiness(_decisions([True] * SHADOW_READY_MIN_RESOLVED))
    assert ready

    ready, reason = shadow_readiness(_decisions([True] * 17 + [False] * 3))
    assert not ready and "一致率" in reason

    ready, reason = shadow_readiness(_decisions([True] * 19 + [False]))
    assert not ready and "分歧" in reason


@pytest.mark.asyncio
async def test_shadow_stats_never_flip_the_switch():
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id="orch-init-ready", name="影子就绪")
        prod = Product(id="orch-p-ready", initiative_id=init.id, name="就绪产品", code="ORCH-READY", shadow_mode=True)
        db.add_all([init, prod])
        for _ in range(SHADOW_READY_MIN_RESOLVED):
            db.add(LeadShadowDecision(
                product_id=prod.id, lead_recommendation="approved",
                human_decision="approved", is_consistent=True,
            ))
        await db.commit()

        stats = await get_shadow_mode_stats(db, prod.id)
        assert stats["ready_to_disable"] is True
        await db.refresh(prod)
        assert prod.shadow_mode is True
