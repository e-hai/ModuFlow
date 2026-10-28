import hashlib
import json
from typing import Any, Callable, Dict, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.adapters.base import AgentEventType, AgentStreamEvent
from backend.app.adapters.simulator_adapter import SimulatorAdapter
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.main import app
from backend.app.models.entities import (
    Artifact,
    ExecutiveRisk,
    GateApplication,
    Issue,
    ModuleInstance,
    Product,
    SessionMessage,
    StrategicInitiative,
)
from backend.app.services import agent_runner, collaboration, orchestrator
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.services.deliverable_audit import audit_unit_economics
from backend.app.services.lead_service import generate_project_daily_digest, get_decision_inbox
from backend.app.services.simulator_deliverables import build_simulated_deliverable
from backend.app.services.workflow_engine import create_workflow_run_from_template, seed_templates_if_empty
from backend.tests.conftest import TestingSessionLocal as AsyncSessionLocal
from backend.tests.conftest import ensure_test_product_authorization
from backend.tests.conftest import test_engine as engine


def _sim(code: str) -> str:
    return build_simulated_deliverable(code, {"product_name": "协作产品", "platform": "ios"})[0]


def _verdict(verdict: str, findings: Optional[List[str]] = None, **extra: Any) -> str:
    payload = {"verdict": verdict, "findings": findings or [f"{verdict} 测试意见"], **extra}
    return f"评审意见\n```json\n{json.dumps(payload, ensure_ascii=False)}\n```\n"


class ReviewScriptAdapter(SimulatorAdapter):
    """Simulator for primary work; review messages answered by `verdict_fn(reviewer, nth_call)`."""

    def __init__(self, verdict_fn: Callable[[str, int], str], primary: Optional[Dict[str, str]] = None):
        super().__init__()
        self.verdict_fn = verdict_fn
        self.primary = primary or {}
        self.review_calls: List[str] = []

    async def execute_task(self, task_id, workspace_dir, system_context, user_instruction,
                           message_type="instruction", metadata: Optional[Dict[str, Any]] = None):
        meta = metadata or {}
        if message_type == "review":
            reviewer = meta["review_spec"]["reviewer"]
            self.review_calls.append(reviewer)
            n = sum(1 for r in self.review_calls if r == reviewer)
            yield AgentStreamEvent(event_type=AgentEventType.ANSWER, content=self.verdict_fn(reviewer, n))
            return
        code = meta.get("module_code", "")
        if code in self.primary:
            event = AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED
            yield AgentStreamEvent(event_type=event, content=self.primary[code])
            yield AgentStreamEvent(event_type=AgentEventType.DONE, content="done")
            return
        async for event in super().execute_task(task_id, workspace_dir, system_context, user_instruction,
                                                message_type, metadata):
            yield event


@pytest_asyncio.fixture(autouse=True)
async def setup_collab_env(monkeypatch):
    settings.AGENT_ADAPTER_TYPE = "simulator"
    monkeypatch.setattr(settings, "COLLAB_REVIEW_MODE", "full")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


def _use(monkeypatch, adapter: ReviewScriptAdapter) -> ReviewScriptAdapter:
    monkeypatch.setattr(agent_runner, "get_agent_adapter", lambda adapter_type=None: adapter)
    return adapter


async def _module(db, run_id: str, code: str) -> ModuleInstance:
    return (await db.execute(select(ModuleInstance).where(
        ModuleInstance.run_id == run_id, ModuleInstance.module_code == code
    ).execution_options(populate_existing=True))).scalar_one()


