import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from pathlib import Path
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
    ExecutiveRisk
)
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template, can_baseline_module
from backend.app.services.agent_roles import seed_agent_roles_if_empty, STAGE_ROLE_CONFIGS, HOTFIX_GATE_CONFIG
from backend.app.services.gate_keeper import (
    get_stage_gate_config,
    evaluate_gate_level,
    create_or_update_gate_application,
    review_gate_application,
    check_stage_gate_passed
)


@pytest_asyncio.fixture(autouse=True)
async def setup_gate_test_env():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


def test_gate_matrix_definitions():
    """Verify all 11 stages and hotfix have correct gate level, approver, and conditions."""
    expected_gates = {
        "01": ("green", "lead", "门禁自检"),
        "02": ("yellow", "human", "LTV/CAC 商业关口"),
        "03": ("yellow", "human", "G1 立项方向"),
        "04": ("yellow", "human", "G2 外测决议"),
        "05": ("green", "lead", "prd_linter 规格门禁"),
        "06": ("green", "lead", "HIG/Material 检测"),
        "07": ("green", "lead", "覆盖率与零推理门禁"),
        "08": ("green", "qa", "G3 质量门"),
        "09": ("red", "human", "G4 提审门禁"),
        "10": ("yellow", "human", "买量预算门禁"),
        "11": ("green", "lead", "Backlog 评审"),
    }

    for code, (lvl, apprv, name) in expected_gates.items():
        cfg = get_stage_gate_config(code)
        assert cfg["level"] == lvl, f"Stage {code} level mismatch: {cfg['level']} != {lvl}"
        assert cfg["approver"] == apprv, f"Stage {code} approver mismatch: {cfg['approver']} != {apprv}"
        assert name in cfg["name"]
        assert len(cfg["conditions"]) >= 1

    # Hotfix gate
    hotfix_cfg = get_stage_gate_config("07", template_id="hotfix")
    assert hotfix_cfg["level"] == "red"
    assert hotfix_cfg["approver"] == "human"


def test_auto_escalation_rules():
    """Verify deterministic auto-escalation rules (Zero LLM)."""
    # 1. Non-sensitive content on green gate (05) stays green
    res_normal = evaluate_gate_level("05", {"feature_name": "夜间模式切换"})
    assert res_normal["effective_level"] == "green"
    assert not res_normal["is_escalated"]

    # 2. Payment trigger -> 🔴 RED
    res_pay = evaluate_gate_level("05", {"content": "新增 24h 通行证与 Stripe IAP 支付通道"})
    assert res_pay["effective_level"] == "red"
    assert res_pay["effective_approver"] == "human"
    assert res_pay["is_escalated"]
    assert any("payment" in r for r in res_pay["escalation_reasons"])

    # 3. Privacy trigger -> 🔴 RED
    res_priv = evaluate_gate_level("03", {"content": "请求收集用户精准位置与通讯录好友列表"})
    assert res_priv["effective_level"] == "red"
    assert res_priv["is_escalated"]

    # 4. Encryption trigger -> 🔴 RED
    res_enc = evaluate_gate_level("07", {"content": "物理存储采用 Keychain AES-256 加密"})
    assert res_enc["effective_level"] == "red"
    assert res_enc["is_escalated"]

    # 5. Budget exceeded trigger -> 🔴 RED
    res_bgt = evaluate_gate_level("10", {"is_budget_exceeded": True})
    assert res_bgt["effective_level"] == "red"
    assert res_bgt["is_escalated"]

    # 6. Stage 05 data dictionary / schema change -> 🔴 RED
    res_schema = evaluate_gate_level("05", {"data_dictionary_schema_change": True})
    assert res_schema["effective_level"] == "red"
    assert res_schema["is_escalated"]

    # 7. Stage 11 major version -> 🟡 YELLOW
    res_v11 = evaluate_gate_level("11", {"is_major_version": True})
    assert res_v11["effective_level"] == "yellow"
    assert res_v11["is_escalated"]


