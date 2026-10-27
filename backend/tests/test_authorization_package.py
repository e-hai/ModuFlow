import os
import json
import yaml
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.tests.conftest import test_engine as engine, TestingSessionLocal as AsyncSessionLocal
from backend.app.core.database import Base
from backend.app.core.config import settings
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowRun,
    ModuleInstance,
    ExecutiveRisk
)
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.services.authorization_engine import (
    load_product_authorization,
    validate_authorization_file,
    validate_authorization_dict,
    check_budget_limits,
    check_time_limits,
    check_kill_criteria,
    check_lead_forbidden_action,
    execute_circuit_breaker,
    get_product_authorization_path,
    MANDATORY_LEAD_FORBIDDEN
)
from scripts.validate_authorization import validate_authorization
from scripts.migrate_legacy_project_auth import (
    generate_default_authorization_dict,
    migrate_workspace_products
)
from sqlalchemy import select


@pytest_asyncio.fixture(autouse=True)
async def setup_auth_test_env():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


def get_valid_auth_payload(code="AUTH-TEST", budget=5000.0) -> dict:
    return generate_default_authorization_dict(
        product_code=code,
        product_name=f"Project {code}",
        budget_allocated=budget,
        platform="ios"
    )


def test_schema_and_canonical_example_validation():
    """Verify that docs/examples/authorization.example.yaml passes schema & rule checks."""
    example_path = settings.BASE_DIR / "docs" / "examples" / "authorization.example.yaml"
    assert example_path.exists(), f"Example file missing: {example_path}"
    is_valid, errors, data = validate_authorization(example_path)
    assert is_valid, f"Canonical example failed validation: {errors}"
    assert data["project_id"] == "WN-PAGER"
    assert data["financial_budget"]["total_budget_limit"] == 5000.0


def test_negative_invalid_schema_rejected():
    """Verify that invalid schema structures (missing required fields, bad types) are rejected."""
    payload = get_valid_auth_payload()
    del payload["owner"] # Missing required field

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml.dump(payload))
        tmp_path = Path(tmp.name)

    try:
        is_valid, errors, _ = validate_authorization(tmp_path)
        assert not is_valid
        assert any("owner" in e for e in errors)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_negative_missing_mandatory_lead_forbidden_rejected():
    """Verify that omitting ANY of the 8 mandatory lead_forbidden items is strictly rejected."""
    payload = get_valid_auth_payload()
    # Remove mandatory item: submit_store_review and modify_permissions
    payload["lead_forbidden"] = [
        "approve_g1_g2_g4_g5",
        "modify_redlines",
        "modify_budget"
    ]

    is_valid, errors = validate_authorization_dict(payload)
    assert not is_valid
    assert any("Missing mandatory lead_forbidden items" in e for e in errors)
    assert any("submit_store_review" in e for e in errors)
    assert any("modify_permissions" in e for e in errors)


def test_negative_hard_stop_lower_than_total_budget_rejected():
    """Verify that hard_stop_limit < total_budget_limit is rejected."""
    payload = get_valid_auth_payload()
    payload["financial_budget"]["total_budget_limit"] = 10000.0
    payload["financial_budget"]["hard_stop_limit"] = 5000.0

    is_valid, errors = validate_authorization_dict(payload)
    assert not is_valid
    assert any("cannot be lower than total_budget_limit" in e for e in errors)


def test_negative_deadline_before_start_date_rejected():
    """Verify that deadline before start_date is rejected."""
    payload = get_valid_auth_payload()
    payload["time_budget"]["start_date"] = "2026-12-31"
    payload["time_budget"]["deadline"] = "2026-01-01"

    is_valid, errors = validate_authorization_dict(payload)
    assert not is_valid
    assert any("cannot be before start_date" in e for e in errors)


def test_deterministic_budget_check_logic():
    """Verify pure Python deterministic budget checking (zero LLM)."""
    payload = get_valid_auth_payload(budget=5000.0)
    payload["financial_budget"]["hard_stop_limit"] = 5500.0
    payload["financial_budget"]["per_stage_limits"] = {"01": 250.0, "04": 350.0}

    # 1. Under budget
    breached, reason, is_hard = check_budget_limits(payload, actual_spent=4200.0)
    assert not breached
    assert reason is None

    # 2. Exceeded total budget limit (soft breach)
    breached, reason, is_hard = check_budget_limits(payload, actual_spent=5200.0)
    assert breached
    assert not is_hard
    assert "exceeded total budget limit" in reason

    # 3. Reached hard stop limit (hard circuit-break)
    breached, reason, is_hard = check_budget_limits(payload, actual_spent=5500.0)
    assert breached
    assert is_hard
    assert "hard stop limit" in reason

    # 4. Stage budget limit check
    breached, reason, _ = check_budget_limits(payload, actual_spent=1000.0, stage_code="01", stage_spent=300.0)
    assert breached
    assert "Stage 01 spent (300.00) exceeded stage limit (250.00)" in reason


