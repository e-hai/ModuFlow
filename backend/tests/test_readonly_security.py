"""
Phase 3 Tests: Permissions, Read-Only Protection & Credential Isolation
(backend/tests/test_readonly_security.py)

Covers:
1. Physical OS-level read-only protection (`0o444`) on protected files.
2. System-protected path detection (authorization, AGENTS.md, platform, decisions).
3. Interception of Agent write attempts with decision audit logs and critical ExecutiveRisk alerts.
4. API-level enforcement: Agent (including lead) attempting to modify authorization package -> 403 Forbidden.
5. API-level enforcement: Agent attempting to increase or modify budget allocated -> 403 Forbidden.
6. Single source of pricing truth: only 'ba' or 'human' can modify pricing/revenue forecasts.
7. Environment credential sanitization: store credentials, Stripe live keys, and prod DB secrets stripped before reaching Agent subprocess.
"""

import os
import stat
import json
import uuid
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.main import app
from backend.tests.conftest import TestingSessionLocal as AsyncSessionLocal
from backend.app.core.config import settings
from backend.app.models.entities import Product, StrategicInitiative, ExecutiveRisk
from backend.app.services.security_guard import (
    apply_readonly_file_protection,
    apply_write_file_permission,
    is_protected_path,
    intercept_agent_write_attempt,
    sanitize_agent_environment,
    validate_pricing_authority
)
from backend.app.services.authorization_engine import get_product_authorization_path
from scripts.migrate_legacy_project_auth import generate_default_authorization_dict


def test_os_level_readonly_file_protection(tmp_path: Path):
    """Test OS-level read-only enforcement (0o444) and write unlocking."""
    test_file = tmp_path / "test_auth.yaml"
    test_file.write_text("initial: content", encoding="utf-8")

    # Lock file to 0o444
    apply_readonly_file_protection(test_file)
    mode = stat.S_IMODE(test_file.stat().st_mode)
    assert mode == 0o444

    # Direct write should be blocked by OS
    with pytest.raises((PermissionError, OSError)):
        with open(test_file, "w") as f:
            f.write("tampered: content")

    # Unlock file for human modification
    apply_write_file_permission(test_file)
    mode = stat.S_IMODE(test_file.stat().st_mode)
    assert mode in [0o644, 0o664]

    with open(test_file, "w") as f:
        f.write("updated: content")
    assert test_file.read_text(encoding="utf-8") == "updated: content"

    # Re-lock
    apply_readonly_file_protection(test_file)
    mode = stat.S_IMODE(test_file.stat().st_mode)
    assert mode == 0o444


def test_protected_path_detection():
    """Verify that is_protected_path accurately identifies system-critical paths."""
    # System critical files
    assert is_protected_path("data/workspaces/INIT-001/products/QPAY/authorization.yaml") is True
    assert is_protected_path("authorization.json") is True
    assert is_protected_path("/Users/dev/ModuFlow/AGENTS.md") is True
    assert is_protected_path("backend/app/services/agent_roles.py") is True

    # System critical directories
    assert is_protected_path("data/workspaces/INIT-001/products/QPAY/decisions/audit.json") is True
    assert is_protected_path("/workspace/platform/ios_hig.md") is True
    assert is_protected_path("data/workspaces/INIT-001/.agents/skills/mr/SKILL.md") is True

    # Unprotected normal deliverables & working files
    assert is_protected_path("data/workspaces/INIT-001/products/QPAY/run/01/交付物_01_市场研究.md") is False
    assert is_protected_path("data/workspaces/INIT-001/products/QPAY/run/06/index.html") is False
    assert is_protected_path("data/workspaces/INIT-001/products/QPAY/run/07/main.py") is False