@pytest.mark.asyncio
async def test_one_page_gate_application_creation_and_red_notification():
    """Verify creating 1-page gate application, disk logging in decisions/, and instant 🔴 alert."""
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id="gate-init-1", name="关口测试工程")
        prod = Product(id="gate-p1", initiative_id=init.id, name="关口产品", code="G-PROD", stage="growth")
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization("gate-init-1", "G-PROD")

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", "Sprint-1")
        m_res = await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "05"))
        m05 = m_res.scalar_one()

        # Submit application for 05 with payment keyword -> auto escalated to 🔴 RED
        gate = await create_or_update_gate_application(
            db=db,
            module_id=m05.id,
            recommendation="建议批准 PRD 封版，涵盖订阅特权体系",
            evidence=["PRD Linter 100/100", "8 项 Gherkin 验收用例通过"],
            risk_assessment="涉及苹果 IAP 扣款回调，需在工序 07 研发实现双向对账",
            submitted_by="agent:lead",
            context={"content": "涉及支付和 IAP 结算流程"}
        )

        assert gate.effective_level == "red"
        assert gate.is_escalated
        assert gate.status == "pending"

        # Check ExecutiveRisk was created with severity='critical' (🔴 instant notification)
        r_stmt = select(ExecutiveRisk).where(ExecutiveRisk.product_code == "G-PROD")
        r_res = await db.execute(r_stmt)
        risks = r_res.scalars().all()
        assert len(risks) >= 1
        assert risks[0].severity == "critical"
        assert "红级关口待批" in risks[0].title

        # Check physical file in decisions/
        dec_file = Path(settings.WORKSPACE_DIR) / "gate-init-1" / "products" / "G-PROD" / "decisions"
        assert dec_file.exists()
        app_files = list(dec_file.glob("*_gate_05_application.json"))
        assert len(app_files) >= 1
        content = json.loads(app_files[0].read_text(encoding="utf-8"))
        assert content["effective_level"] == "red"
        assert "涉及支付" in content["recommendation"] or len(content["escalation_reasons"]) > 0


@pytest.mark.asyncio
async def test_negative_agent_cannot_approve_yellow_or_red_gate():
    """Verify that Agent (including lead) is STRICTLY FORBIDDEN from approving Yellow or Red gates."""
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id="gate-init-2", name="关口测试工程2")
        prod = Product(id="gate-p2", initiative_id=init.id, name="关口产品2", code="G-PROD2", stage="growth")
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization("gate-init-2", "G-PROD2")

        run = await create_workflow_run_from_template(db, prod.id, "full-product-launch", "Sprint-1")
        m_res = await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "03"))
        m03 = m_res.scalar_one() # G1 立项方向 (Yellow)

        # Create application for G1
        gate = await create_or_update_gate_application(
            db=db,
            module_id=m03.id,
            recommendation="核心卖点验证通过，建议立项开工",
            evidence=["UVP 一页纸确定", "MoSCoW 斩立决伪需求"],
            risk_assessment="获客成本可能受市场投放波动影响",
            submitted_by="agent:pm"
        )
        assert gate.effective_level == "yellow"

        # 1. Lead agent attempts to approve -> REJECTED WITH PermissionError
        with pytest.raises(PermissionError) as exc_info:
            await review_gate_application(
                db=db,
                gate_id=gate.id,
                action="approve",
                comment="Lead Agent 自批 G1 立项",
                actor="agent:lead",
                actor_role="lead"
            )
        assert "严禁 Agent (包括 lead) 审批黄级/红级关口" in str(exc_info.value)

        # 2. PM agent attempts to approve -> REJECTED
        with pytest.raises(PermissionError) as exc_info2:
            await review_gate_application(
                db=db,
                gate_id=gate.id,
                action="approve",
                comment="PM Agent 尝试自批",
                actor="agent:pm",
                actor_role="agent"
            )
        assert "必须由人类负责人" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_human_can_approve_yellow_and_red_gate():
    """Verify that human authorizer can approve Yellow/Red gate and unblock stage."""
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id="gate-init-3", name="关口测试工程3")
        prod = Product(id="gate-p3", initiative_id=init.id, name="关口产品3", code="G-PROD3", stage="growth")
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization("gate-init-3", "G-PROD3")

        run = await create_workflow_run_from_template(db, prod.id, "full-product-launch", "Sprint-1")
        m_res = await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "02"))
        m02 = m_res.scalar_one() # LTV/CAC (Yellow)

        gate = await create_or_update_gate_application(
            db=db,
            module_id=m02.id,
            recommendation="LTV/CAC 达标 3.8x，单位经济健康",
            evidence=["测算 LTV=45 USD, CAC=11.6 USD", "回本周期 4.2 个月"],
            risk_assessment="注意广告网络扣量风险",
            submitted_by="agent:ba"
        )

        # Human approves
        updated_gate = await review_gate_application(
            db=db,
            gate_id=gate.id,
            action="approve",
            comment="财务模型审定无误，准予进入工序03",
            actor="human:alex_sponsor",
            actor_role="human"
        )
        assert updated_gate.status == "approved"
        assert updated_gate.reviewed_by == "human:alex_sponsor"
        assert updated_gate.reviewer_role == "human"

        # Check gate passed
        passed, reason, _ = await check_stage_gate_passed(db, m02.id)
        assert passed
        assert "批准通过" in reason


