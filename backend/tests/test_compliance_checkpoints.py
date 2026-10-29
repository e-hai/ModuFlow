"""
Phase 5 Tests: Compliance Specialist (cmp) Checkpoints & G5 Auto-Escalation
(backend/tests/test_compliance_checkpoints.py)

Covers:
1. cmp role registration and attachment to stages 03, 05, and 09.
2. Stage 03 checkpoint: privacy & permission screening, regional payment & tax hints, IP/gambling infringement.
3. Stage 05 checkpoint: PRD sensitive data security, dark patterns avoidance, ATT tracking prompts.
4. Stage 09 checkpoint: Apple 4.3 / 5.1 privacy URL check, Remote Config kill switch, emergency rollback plan.
5. High-risk compliance findings auto-escalate gate to 🔴 G5 (human approval mandatory) and generate ExecutiveRisk.
6. Strict redline: All outputs must include mandatory legal disclaimer stating that agent cannot produce binding legal conclusions.
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
    Artifact,
    GateApplication,
    ExecutiveRisk
)
from backend.app.services.agent_roles import (
    DEFAULT_AGENT_ROLES,
    STAGE_ROLE_CONFIGS,
    migrate_db_for_roles,
    seed_agent_roles_if_empty
)
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.gate_keeper import create_or_update_gate_application
from backend.app.services.compliance_engine import (
    LEGAL_DISCLAIMER,
    audit_stage_compliance,
    run_stage_compliance_check
)


@pytest_asyncio.fixture(autouse=True)
async def setup_compliance_test_env():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await migrate_db_for_roles(db)
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


def test_cmp_role_initialization_and_redlines():
    """Verify cmp role exists and is attached to stages 03, 05, 09 with strict legal disclaimers."""
    cmp_role = next((r for r in DEFAULT_AGENT_ROLES if r["role_code"] == "cmp"), None)
    assert cmp_role is not None
    assert cmp_role["name"] == "合规风控 Agent"
    assert cmp_role["title"] == "全球法务政策与合规风控专家 (Compliance Specialist)"

    persona = cmp_role["system_persona"]
    assert "工序 03" in persona
    assert "工序 05" in persona
    assert "工序 09" in persona
    assert "严禁替代专业律师出具法律保证" in persona
    assert "G5 关口" in persona

    # Check that stages 03, 05, and 09 include cmp in collaborators
    assert "cmp" in STAGE_ROLE_CONFIGS["03"]["collaborators"]
    assert "cmp" in STAGE_ROLE_CONFIGS["05"]["collaborators"]
    assert "cmp" in STAGE_ROLE_CONFIGS["09"]["collaborators"]


def test_stage_03_compliance_audit():
    """Stage 03: Screen permissions, regional tax hints, and gambling/infringement risks."""
    # 1. Sensitive permission -> needs_fix
    content_perm = "本产品核心亮点：实时向附近好友广播精确地理位置与后台定位，并同步通讯录联系人。"
    res_perm = audit_stage_compliance("03", content_perm, target_market="美国")
    assert res_perm["status"] == "needs_fix"
    assert res_perm["risk_level"] == "medium"
    assert any("地理位置" in f["item"] for f in res_perm["findings"])
    assert any("COPPA" in hint for hint in res_perm["regional_tax_hints"])

    # 2. Regional tax hints for Europe
    res_eu = audit_stage_compliance("03", "常规工具应用，零高危权限", target_market="欧洲出海")
    assert any("DAC7" in hint for hint in res_eu["regional_tax_hints"])
    assert any("VAT" in hint for hint in res_eu["regional_tax_hints"])

    # 3. Blatant gambling / illegal profit claims -> High risk G5 escalation!
    content_gamble = "打造 100%返现的线上海外 casino 博彩对战平台，稳赚不赔。"
    res_gamble = audit_stage_compliance("03", content_gamble, target_market="美国")
    assert res_gamble["status"] == "legal_review"
    assert res_gamble["risk_level"] == "high"
    assert res_gamble["is_g5_escalated"] is True
    assert "G5" in res_gamble["summary"]


def test_stage_05_prd_compliance_audit():
    """Stage 05: PRD sensitive data security, dark patterns, and ATT rules."""
    # 1. Plaintext password in PRD data dictionary -> High risk G5!
    content_plaintext = "5.3 数据存储：本地 SQLite 表 user_account，包含字段 password VARCHAR 明文保存。"
    res_plain = audit_stage_compliance("05", content_plaintext)
    assert res_plain["status"] == "legal_review"
    assert res_plain["risk_level"] == "high"
    assert res_plain["is_g5_escalated"] is True

    # 2. Subscription PRD missing cancellation/refund guidance -> needs_fix
    content_dark = "设计 VIP 自动续费订阅，每周扣费 $9.99，点击继续即刻扣费。"
    res_dark = audit_stage_compliance("05", content_dark)
    assert res_dark["status"] == "needs_fix"
    assert any("暗黑模式" in f["item"] for f in res_dark["findings"])

    # 3. Clean PRD with Keychain encryption and cancellation terms -> passed
    content_clean = (
        "5.3 数据存储：用户凭证使用 iOS Keychain 加密存储。\n"
        "商业化说明：用户可随时在设置中取消自动续费，提供明确退款通道。"
    )
    res_clean = audit_stage_compliance("05", content_clean)
    assert res_clean["status"] == "passed"
    assert res_clean["risk_level"] == "low"
    assert res_clean["is_g5_escalated"] is False


def test_stage_05_tracking_requirements_pass_when_the_prd_is_complete():
    content = """
    iOS 使用 IDFA 做广告追踪。NSUserTrackingUsageDescription 的 ATT 授权弹窗文案已定义；
    用户选择 Ask App not to Track / denied 后，归因降级为 SKAdNetwork，核心功能保持可用。
    Android 声明 com.google.android.gms.permission.AD_ID 权限；目标受众年龄为 13 岁及以上，
    遵守家庭政策。用户停用个性化广告（OPTED_OUT）后降级为非个性化归因。
    """
    result = audit_stage_compliance("05", content, platform="cross_platform")
    assert result["status"] == "passed"
    assert all(f["passed"] for f in result["findings"])


def test_stage_09_submission_compliance_audit():
    """Stage 09: Apple 4.3 spam, Privacy policy URL, Remote Config & Rollback plan."""
    # 1. Missing privacy policy URL -> High risk G5!
    content_no_privacy = "提审清单：包含应用截图与 ASO 关键词，包含提审降级开关 Remote Config，回滚预案具备。"
    res_no_priv = audit_stage_compliance("09", content_no_privacy)
    assert res_no_priv["status"] == "legal_review"
    assert res_no_priv["risk_level"] == "high"
    assert res_no_priv["is_g5_escalated"] is True
    assert any("隐私协议" in f["item"] for f in res_no_priv["findings"])

    # 2. Missing Remote Config degradation switch -> needs_fix
    content_no_rc = "提审清单：包含隐私政策链接 https://example.com/privacy，未配置 Remote Config 降级开关。"
    res_no_rc = audit_stage_compliance("09", content_no_rc)
    assert res_no_rc["status"] == "needs_fix"
    assert any("提审降级保护开关" in f["item"] for f in res_no_rc["findings"])

    # 3. Fully compliant stage 09 deliverable -> passed
    content_compliant = (
        "【提审合规表】\n"
        "- 隐私协议有效 URL: https://moduflow.ai/privacy_policy\n"
        "- Remote Config 提审降级开关已接入并配置默认值\n"
        "- 快速回滚预案与应急联系人已就绪\n"
        "- Apple 4.3 查重度排查通过，具备独特价值主张"
    )
    res_comp = audit_stage_compliance("09", content_compliant)
    assert res_comp["status"] == "passed"
    assert res_comp["risk_level"] == "low"
    assert res_comp["is_g5_escalated"] is False


@pytest.mark.asyncio
async def test_api_compliance_audit_and_g5_escalation():
    """
    API test: Triggering compliance audit on a high-risk PRD module:
    - Automatically upgrades GateApplication to 🔴 RED G5.
    - Emits ExecutiveRisk with severity='critical'.
    - Logs audit into decisions/.
    """
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-CMP-{uid}"
    prod_code = f"CMP_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="合规测试工程", target_market="欧盟")
        prod = Product(
            id=f"p-{uid}",
            initiative_id=init.id,
            name="CmpApp",
            code=prod_code,
            stage="growth"
        )
        db.add_all([init, prod])
        await db.commit()
        ensure_test_product_authorization(init.id, prod.code)

        run = await create_workflow_run_from_template(db, prod.id, "fast-iteration", f"Run-{uid}")
        m_res = await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "05")
        )
        m05 = m_res.scalar_one()

        # Gate application starts at Green
        gate = await create_or_update_gate_application(
            db=db,
            module_id=m05.id,
            recommendation="PRD 待审计",
            evidence=["测试用例已写"],
            risk_assessment="待合规审查",
            submitted_by="agent:pm",
            context={}
        )
        assert gate.effective_level == "green"
        gate_id = gate.id

        # Create high-risk PRD artifact with plaintext password
        art = Artifact(
            module_id=m05.id,
            title="交付物_05_高危PRD.md",
            version=1,
            artifact_type="markdown",
            content="# PRD\n5.3 数据库字段：password VARCHAR 明文存储。",
            content_hash="hash-123",
            is_baseline=False
        )
        db.add(art)
        await db.commit()
        module_id = m05.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Run compliance audit via API
        resp = await ac.post(f"/api/v1/modules/{module_id}/compliance-audit")
        assert resp.status_code == 200
        result = resp.json()

        assert result["status"] == "legal_review"
        assert result["risk_level"] == "high"
        assert result["is_g5_escalated"] is True
        assert "【免责声明】" in result["legal_disclaimer"]

    # Verify that GateApplication was auto-escalated to 🔴 RED
    async with AsyncSessionLocal() as db:
        updated_gate = await db.get(GateApplication, gate_id)
        assert updated_gate.effective_level == "red"
        assert updated_gate.is_escalated is True
        assert "compliance_high_risk" in updated_gate.escalation_reasons

        # Verify ExecutiveRisk emitted
        risk_stmt = select(ExecutiveRisk).where(
            ExecutiveRisk.initiative_id == init_id,
            ExecutiveRisk.rule_code == "COMPLIANCE_G5_05"
        )
        risk_res = await db.execute(risk_stmt)
        risks = risk_res.scalars().all()
        assert len(risks) >= 1
        assert risks[0].severity == "critical"

        # Verify audit file in decisions/
        decisions_dir = Path(settings.WORKSPACE_DIR) / init_id / "products" / prod_code / "decisions"
        assert decisions_dir.exists()
        audit_files = list(decisions_dir.glob("*_compliance_audit_stage_05.json"))
        assert len(audit_files) >= 1


def test_mandatory_legal_disclaimer_present():
    """Verify that every compliance audit includes the mandatory legal disclaimer."""
    res = audit_stage_compliance("03", "常规正常内容")
    assert "legal_disclaimer" in res
    assert "不构成任何具有法律效力的正式法律意见" in res["legal_disclaimer"]
    assert "高风险问题必须由签约法务顾问或执业律师出具" in res["legal_disclaimer"]
