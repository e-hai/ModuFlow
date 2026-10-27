"""
Phase 4 Tests: Lead Agent & Shadow Mode Consistency Tracking
(backend/tests/test_lead_shadow_mode.py)

Covers:
1. Lead role initialization, responsibilities, and hard redlines.
2. Shadow mode active: Lead evaluates gate -> produces recommendation, but DOES NOT approve gate (status remains pending).
3. Human review synchronization: consistency tracking (lead_recommendation vs human_decision).
4. Divergence tracking: when human decision differs from lead recommendation, is_consistent=False and consistency rate drops.
5. Protection: Agent (including lead) attempting to toggle shadow mode -> 403 Forbidden.
6. Human authority: Human toggles shadow mode off -> autonomous mode allows lead to self-approve green gates.
7. Lead CR arbitration: low-risk CR arbitrated vs sensitive CR (payment/privacy) auto-escalated to human.
8. 1-Page Lead Daily Progress Digest generation.
"""

import json
import uuid
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.main import app
from backend.tests.conftest import test_engine as engine, TestingSessionLocal as AsyncSessionLocal, ensure_test_product_authorization
from backend.app.core.database import Base
from backend.app.core.config import settings
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowRun,
    ModuleInstance,
    GateApplication,
    LeadShadowDecision,
    Issue
)
from backend.app.services.agent_roles import DEFAULT_AGENT_ROLES, STAGE_ROLE_CONFIGS, migrate_db_for_roles, seed_agent_roles_if_empty
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.gate_keeper import create_or_update_gate_application, review_gate_application
from backend.app.services.lead_service import (
    evaluate_gate_by_lead,
    get_shadow_mode_stats,
    toggle_product_shadow_mode,
    arbitrate_cr_by_lead,
    generate_project_daily_digest
)


@pytest_asyncio.fixture(autouse=True)
async def setup_lead_test_env():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await migrate_db_for_roles(db)
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


def test_lead_role_initialization_and_redlines():
    """Verify Lead Agent role exists and defines strict redlines and shadow mode rules."""
    lead_role = next((r for r in DEFAULT_AGENT_ROLES if r["role_code"] == "lead"), None)
    assert lead_role is not None
    assert lead_role["name"] == "项目总控 Agent"
    assert lead_role["title"] == "项目总负责人 (Project Lead)"

    persona = lead_role["system_persona"]
    # Check redlines
    assert "严禁通过 G1/G2/G4/G5" in persona
    assert "严禁修改自身权限" in persona
    assert "严禁批准任何涉及支付、隐私" in persona
    assert "严禁触发未经人类授权的生产热修复" in persona
    assert "严禁批准预算增加" in persona
    assert "严禁提交应用商店提审" in persona
    assert "影子模式 (Shadow Mode)" in persona
    assert "所有决策留痕" in persona


@pytest.mark.asyncio
async def test_shadow_mode_active_lead_does_not_approve_gate():
    """Under Shadow Mode (default True), lead only recommends approval, gate remains pending."""
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-SHADOW-{uid}"
    prod_code = f"SHADOW_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="影子模式工程")
        prod = Product(
            id=f"p-{uid}",
            initiative_id=init.id,
            name="ShadowApp",
            code=prod_code,
            stage="growth",
            shadow_mode=True
        )
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization(init.id, prod.code)

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", f"Run-{uid}")
        m_res = await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "05")
        )
        m05 = m_res.scalar_one()

        gate = await create_or_update_gate_application(
            db=db,
            module_id=m05.id,
            recommendation="建议批准 PRD 规格封版",
            evidence=["prd_linter 100/100", "8 项用例通过"],
            risk_assessment="常规业务逻辑，无外部 API 风险",
            submitted_by="agent:pm",
            context={"content": "纯业务功能规格"}
        )
        gate_id = gate.id

    async with AsyncSessionLocal() as db:
        # Lead evaluates the gate
        eval_gate, shadow_dec = await evaluate_gate_by_lead(db, gate_id, lead_actor="agent:lead")

        # Crucial check: Gate status must STILL be pending because shadow_mode is True!
        assert eval_gate.status == "pending"
        assert eval_gate.lead_recommendation == "approved"
        assert "预评估" in eval_gate.lead_rationale

        assert shadow_dec.lead_recommendation == "approved"
        assert shadow_dec.human_decision is None
        assert shadow_dec.is_consistent is None

        # Verify audit file in decisions/
        decisions_dir = Path(settings.WORKSPACE_DIR) / init_id / "products" / prod_code / "decisions"
        assert decisions_dir.exists()
        eval_files = list(decisions_dir.glob("*_lead_gate_evaluation.json"))
        assert len(eval_files) >= 1