@pytest.mark.asyncio
async def test_agent_write_attempt_interception_and_audit():
    """
    Verify application-level write interceptor blocks agent attempts,
    logs security violation in decisions/, and records ExecutiveRisk.
    """
    async with AsyncSessionLocal() as db:
        init_id = "INIT-SEC-01"
        prod_code = "SEC_APP"
        target_path = Path(settings.WORKSPACE_DIR) / init_id / "products" / prod_code / "authorization.yaml"

        # 1. Agent write attempt should be intercepted
        is_blocked, err_msg = await intercept_agent_write_attempt(
            file_path=target_path,
            actor="lead_agent_v1",
            actor_role="lead",
            db=db,
            initiative_id=init_id,
            product_code=prod_code
        )
        assert is_blocked is True
        assert "权限拒绝" in err_msg
        assert "lead_agent_v1" in err_msg

        # 2. Verify audit file was written in decisions/
        decisions_dir = Path(settings.WORKSPACE_DIR) / init_id / "products" / prod_code / "decisions"
        assert decisions_dir.exists()
        audit_files = list(decisions_dir.glob("*_security_violation_unauthorized_write.json"))
        assert len(audit_files) >= 1
        audit_data = json.loads(audit_files[0].read_text(encoding="utf-8"))
        assert audit_data["event"] == "SECURITY_VIOLATION_UNAUTHORIZED_WRITE"
        assert audit_data["actor"] == "lead_agent_v1"
        assert audit_data["action"] == "BLOCKED"

        # 3. Verify ExecutiveRisk created in database
        risk_stmt = select(ExecutiveRisk).where(
            ExecutiveRisk.initiative_id == init_id,
            ExecutiveRisk.rule_code == "SECURITY_VIOLATION_UNAUTHORIZED_WRITE"
        )
        risk_res = await db.execute(risk_stmt)
        risks = risk_res.scalars().all()
        assert len(risks) >= 1
        assert risks[0].severity == "critical"

        # 4. Human write attempt should NOT be intercepted
        is_blocked_human, err_msg_human = await intercept_agent_write_attempt(
            file_path=target_path,
            actor="human_admin",
            actor_role="human",
            db=db,
            initiative_id=init_id,
            product_code=prod_code
        )
        assert is_blocked_human is False
        assert err_msg_human is None


def test_credential_sanitization():
    """Verify that forbidden credentials are completely stripped from agent environment."""
    dirty_env = {
        "PATH": "/usr/local/bin:/bin",
        "HOME": "/Users/moduflow",
        "MODUFLOW_WORKSPACE": "/tmp/workspace",
        "APPLE_ID": "developer@moduflow.ai",
        "APPLE_APP_SPECIFIC_PASSWORD": "secret-apple-password",
        "APP_STORE_CONNECT_API_KEY": "p8-private-key-content",
        "FASTLANE_PASSWORD": "fastlane-secret",
        "STRIPE_SECRET_KEY": "sk_live_51Ny8...",
        "STRIPE_LIVE_KEY": "pk_live_...",
        "DATABASE_URL": "postgresql://root:secret@prod-db.internal:5432/moduflow",
        "PROD_DB_PASSWORD": "supersecretpassword",
        "DATABASE_PASSWORD": "dbpass"
    }

    sanitized = sanitize_agent_environment(dirty_env)

    # All forbidden secrets must be stripped
    assert "APPLE_ID" not in sanitized
    assert "APPLE_APP_SPECIFIC_PASSWORD" not in sanitized
    assert "APP_STORE_CONNECT_API_KEY" not in sanitized
    assert "FASTLANE_PASSWORD" not in sanitized
    assert "STRIPE_SECRET_KEY" not in sanitized
    assert "STRIPE_LIVE_KEY" not in sanitized
    assert "DATABASE_URL" not in sanitized
    assert "PROD_DB_PASSWORD" not in sanitized
    assert "DATABASE_PASSWORD" not in sanitized

    # Safe environment variables must be preserved
    assert sanitized["PATH"] == "/usr/local/bin:/bin"
    assert sanitized["HOME"] == "/Users/moduflow"
    assert sanitized["MODUFLOW_WORKSPACE"] == "/tmp/workspace"


def test_pricing_authority_enforcement():
    """Enforce that commercial analyst (ba) is the sole source of pricing truth."""
    # Non-ba roles must be rejected
    is_ok, msg = validate_pricing_authority("pm")
    assert is_ok is False
    assert "唯一来源" in msg

    is_ok, msg = validate_pricing_authority("mkt")
    assert is_ok is False

    is_ok, msg = validate_pricing_authority("eng")
    assert is_ok is False

    # ba and human must be permitted
    is_ok, msg = validate_pricing_authority("ba")
    assert is_ok is True
    assert msg is None

    is_ok, msg = validate_pricing_authority("human")
    assert is_ok is True
    assert msg is None