def test_deterministic_time_limit_logic():
    """Verify pure Python deterministic time limit checking (zero LLM)."""
    payload = get_valid_auth_payload()
    payload["time_budget"]["start_date"] = "2026-01-01"
    payload["time_budget"]["deadline"] = "2026-06-30"
    payload["time_budget"]["max_duration_days"] = 60

    # Past deadline
    now_past = datetime(2026, 7, 15, tzinfo=timezone.utc)
    expired, reason = check_time_limits(payload, current_time=now_past)
    assert expired
    assert "deadline" in reason

    # Duration exceeded
    now_duration_exceeded = datetime(2026, 3, 15, tzinfo=timezone.utc)
    expired, reason = check_time_limits(payload, current_time=now_duration_exceeded)
    assert expired
    assert "max allowed duration" in reason

    # Within limits
    now_ok = datetime(2026, 1, 20, tzinfo=timezone.utc)
    expired, reason = check_time_limits(payload, current_time=now_ok)
    assert not expired
    assert reason is None


def test_deterministic_kill_criteria_logic():
    """Verify stop-loss evaluation against kill_criteria without LLM."""
    payload = get_valid_auth_payload()
    payload["kill_criteria"] = [
        {"id": "KC-01", "metric": "ltv_cac_ratio", "operator": "<", "threshold": 3.0, "action": "pause_and_escalate", "description": "LTV/CAC < 3.0"},
        {"id": "KC-02", "metric": "cac", "operator": ">", "threshold": 2.5, "action": "pause_and_escalate", "description": "CAC > 2.5"},
        {"id": "KC-03", "metric": "d1_retention", "operator": "<=", "threshold": 0.20, "action": "pause_and_escalate", "description": "D1 Retention <= 20%"}
    ]

    # Safe metrics
    safe_metrics = {"ltv_cac_ratio": 3.5, "cac": 1.8, "d1_retention": 0.35}
    triggered = check_kill_criteria(payload, safe_metrics)
    assert len(triggered) == 0

    # LTV/CAC breach
    breach_metrics = {"ltv_cac_ratio": 2.4, "cac": 1.8, "d1_retention": 0.35}
    triggered = check_kill_criteria(payload, breach_metrics)
    assert len(triggered) == 1
    assert triggered[0]["id"] == "KC-01"

    # Multi-metric breach
    double_breach = {"ltv_cac_ratio": 2.1, "cac": 3.2, "d1_retention": 0.15}
    triggered = check_kill_criteria(payload, double_breach)
    assert len(triggered) == 3


def test_lead_forbidden_action_interception():
    """Verify that lead forbidden actions are blocked deterministically."""
    payload = get_valid_auth_payload()
    for forbidden in MANDATORY_LEAD_FORBIDDEN:
        is_forbidden, reason = check_lead_forbidden_action(payload, forbidden)
        assert is_forbidden
        assert "strictly forbidden" in reason

    # Allowed normal action
    is_forbidden, reason = check_lead_forbidden_action(payload, "generate_daily_standup_report")
    assert not is_forbidden
    assert reason is None


@pytest.mark.asyncio
async def test_circuit_breaker_execution_flow():
    """Verify that execute_circuit_breaker pauses product, writes decisions/ log, and logs 🔴 risk."""
    init_id = "test-cb-init"
    prod_code = "CB-PROD"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(id=init_id, name="熔断测试工程")
        prod = Product(
            id="cb-p1",
            initiative_id=init_id,
            name="熔断测试产品",
            code=prod_code,
            stage="growth",
            budget_allocated=5000.0,
            actual_spent=5600.0
        )
        db.add_all([init, prod])
        await db.commit()

        # Execute circuit breaker
        event = await execute_circuit_breaker(
            initiative_id=init_id,
            product_code=prod_code,
            trigger_type="budget_exceeded",
            details={"reason": "Actual spent exceeded hard stop ceiling (5500.0)", "actual_spent": 5600.0},
            db=db
        )

        assert event["action_taken"] == "paused"
        assert event["escalation_level"] == "red"

        # Verify DB product stage is 'paused'
        p_res = await db.execute(select(Product).where(Product.code == prod_code))
        updated_prod = p_res.scalar_one()
        assert updated_prod.stage == "paused"
        assert "熔断触发" in updated_prod.key_risk

        # Verify ExecutiveRisk record created with severity='critical'
        r_res = await db.execute(select(ExecutiveRisk).where(ExecutiveRisk.product_code == prod_code))
        risk = r_res.scalar_one()
        assert risk.severity == "critical"
        assert risk.rule_code == "CIRCUIT_BREAKER_BUDGET_EXCEEDED"

        # Verify physical file written in decisions/
        decisions_dir = settings.WORKSPACE_DIR / init_id / "products" / prod_code / "decisions"
        assert decisions_dir.exists()
        decision_files = list(decisions_dir.glob("*_budget_exceeded.json"))
        assert len(decision_files) >= 1
        saved_data = json.loads(decision_files[0].read_text(encoding="utf-8"))
        assert saved_data["action_taken"] == "paused"