@pytest.mark.asyncio
async def test_shadow_mode_consistency_tracking():
    """Verify human approval matches lead recommendation -> is_consistent=True & consistency_rate=1.0."""
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-CONSIST-{uid}"
    prod_code = f"CONSIST_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="一致率测试工程")
        prod = Product(
            id=f"p-{uid}",
            initiative_id=init.id,
            name="ConsistApp",
            code=prod_code,
            stage="growth",
            shadow_mode=True
        )
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization(init.id, prod.code)

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", f"Run-{uid}")
        m_res = await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "05")
        )
        m05 = m_res.scalar_one()

        gate = await create_or_update_gate_application(
            db=db,
            module_id=m05.id,
            recommendation="PRD 封版",
            evidence=["测试用例全部绿灯"],
            risk_assessment="无高危风险",
            submitted_by="agent:pm",
            context={}
        )
        gate_id = gate.id

        # 1. Lead evaluates gate -> recommends 'approved'
        await evaluate_gate_by_lead(db, gate_id, lead_actor="agent:lead")

        # 2. Human reviews and approves -> action='approve'
        reviewed_gate = await review_gate_application(
            db=db,
            gate_id=gate_id,
            action="approve",
            comment="同意 Lead 评估，准予放行",
            actor="human:sponsor_dan",
            actor_role="human"
        )
        assert reviewed_gate.status == "approved"
        assert reviewed_gate.is_consistent is True

        # 3. Check consistency stats
        stats = await get_shadow_mode_stats(db, prod.id)
        assert stats["total_evaluated"] == 1
        assert stats["consistent_count"] == 1
        assert stats["divergent_count"] == 0
        assert stats["consistency_rate"] == 1.0
        assert stats["consistency_percentage"] == "100.0%"


@pytest.mark.asyncio
async def test_shadow_mode_divergence_tracking():
    """Verify when human disagrees with lead recommendation, is_consistent=False and consistency drops."""
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-DIV-{uid}"
    prod_code = f"DIV_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="分歧测试工程")
        prod = Product(
            id=f"p-{uid}",
            initiative_id=init.id,
            name="DivApp",
            code=prod_code,
            stage="growth",
            shadow_mode=True
        )
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization(init.id, prod.code)

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", f"Run-{uid}")
        m05_res = await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "05")
        )
        m05 = m05_res.scalar_one()
        m06_res = await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "06")
        )
        m06 = m06_res.scalar_one()

        # Gate 1: Both approve -> Consistent
        g1 = await create_or_update_gate_application(
            db=db, module_id=m05.id, recommendation="PRD 1", evidence=["OK"], risk_assessment="Low", submitted_by="agent:pm", context={}
        )
        await evaluate_gate_by_lead(db, g1.id)
        await review_gate_application(db, g1.id, "approve", "Approved by human", "human:alice", "human")

        # Gate 2: Lead recommends approved, but Human rejects -> Divergent!
        g2 = await create_or_update_gate_application(
            db=db, module_id=m06.id, recommendation="Design 1", evidence=["OK"], risk_assessment="Low", submitted_by="agent:ux", context={}
        )
        await evaluate_gate_by_lead(db, g2.id)
        reviewed_g2 = await review_gate_application(
            db=db,
            gate_id=g2.id,
            action="reject",
            comment="人类复核发现竞品数据存在假数据，打回重测",
            actor="human:alice",
            actor_role="human"
        )
        assert reviewed_g2.status == "rejected"
        assert reviewed_g2.is_consistent is False

        # Stats check: 1 consistent, 1 divergent -> 50%
        stats = await get_shadow_mode_stats(db, prod.id)
        assert stats["total_evaluated"] == 2
        assert stats["consistent_count"] == 1
        assert stats["divergent_count"] == 1
        assert stats["consistency_rate"] == 0.5
        assert stats["consistency_percentage"] == "50.0%"


@pytest.mark.asyncio
async def test_negative_agent_cannot_toggle_shadow_mode():
    """Agent (including lead) attempting to disable shadow mode must be rejected with 403."""
    uid = uuid.uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        prod = Product(
            name="ShadowProtect",
            code=f"SPROT_{uid}",
            stage="growth",
            shadow_mode=True
        )
        db.add(prod)
        await db.commit()
        await db.refresh(prod)
        prod_id = prod.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Agent tries to disable shadow mode -> 403 Forbidden
        agent_resp = await ac.post(
            f"/api/v1/products/{prod_id}/lead/shadow-mode",
            json={"enabled": False},
            headers={"X-ModuFlow-Actor": "agent:lead"}
        )
        assert agent_resp.status_code == 403
        assert "只有人类负责人" in agent_resp.json()["detail"]

    # Verify shadow_mode remains True in database
    async with AsyncSessionLocal() as db:
        check_prod = await db.get(Product, prod_id)
        assert check_prod.shadow_mode is True