async def _run_at(db, suffix: str, target: str, shadow_mode: bool = False,
                  overrides: Optional[Dict[str, str]] = None):
    """A full-launch run with every stage before `target` baselined from simulator drafts."""
    init = StrategicInitiative(id=f"collab-init-{suffix}", name="协作评审测试")
    prod = Product(id=f"collab-p-{suffix}", initiative_id=init.id, name="协作产品",
                   code=f"COLLAB-{suffix.upper()}", stage="growth", shadow_mode=shadow_mode)
    db.add_all([init, prod])
    await db.commit()
    ensure_test_product_authorization(init.id, prod.code)
    run = await create_workflow_run_from_template(db, prod.id, "full-product-launch", f"Sprint-{suffix}")
    modules = (await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run.id))).scalars().all()
    by_code = {m.module_code: m for m in modules}
    for m in sorted(modules, key=lambda x: x.order_index):
        if m.order_index >= by_code[target].order_index:
            break
        content = (overrides or {}).get(m.module_code) or _sim(m.module_code) or "工序 01 演示稿"
        art = Artifact(module_id=m.id, version=1, title=f"工序 {m.module_code}", content=content,
                       content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(), is_baseline=True)
        db.add(art)
        await db.flush()
        m.baseline_artifact_id = art.id
        m.phase = "baselined"
        m.is_unlocked = True
    by_code[target].is_unlocked = True
    await db.commit()
    return prod, run


async def _gate(db, module_id: str) -> Optional[GateApplication]:
    return (await db.execute(select(GateApplication).where(GateApplication.module_id == module_id)
                             .execution_options(populate_existing=True))).scalars().first()


def _review_evidence(gate: GateApplication) -> Dict[str, Any]:
    return next(e for e in gate.evidence if isinstance(e, dict) and e.get("checker") == "collaboration_review")


# ---------------------------------------------------------------------------
# Deterministic cross-checks
# ---------------------------------------------------------------------------

def _spec(code: str, check: str) -> Dict[str, Any]:
    return next(s for s in collaboration.REVIEW_MATRIX[code] if s.get("check") == check)


def test_fakedoor_budget_check():
    spec = _spec("04", "fakedoor_budget")
    auth = {"financial_budget": {"per_stage_limits": {"04": 400}}}
    assert collaboration.run_check(spec, [_sim("04")], {}, auth)["verdict"] == "approve"
    over = collaboration.run_check(spec, ['```json\n{"test_budget_usd": 900}\n```'], {}, auth)
    assert over["verdict"] == "request_changes" and "超过" in over["findings"][0]
    missing = collaboration.run_check(spec, ["预算 $200"], {}, auth)
    assert missing["verdict"] == "request_changes"


def test_view_and_acceptance_coverage_checks():
    upstream = {"05": _sim("05")}
    assert collaboration.extract_ids("V", "V-01~V-04") == ["V-01", "V-02", "V-03", "V-04"]

    views = _spec("06", "view_coverage")
    assert collaboration.run_check(views, [_sim("06")], upstream, {})["verdict"] == "approve"
    partial = collaboration.run_check(views, ["只覆盖 V-01 与 V-02"], upstream, {})
    assert partial["verdict"] == "request_changes" and "V-03" in partial["findings"][0]

    acs = _spec("07", "acceptance_coverage")
    assert collaboration.run_check(acs, [_sim("07")], upstream, {})["verdict"] == "approve"
    assert collaboration.run_check(acs, ["单测覆盖 AC-01"], upstream, {})["verdict"] == "request_changes"
    assert collaboration.run_check(acs, ["无 AC"], {}, {})["verdict"] == "approve"


def test_ecac_vs_ltv_check():
    spec = _spec("10", "ecac_vs_ltv")
    upstream = {"02": _sim("02")}
    ltv = audit_unit_economics([upstream["02"]])["ltv_180d_usd"]
    assert collaboration.run_check(spec, [_sim("10")], upstream, {})["verdict"] == "approve"
    too_high = f'```json\n{{"ecac_limit_usd": {round(ltv / 3 + 0.5, 2)}}}\n```'
    assert collaboration.run_check(spec, [too_high], upstream, {})["verdict"] == "request_changes"


def test_backlog_evidence_check():
    spec = _spec("11", "backlog_evidence")
    assert collaboration.run_check(spec, [_sim("11")], {}, {})["verdict"] == "approve"
    weak = "| P1 | 加个暗黑模式 | 有用户提了 |"
    assert collaboration.run_check(spec, [weak], {}, {})["verdict"] == "request_changes"