@pytest.mark.asyncio
async def test_negative_agent_cannot_update_authorization_via_api():
    """API-level test: An agent attempting PUT /authorization must be rejected with 403."""
    uid = uuid.uuid4().hex[:6]
    init_id = f"INIT-AUTH-{uid}"
    prod_code = f"AGUARD_{uid}"

    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(
            id=init_id,
            name="权限测试战略",
            target_market="美国",
            strategic_intent="测试Agent防篡改"
        )
        db.add(init)
        await db.flush()

        prod = Product(
            name="AuthGuard",
            code=prod_code,
            initiative_id=init.id,
            budget_allocated=3000.0,
            stage="validating"
        )
        db.add(prod)
        await db.commit()

        # Pre-create valid authorization file
        from backend.tests.conftest import ensure_test_product_authorization
        ensure_test_product_authorization(init.id, prod.code, 3000.0)

    auth_dict = generate_default_authorization_dict(prod_code, "AuthGuard", 8000.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Agent attempts to overwrite authorization -> 403 Forbidden
        agent_resp = await ac.put(
            f"/api/v1/initiatives/{init.id}/products/{prod_code}/authorization",
            json=auth_dict,
            headers={"X-ModuFlow-Actor": "agent:lead"}
        )
        assert agent_resp.status_code == 403
        assert "权限拒绝" in agent_resp.json()["detail"]

        # 2. Human updates authorization -> 200 OK
        human_resp = await ac.put(
            f"/api/v1/initiatives/{init.id}/products/{prod_code}/authorization",
            json=auth_dict,
            headers={"X-ModuFlow-Actor": "human:sponsor_dan"}
        )
        assert human_resp.status_code == 200
        assert human_resp.json()["ok"] is True
        assert human_resp.json()["authorization_package"]["financial_budget"]["total_budget_limit"] == 8000.0


@pytest.mark.asyncio
async def test_negative_agent_cannot_modify_product_budget():
    """API-level test: An agent attempting to modify budget_allocated via PATCH /products must be rejected with 403."""
    uid = uuid.uuid4().hex[:6]
    prod_code = f"BGUARD_{uid}"

    async with AsyncSessionLocal() as db:
        prod = Product(
            name="BudgetGuard",
            code=prod_code,
            budget_allocated=2000.0,
            stage="validating"
        )
        db.add(prod)
        await db.commit()
        await db.refresh(prod)
        prod_id = prod.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Agent attempts to increase budget -> 403 Forbidden
        agent_resp = await ac.patch(
            f"/api/v1/products/{prod_id}",
            json={"budget_allocated": 10000.0},
            headers={"X-ModuFlow-Actor": "agent:lead"}
        )
        assert agent_resp.status_code == 403
        assert "严禁修改项目预算上限" in agent_resp.json()["detail"]

        # 2. Human modifies budget -> 200 OK
        human_resp = await ac.patch(
            f"/api/v1/products/{prod_id}",
            json={"budget_allocated": 4000.0},
            headers={"X-ModuFlow-Actor": "human:sponsor_bob"}
        )
        assert human_resp.status_code == 200
        assert human_resp.json()["budget_allocated"] == 4000.0


@pytest.mark.asyncio
async def test_pricing_authority_via_api():
    """API-level test: Only 'ba' or 'human' can modify financial forecasts."""
    uid = uuid.uuid4().hex[:6]
    prod_code = f"PGUARD_{uid}"

    async with AsyncSessionLocal() as db:
        prod = Product(
            name="PricingGuard",
            code=prod_code,
            budget_allocated=2000.0,
            revenue_contribution=100.0,
            stage="validating"
        )
        db.add(prod)
        await db.commit()
        await db.refresh(prod)
        prod_id = prod.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. PM agent attempts to update revenue -> 403 Forbidden
        pm_resp = await ac.patch(
            f"/api/v1/products/{prod_id}",
            json={"revenue_contribution": 5000.0},
            headers={"X-ModuFlow-Actor": "agent:pm"}
        )
        assert pm_resp.status_code == 403
        assert "商业分析师 (ba) 是产品定价与单位经济的唯一来源" in pm_resp.json()["detail"]

        # 2. BA agent updates revenue -> 200 OK
        ba_resp = await ac.patch(
            f"/api/v1/products/{prod_id}",
            json={"revenue_contribution": 5000.0},
            headers={"X-ModuFlow-Actor": "agent:ba"}
        )
        assert ba_resp.status_code == 200
        assert ba_resp.json()["revenue_contribution"] == 5000.0