@pytest.mark.asyncio
async def test_negative_stage_09_blocked_without_human_approval():
    """Verify that Stage 09 (Release/G4) CANNOT baseline without recorded human approval."""
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id="gate-init-4", name="提审关口测试")
        prod = Product(id="gate-p4", initiative_id=init.id, name="提审产品", code="G-PROD4", stage="growth")
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization("gate-init-4", "G-PROD4")

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", "Sprint-Release")
        m_res = await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "09"))
        m09 = m_res.scalar_one()

        # 1. No gate application exists -> strictly blocked
        can_b, reason = await can_baseline_module(db, m09.id)
        assert not can_b
        assert "工序 09 (发布上线) 缺少人类确认记录" in reason

        # 2. Gate application exists but pending -> strictly blocked
        gate = await create_or_update_gate_application(
            db=db,
            module_id=m09.id,
            recommendation="合规表无红灯，申请发布 v1.0",
            evidence=["Apple 4.3 查重通过", "Remote Config 降级开关已就绪"],
            risk_assessment="首发新版本可能存在偶发 Crash，已准备回滚包",
            submitted_by="agent:qa"
        )
        can_b2, reason2 = await can_baseline_module(db, m09.id)
        assert not can_b2
        assert "尚未获批" in reason2

        # 3. Human approves -> gate passed
        await review_gate_application(
            db=db,
            gate_id=gate.id,
            action="approve",
            comment="已亲自核查隐私政策与降级开关，确认放行提审",
            actor="human:vp_product",
            actor_role="human"
        )
        passed, gate_reason, _ = await check_stage_gate_passed(db, m09.id)
        assert passed
        assert "人类提审确认记录具备" in gate_reason