@pytest.mark.asyncio
async def test_api_product_creation_and_authorization_lifecycle():
    """Verify API POST /products with/without authorization, PUT /authorization, and PATCH metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create initiative
        init_res = await client.post("/api/v1/initiatives", json={
            "name": "北美出海矩阵",
            "owner": "Founder",
            "budget": 200000.0
        })
        init_id = init_res.json()["id"]

        # 2. Create product with invalid authorization -> 422 rejected
        bad_auth = get_valid_auth_payload("BAD-PROD")
        bad_auth["lead_forbidden"] = [] # Missing mandatory items
        res_bad = await client.post("/api/v1/products", json={
            "name": "Bad Product",
            "code": "BAD-PROD",
            "initiative_id": init_id,
            "authorization_package": bad_auth
        })
        assert res_bad.status_code == 422
        assert "非法授权包被拒" in res_bad.json()["detail"]["message"]

        # 3. Create product without authorization -> created with 'needs_authorization'
        res_unauth = await client.post("/api/v1/products", json={
            "name": "Unauth Product",
            "code": "UNAUTH-PROD",
            "initiative_id": init_id
        })
        assert res_unauth.status_code == 200
        unauth_data = res_unauth.json()
        assert unauth_data["authorization_status"] == "needs_authorization"

        # 4. Create workflow run for unauth product
        run_res = await client.post("/api/v1/runs", json={
            "product_id": unauth_data["id"],
            "template_id": "full-product-launch",
            "name": "V1.0"
        })
        assert run_res.status_code == 200
        m01 = next(m for m in run_res.json()["modules"] if m["module_code"] == "01")

        # 5. Attempt to chat/execute on Stage 01 without authorization -> rejected with guidance
        sess_res = await client.get(f"/api/v1/modules/{m01['id']}/session")
        sess_id = sess_res.json()["id"]
        post_msg = await client.post(
            f"/api/v1/sessions/{sess_id}/messages?trigger_agent=true",
            json={
                "sender": "Alice",
                "sender_role": "human",
                "message_type": "instruction",
                "content": "开始工序01调研"
            }
        )
        assert post_msg.status_code == 200
        msgs = post_msg.json()
        assert len(msgs) == 2
        assert msgs[1]["message_type"] == "error"
        assert "尚未配置合规授权包" in msgs[1]["content"]

        # 6. Upload valid authorization via PUT endpoint
        valid_auth = get_valid_auth_payload("UNAUTH-PROD", budget=6000.0)
        put_auth = await client.put(
            f"/api/v1/initiatives/{init_id}/products/UNAUTH-PROD/authorization",
            json=valid_auth
        )
        assert put_auth.status_code == 200
        assert put_auth.json()["authorization_status"] == "authorized"

        # 7. Check authorization endpoint
        get_auth = await client.get(f"/api/v1/initiatives/{init_id}/products/UNAUTH-PROD/authorization")
        assert get_auth.status_code == 200
        assert get_auth.json()["authorization_status"] == "authorized"

        # 8. Now Stage 01 message works!
        post_msg_after = await client.post(
            f"/api/v1/sessions/{sess_id}/messages?trigger_agent=true",
            json={
                "sender": "Alice",
                "sender_role": "human",
                "message_type": "instruction",
                "content": "现在开始市场调研"
            }
        )
        assert post_msg_after.status_code == 200
        msgs_after = post_msg_after.json()
        assert len(msgs_after) == 2
        assert msgs_after[1]["message_type"] != "error"

        # 9. Update metrics via PATCH /products: exceed budget -> triggers circuit breaker
        patch_res = await client.patch(
            f"/api/v1/products/{unauth_data['id']}",
            json={"actual_spent": 7000.0}
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["authorization_status"] == "paused"
        assert patch_res.json()["stage"] == "paused"


def test_legacy_workspace_migration():
    """Verify that migrate_legacy_project_auth.py migrates legacy unconfigured projects."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_workspaces = Path(tmp_dir)
        p_dir = tmp_workspaces / "legacy-init" / "products" / "LEGACY-P1"
        p_dir.mkdir(parents=True, exist_ok=True)

        # 1. Dry run
        dry_results = migrate_workspace_products(tmp_workspaces, dry_run=True)
        assert len(dry_results) == 1
        assert dry_results[0]["status"] == "needs_migration"

        # 2. Actual migration
        real_results = migrate_workspace_products(tmp_workspaces, dry_run=False)
        assert len(real_results) == 1
        assert real_results[0]["status"] == "migrated_created"

        # 3. Check created authorization.yaml is fully valid
        auth_file = p_dir / "authorization.yaml"
        assert auth_file.exists()
        is_valid, errors, data = validate_authorization(auth_file)
        assert is_valid, f"Migrated package was invalid: {errors}"
        assert data["project_id"] == "LEGACY-P1"
        assert data["financial_budget"]["total_budget_limit"] == 5000.0