@pytest.mark.asyncio
async def test_human_can_toggle_shadow_mode_and_enable_autonomous_lead():
    """Human toggles shadow mode off -> lead can self-approve green gates autonomously."""
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-AUTON-{uid}"
    prod_code = f"AUTON_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="自主放行测试工程")
        prod = Product(
            id=f"p-{uid}",
            initiative_id=init.id,
            name="AutonApp",
            code=prod_code,
            stage="growth",
            shadow_mode=True
        )
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization(init.id, prod.code)
        prod_id = prod.id

        run = await create_workflow_run_from_template(db, prod.id, "full-product-launch", f"Run-{uid}")
        m_res = await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "01")
        )
        m01 = m_res.scalar_one()

        gate = await create_or_update_gate_application(
            db=db,
            module_id=m01.id,
            recommendation="工序 01 门禁自检放行",
            evidence=["SOM 测算 $1.2M", "干建议明确"],
            risk_assessment="风险受控",
            submitted_by="agent:mr",
            context={}
        )
        gate_id = gate.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Human turns off shadow mode -> 200 OK
        human_resp = await ac.post(
            f"/api/v1/products/{prod_id}/lead/shadow-mode",
            json={"enabled": False},
            headers={"X-ModuFlow-Actor": "human:sponsor_dan"}
        )
        assert human_resp.status_code == 200
        assert human_resp.json()["shadow_mode"] is False

    # 2. In autonomous mode (shadow_mode=False), lead can self-approve the green gate
    async with AsyncSessionLocal() as db:
        eval_gate, shadow_dec = await evaluate_gate_by_lead(db, gate_id, lead_actor="agent:lead")
        assert eval_gate.status == "approved"
        assert eval_gate.reviewed_by == "agent:lead"
        assert eval_gate.reviewer_role == "lead"
        assert "自主放行" in eval_gate.review_comment


@pytest.mark.asyncio
async def test_lead_cr_arbitration():
    """Lead arbitrates low-risk CR vs auto-escalates sensitive CR (payment/privacy)."""
    async with AsyncSessionLocal() as db:
        # 1. Low risk CR: UI spacing & copy
        low_risk_issue = Issue(
            id=f"CR-{uuid.uuid4().hex[:6]}",
            title="优化深色模式卡片边距与引导文案",
            source_module_id="mod-1",
            target_module_id="mod-2",
            reporter="ux",
            category="requirement_cr",
            priority="P2",
            description={"summary": "边距调整为 16pt，文案微调"}
        )
        # 2. High risk CR: Payment channel addition
        high_risk_issue = Issue(
            id=f"CR-{uuid.uuid4().hex[:6]}",
            title="接入 Stripe IAP 支付回调与订阅扣款通道",
            source_module_id="mod-1",
            target_module_id="mod-2",
            reporter="eng",
            category="requirement_cr",
            priority="P1",
            description={"summary": "新增支付订阅和扣费 Webhook"}
        )
        db.add_all([low_risk_issue, high_risk_issue])
        await db.commit()

        # Low risk arbitration
        low_res = await arbitrate_cr_by_lead(db, low_risk_issue.id)
        assert low_res["is_escalated"] is False
        assert low_res["lead_recommendation"] == "accept_cr_revision"

        # High risk arbitration -> auto escalated to human!
        high_res = await arbitrate_cr_by_lead(db, high_risk_issue.id)
        assert high_res["is_escalated"] is True
        assert high_res["lead_recommendation"] == "escalate_to_human"
        assert "支付" in high_res["escalation_reason"]


@pytest.mark.asyncio
async def test_project_daily_digest_generation():
    """Verify 1-page Lead Daily Progress Digest generation via API."""
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-DIGEST-{uid}"
    prod_code = f"DIGEST_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="日报测试工程")
        prod = Product(
            id=f"p-{uid}",
            initiative_id=init.id,
            name="DigestApp",
            code=prod_code,
            stage="growth",
            budget_allocated=10000.0,
            actual_spent=2500.0,
            shadow_mode=True
        )
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization(init.id, prod.code, 10000.0)
        prod_id = prod.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/products/{prod_id}/lead/daily-digest")
        assert resp.status_code == 200
        digest = resp.json()

        assert digest["product_name"] == "DigestApp"
        assert digest["product_code"] == prod_code
        assert digest["shadow_mode_active"] is True
        assert digest["financial_summary"]["actual_spent"] == 2500.0
        assert digest["financial_summary"]["burn_rate"] == "25.0%"
        assert "shadow_consistency" in digest
        assert "lead_dispatch_recommendation" in digest