def test_unparseable_verdict_counts_as_request_changes():
    parsed = collaboration.parse_verdict("我觉得挺好的，没有 JSON。")
    assert parsed["verdict"] == "request_changes" and parsed["parse_error"]
    bad = collaboration.parse_verdict('```json\n{"verdict": "approve_gate"}\n```')
    assert bad["verdict"] == "request_changes"
    ok = collaboration.parse_verdict(_verdict("raise_cr", cr_target_stage="05", cr_flags={"is_payment_related": True}))
    assert ok["verdict"] == "raise_cr" and ok["cr_flags"] == {"is_payment_related": True}


def test_handoff_requirements_skip_stages_outside_run():
    missing = collaboration.check_handoff("07", {"05": "没有验收编号", "06": "Design Tokens"}, ["05", "06"])
    assert [m["upstream"] for m in missing] == ["05"]
    assert collaboration.check_handoff("07", {}, ["07", "08", "09"]) == []


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_changes_review_revises_then_passes(monkeypatch):
    adapter = _use(monkeypatch, ReviewScriptAdapter(
        lambda reviewer, n: _verdict("request_changes", ["AC-02 的保存失败分支没写"]) if reviewer == "eng" and n == 1
        else _verdict("approve")
    ))
    async with AsyncSessionLocal() as db:
        _prod, run = await _run_at(db, "revise", "05")
        await orchestrator.advance_run(db, run.id)

        m05 = await _module(db, run.id, "05")
        assert m05.phase == "baselined"
        assert adapter.review_calls[:4] == ["eng", "ux", "eng", "ux"]

        msgs = (await db.execute(select(SessionMessage))).scalars().all()
        revision = [m for m in msgs if (m.metadata_json or {}).get("orchestrator") == "revision"]
        assert revision and "【eng 评审：需修订】" in revision[0].content
        assert any(m.message_type == "review" and m.role_code == "ux" for m in msgs)

        gate = await _gate(db, m05.id)
        assert gate.reviewer_role == "lead"
        ev = _review_evidence(gate)
        assert {r["reviewer"] for r in ev["results"]} == {"eng", "ux"}
        assert all(r["verdict"] == "approve" for r in ev["results"])
        assert "同事复核" in gate.risk_assessment


@pytest.mark.asyncio
async def test_reviews_never_approve_gates(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(lambda reviewer, n: _verdict("approve")))
    async with AsyncSessionLocal() as db:
        _prod, run = await _run_at(db, "noapprove", "05", shadow_mode=True)
        await orchestrator.advance_run(db, run.id)
        m05 = await _module(db, run.id, "05")
        gate = await _gate(db, m05.id)
        assert gate.status == "pending" and m05.phase != "baselined"
        assert gate.reviewed_by is None