@pytest.mark.asyncio
async def test_api_gate_application_and_review_lifecycle():
    """Test full API RESTful endpoints: submit application, pending-batch list, review with header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create initiative & product
        init_res = await client.post("/api/v1/initiatives", json={
            "name": "关口 API 全链路测试",
            "owner": "Founder",
            "budget": 100000.0
        })
        init_id = init_res.json()["id"]

        prod_res = await client.post("/api/v1/products", json={
            "name": "GateAPIApp",
            "code": "G-API",
            "initiative_id": init_id,
            "auto_authorize": True
        })
        prod_id = prod_res.json()["id"]

        run_res = await client.post("/api/v1/runs", json={
            "product_id": prod_id,
            "template_id": "fast-iteration",
            "name": "Iteration-1"
        })
        run_data = run_res.json()
        m05 = next(m for m in run_data["modules"] if m["module_code"] == "05")

        # 1. Get gate config
        cfg_res = await client.get(f"/api/v1/modules/{m05['id']}/gate-config")
        assert cfg_res.status_code == 200
        assert cfg_res.json()["name"] == "prd_linter 规格门禁"
        assert cfg_res.json()["level"] == "green"

        # 2. Submit application with payment -> auto escalated to RED
        app_res = await client.post(
            f"/api/v1/modules/{m05['id']}/gate-application",
            headers={"X-ModuFlow-Actor": "agent:lead"},
            json={
                "recommendation": "建议 PRD 基线定稿",
                "evidence": ["PRD 满分", "UI 画板契约对齐"],
                "risk_assessment": "涉及海外支付手续费",
                "decision_options": ["approve", "reject", "adjust"],
                "context": {"is_payment_related": True}
            }
        )
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data["effective_level"] == "red"
        assert app_data["is_escalated"]
        gate_id = app_data["id"]

        # 3. Check pending batch list includes this gate
        batch_res = await client.get("/api/v1/gates/pending-batch?level=red")
        assert batch_res.status_code == 200
        pending_list = batch_res.json()
        assert any(g["id"] == gate_id for g in pending_list)

        # 4. Agent attempts to review red gate -> 403 Forbidden
        bad_rev = await client.post(
            f"/api/v1/gates/{gate_id}/review",
            headers={"X-ModuFlow-Actor": "agent:lead"},
            json={
                "action": "approve",
                "comment": "Agent 强行审批"
            }
        )
        assert bad_rev.status_code == 403
        assert "严禁 Agent (包括 lead) 审批黄级/红级关口" in bad_rev.json()["detail"]

        # 5. Human reviews red gate -> 200 OK
        good_rev = await client.post(
            f"/api/v1/gates/{gate_id}/review",
            headers={"X-ModuFlow-Actor": "human:sponsor_tom"},
            json={
                "action": "approve",
                "comment": "支付方案已通过法务与财务双重评估，准予定稿"
            }
        )
        assert good_rev.status_code == 200
        assert good_rev.json()["status"] == "approved"
        assert good_rev.json()["reviewed_by"] == "human:sponsor_tom"

        # 6. Check module details contains gate and gate_application
        mod_res = await client.get(f"/api/v1/modules/{m05['id']}")
        assert mod_res.status_code == 200
        mod_data = mod_res.json()
        assert mod_data["gate"] is not None
        assert mod_data["gate_application"]["status"] == "approved"


@pytest.mark.asyncio
async def test_gate_rejection_and_adjustment_flow():
    """Verify that reject and adjust actions properly update state and prevent premature baselining."""
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id="gate-init-5", name="打回与调整测试")
        prod = Product(id="gate-p5", initiative_id=init.id, name="打回产品", code="G-PROD5", stage="growth")
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization("gate-init-5", "G-PROD5")

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", "Sprint-Reject")
        m_res = await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "05"))
        m05 = m_res.scalar_one()

        gate = await create_or_update_gate_application(
            db=db,
            module_id=m05.id,
            recommendation="申请基线定稿",
            evidence=["测试证据"],
            risk_assessment="风险说明",
            submitted_by="agent:lead"
        )

        # 1. Human requests adjustment
        adj_gate = await review_gate_application(
            db=db,
            gate_id=gate.id,
            action="adjust",
            comment="请补充离线缓存降级用例",
            actor="human:lead_reviewer",
            actor_role="human"
        )
        assert adj_gate.status == "needs_adjustment"

        passed, reason, _ = await check_stage_gate_passed(db, m05.id)
        assert not passed
        assert "已被要求调整修改" in reason

        # 2. Resubmit application
        gate2 = await create_or_update_gate_application(
            db=db,
            module_id=m05.id,
            recommendation="已补齐离线缓存降级用例，重新申请定稿",
            evidence=["离线用例已补充"],
            risk_assessment="无残留风险",
            submitted_by="agent:lead"
        )
        assert gate2.status == "pending"

        # 3. Human rejects
        rej_gate = await review_gate_application(
            db=db,
            gate_id=gate2.id,
            action="reject",
            comment="技术架构重大缺陷，完全打回",
            actor="human:lead_reviewer",
            actor_role="human"
        )
        assert rej_gate.status == "rejected"

        passed2, reason2, _ = await check_stage_gate_passed(db, m05.id)
        assert not passed2
        assert "已被驳回" in reason2