@pytest.mark.asyncio
async def test_unresolved_review_becomes_dispute_and_human_overrides(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(
        lambda reviewer, n: _verdict("request_changes", ["推送依赖的后台任务在 iOS 上不可行"]) if reviewer == "eng"
        else _verdict("approve")
    ))
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "dispute", "05")
        await orchestrator.advance_run(db, run.id)
        m05 = await _module(db, run.id, "05")
        assert m05.phase != "baselined" and await _gate(db, m05.id) is None

        risk = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code == "ORCH_DISPUTE_05"
        ))).scalar_one()
        assert not risk.is_resolved and "不可行" in risk.description
        inbox = await get_decision_inbox(db, prod.initiative_id)
        assert any(item["kind"] == "dispute" and item["module_id"] == m05.id for item in inbox["items"])
        status = await orchestrator.get_run_orchestration_status(db, run.id)
        assert status["current_stage"]["state"] == "dispute"

        digest = await generate_project_daily_digest(db, prod.id)
        assert digest["collaboration"]["disputes_pending"] == 1
        assert digest["collaboration"]["dispute_stages"] == ["05"]
        assert any(i["item_type"] == "评审分歧" for i in digest["pending_items"])

        again = await orchestrator.advance_run(db, run.id)
        assert again["processed"] == []
        module_id = m05.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        denied = await ac.post(f"/api/v1/modules/{module_id}/resolve-dispute",
                               json={"decision": "override_review"}, headers={"X-ModuFlow-Actor": "agent:lead"})
        assert denied.status_code == 403
        res = await ac.post(f"/api/v1/modules/{module_id}/resolve-dispute",
                            json={"decision": "override_review", "comment": "后台任务改为本地通知"},
                            headers={"X-ModuFlow-Actor": "human:sponsor"})
        assert res.status_code == 200, res.text
        none_left = await ac.post(f"/api/v1/modules/{module_id}/resolve-dispute",
                                  json={"decision": "override_review"}, headers={"X-ModuFlow-Actor": "human:sponsor"})
        assert none_left.status_code == 409

    async with AsyncSessionLocal() as db:
        m05 = await _module(db, run.id, "05")
        assert m05.phase == "baselined"
        ev = _review_evidence(await _gate(db, m05.id))
        assert ev["overridden_by"] == "human:sponsor" and ev["results"] == []


@pytest.mark.asyncio
async def test_accepting_review_sends_findings_back_to_primary(monkeypatch):
    adapter = _use(monkeypatch, ReviewScriptAdapter(
        lambda reviewer, n: _verdict("request_changes", ["缺 Error 态"]) if reviewer == "ux" and n <= 3
        else _verdict("approve")
    ))
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "accept", "05")
        await orchestrator.advance_run(db, run.id)
        m05 = await _module(db, run.id, "05")
        status = await orchestrator.resolve_dispute(db, m05.id, "accept_review", "human:sponsor")
        assert status == "baselined"
        assert adapter.review_calls.count("ux") == 4

        msgs = (await db.execute(select(SessionMessage).order_by(SessionMessage.created_at))).scalars().all()
        ruling = next(i for i, m in enumerate(msgs) if (m.metadata_json or {}).get("orchestrator") == "dispute_resolution")
        assert any((m.metadata_json or {}).get("orchestrator") == "revision" for m in msgs[ruling:])
        risk = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code == "ORCH_DISPUTE_05"
        ))).scalar_one()
        assert risk.is_resolved


@pytest.mark.asyncio
async def test_high_risk_cr_from_review_escalates_gate_to_red(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(
        lambda reviewer, n: _verdict("raise_cr", ["订阅恢复购买需要改支付流程"], cr_target_stage="05",
                                     cr_flags={"is_payment_related": True}) if reviewer == "eng"
        else _verdict("approve")
    ))
    async with AsyncSessionLocal() as db:
        _prod, run = await _run_at(db, "redcr", "05")
        await orchestrator.advance_run(db, run.id)
        m05 = await _module(db, run.id, "05")
        gate = await _gate(db, m05.id)
        assert gate.effective_level == "red" and gate.status == "pending"
        assert m05.phase != "baselined"

        crs = (await db.execute(select(Issue).where(Issue.category == "requirement_cr"))).scalars().all()
        assert len(crs) == 1 and crs[0].target_module_id == m05.id and crs[0].reporter_role == "eng"
        ev = _review_evidence(gate)
        assert ev["change_requests"][0]["escalated"] is True


@pytest.mark.asyncio
async def test_low_risk_cr_is_carried_over_without_blocking(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(
        lambda reviewer, n: _verdict("raise_cr", ["按钮文案建议更口语"], cr_target_stage="05") if reviewer == "ux"
        else _verdict("approve")
    ))
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "lowcr", "05")
        await orchestrator.advance_run(db, run.id)
        m05 = await _module(db, run.id, "05")
        assert m05.phase == "baselined"
        gate = await _gate(db, m05.id)
        assert gate.effective_level == "green"
        ev = _review_evidence(gate)
        assert ev["change_requests"][0]["escalated"] is False
        assert "另有变更已记下" in gate.risk_assessment
        digest = await generate_project_daily_digest(db, prod.id)
        assert digest["collaboration"]["carried_over_crs"] == 1


@pytest.mark.asyncio
async def test_failed_cross_check_skips_llm_review(monkeypatch):
    adapter = _use(monkeypatch, ReviewScriptAdapter(lambda reviewer, n: _verdict("approve"),
                                                    primary={"07": _sim("07").replace("AC-02", "AC-01")}))
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "skipllm", "07")
        result = await orchestrator.advance_run(db, run.id)
        m07 = await _module(db, run.id, "07")
        assert m07.phase != "baselined"
        assert "07" in result["processed"]
        assert adapter.review_calls == []
        risk = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code == "ORCH_DISPUTE_07"
        ))).scalar_one()
        assert "AC-02" in risk.description


def _approved_gate(module: ModuleInstance, run_id: str, product_code: str) -> GateApplication:
    return GateApplication(
        module_id=module.id, run_id=run_id, product_code=product_code, module_code=module.module_code,
        gate_name="prd_linter", base_level="green", effective_level="red", is_escalated=True,
        escalation_reasons=["payment"], status="approved", recommendation="已确认",
        evidence=[], risk_assessment="测试签字", decision_options=["approve", "reject", "adjust"],
        submitted_by="agent:pm", reviewed_by="human:owner", reviewer_role="human", decision_action="approve",
    )


async def _revision_count(db) -> int:
    msgs = (await db.execute(select(SessionMessage))).scalars().all()
    return sum(1 for m in msgs if (m.metadata_json or {}).get("orchestrator") == "revision")


@pytest.mark.asyncio
async def test_missing_handoff_anchor_is_repaired_and_signature_kept(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(lambda reviewer, n: _verdict("approve")))
    prd_without_ac = _sim("05").replace("AC-01 ", "").replace("AC-02 ", "")
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "handoff", "07", overrides={"05": prd_without_ac})
        m05 = await _module(db, run.id, "05")
        db.add(_approved_gate(m05, run.id, prod.code))
        await db.commit()

        result = await orchestrator.advance_run(db, run.id)
        assert "07" in result["dispatched"]
        m05 = await _module(db, run.id, "05")
        assert m05.phase == "baselined"
        baseline = (await db.execute(select(Artifact).where(Artifact.id == m05.baseline_artifact_id))).scalar_one()
        assert "AC-01" in baseline.content and "AC-02" in baseline.content
        gate = await _gate(db, m05.id)
        assert gate.status == "approved" and gate.reviewer_role == "human" and gate.reviewed_by == "human:owner"

        gaps = (await db.execute(select(Issue).where(Issue.category == "handoff_gap"))).scalars().all()
        assert len(gaps) == 1
        await db.refresh(gaps[0])
        assert gaps[0].status == "closed" and gaps[0].resolution == "fixed"


@pytest.mark.asyncio
async def test_missing_tracking_dictionary_sends_stage05_back(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(lambda reviewer, n: _verdict("approve")))
    prd_without_events = _sim("05").replace("埋点", "事件")
    async with AsyncSessionLocal() as db:
        _prod, run = await _run_at(db, "tracking", "11", overrides={"05": prd_without_events})
        result = await orchestrator.advance_run(db, run.id)
        assert "11" in result["dispatched"]
        m05 = await _module(db, run.id, "05")
        assert m05.phase == "baselined"
        baseline = (await db.execute(select(Artifact).where(Artifact.id == m05.baseline_artifact_id))).scalar_one()
        assert "埋点" in baseline.content
        gaps = (await db.execute(select(Issue).where(Issue.category == "handoff_gap"))).scalars().all()
        assert len(gaps) == 1 and gaps[0].status == "closed"


@pytest.mark.asyncio
async def test_handoff_repair_stops_after_two_failures(monkeypatch):
    _use(monkeypatch, ReviewScriptAdapter(
        lambda reviewer, n: _verdict("approve"),
        primary={"05": "补写后仍然没有验收编号，也没有章节。"},
    ))
    prd_without_ac = _sim("05").replace("AC-01 ", "").replace("AC-02 ", "")
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "handoffstuck", "07", overrides={"05": prd_without_ac})
        result = await orchestrator.advance_run(db, run.id)
        m07 = await _module(db, run.id, "07")
        m05 = await _module(db, run.id, "05")
        assert result["dispatched"] == []
        assert not (await db.execute(select(Artifact).where(Artifact.module_id == m07.id))).scalars().all()
        assert m05.phase == "baselined"
        baseline = (await db.execute(select(Artifact).where(Artifact.id == m05.baseline_artifact_id))).scalar_one()
        assert "AC-01" not in baseline.content
        assert await _revision_count(db) == 2

        risk = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.product_code == prod.code, ExecutiveRisk.rule_code == "ORCH_STUCK_05"
        ))).scalar_one()
        assert "验收编号" in risk.description
        gaps = (await db.execute(select(Issue).where(Issue.category == "handoff_gap"))).scalars().all()
        assert len(gaps) == 1 and gaps[0].status == "open"
        inbox = await get_decision_inbox(db, prod.initiative_id)
        assert any(item["kind"] == "handoff_gap" and item["module_id"] == m07.id for item in inbox["items"])
        status = await orchestrator.get_run_orchestration_status(db, run.id)
        assert status["current_stage"]["state"] == "handoff_incomplete"
        digest = await generate_project_daily_digest(db, prod.id)
        assert digest["collaboration"]["handoff_gaps_open"] == 1

        await orchestrator.advance_run(db, run.id)
        assert await _revision_count(db) == 2
        assert len((await db.execute(select(Issue).where(Issue.category == "handoff_gap"))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_handoff_repair_new_red_flag_keeps_old_signature_pending(monkeypatch):
    patched = _sim("05") + '\n```json\n{"is_payment_related": true}\n```\n'
    _use(monkeypatch, ReviewScriptAdapter(lambda reviewer, n: _verdict("approve"), primary={"05": patched}))
    prd_without_ac = _sim("05").replace("AC-01 ", "").replace("AC-02 ", "")
    async with AsyncSessionLocal() as db:
        prod, run = await _run_at(db, "handoffred", "07", overrides={"05": prd_without_ac})
        m05 = await _module(db, run.id, "05")
        db.add(_approved_gate(m05, run.id, prod.code))
        await db.commit()

        result = await orchestrator.advance_run(db, run.id)
        assert "07" not in result["dispatched"]
        m05 = await _module(db, run.id, "05")
        assert m05.phase != "baselined"
        baseline = (await db.execute(select(Artifact).where(Artifact.id == m05.baseline_artifact_id))).scalar_one()
        assert "AC-01" not in baseline.content
        gate = await _gate(db, m05.id)
        assert gate.status == "pending" and gate.effective_level == "red" and gate.reviewer_role is None

        await orchestrator.advance_run(db, run.id)
        assert await _revision_count(db) == 1
        versions = (await db.execute(select(Artifact).where(Artifact.module_id == m05.id))).scalars().all()
        assert len(versions) == 2


@pytest.mark.asyncio
async def test_downstream_context_carries_handoff_anchors(monkeypatch):
    from backend.app.services.context_assembler import assemble_module_context

    async with AsyncSessionLocal() as db:
        _prod, run = await _run_at(db, "anchors", "07")
        m07 = await _module(db, run.id, "07")
        ctx, _path, meta = await assemble_module_context(db, m07.id, "开工")
        assert "## 上游交接锚点" in ctx and "AC-01" in ctx

        review_ctx, _p, review_meta = await assemble_module_context(db, m07.id, "评审", role_override="qa")
        assert review_meta["role_code"] == "qa"
        assert "协作评审身份" in review_ctx
