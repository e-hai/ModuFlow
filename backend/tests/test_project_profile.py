"""
ModuFlow Phase 6: Project Profile & Parameterized Redlines Tests
(backend/tests/test_project_profile.py)

Validates:
1. Profile resolution from authorization package, Product entity, and default fallback.
2. iOS HIG check (check_hig): Dynamic Island (>=71pt), touch target (>=44pt).
3. Android Material check (check_material): status bar cutout (>=24~48dp), touch target (>=48dp).
4. Critical negative constraint: Android project does NOT trigger iOS-specific HIG checks or Apple 4.3.
5. Parameterized client zero inference:
   - client_zero_inference=True: AI calls > 0 strictly fails.
   - client_zero_inference=False: AI calls > 0 passes (edge AI permitted).
6. Skill and MCP mounting customization by platform and zero inference profile.
7. Compliance audit adaptation (Stage 05 AD_ID vs ATT, Stage 09 Google Play vs Apple 4.3).
8. REST API endpoints for profile, design audit, and zero-inference audit.
"""

import os
import uuid
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from sqlalchemy import select, text
from backend.app.core.database import AsyncSessionLocal, Base, engine
from backend.app.main import app
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowTemplate,
    WorkflowRun,
    ModuleInstance,
    Artifact
)
from backend.app.services.agent_roles import (
    DEFAULT_AGENT_ROLES,
    STAGE_ROLE_CONFIGS,
    migrate_db_for_roles,
    seed_agent_roles_if_empty,
    get_stage_gate_conditions
)
from backend.app.services.profile_guard import (
    resolve_project_profile,
    check_hig,
    check_material,
    audit_platform_design_system,
    audit_client_zero_inference
)
from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp
from backend.app.services.compliance_engine import audit_stage_compliance
from scripts.migrate_legacy_project_auth import generate_default_authorization_dict


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await migrate_db_for_roles(db)
        await seed_agent_roles_if_empty(db)
    yield


def test_profile_resolution_from_auth_and_product(tmp_path):
    """Test resolving project profile across multiple precedence levels."""
    # 1. From direct auth dict
    auth_android = {
        "profile": {
            "platform": "android",
            "client_zero_inference": False
        }
    }
    p1 = resolve_project_profile(auth_data=auth_android)
    assert p1["platform"] == "android"
    assert p1["client_zero_inference"] is False

    # 2. From fallback defaults
    p2 = resolve_project_profile()
    assert p2["platform"] == "ios"
    assert p2["client_zero_inference"] is True

    # 3. From custom fallback
    p3 = resolve_project_profile(fallback_platform="cross_platform", fallback_zero_inference=False)
    assert p3["platform"] == "cross_platform"
    assert p3["client_zero_inference"] is False


def test_ios_hig_check_positive_and_negative():
    """Verify iOS HIG ruleset: Dynamic Island >=71pt, touch >=44pt."""
    # Positive case: 74pt top, 44pt touch
    res_pos = check_hig(top_pt=74, touch_pt=44)
    assert res_pos["passed"] is True
    assert res_pos["platform"] == "ios"
    assert len(res_pos["errors"]) == 0

    # Negative case: top_pt = 60pt (below 71pt Dynamic Island requirement)
    res_neg_island = check_hig(top_pt=60, touch_pt=44)
    assert res_neg_island["passed"] is False
    assert any("71pt" in err for err in res_neg_island["errors"])

    # Negative case: touch_pt = 36pt (below 44pt touch target)
    res_neg_touch = check_hig(top_pt=74, touch_pt=36)
    assert res_neg_touch["passed"] is False
    assert any("44×44pt" in err for err in res_neg_touch["errors"])


def test_android_material_check_positive_and_negative():
    """Verify Android Material 3 ruleset: cutout safe area >=24~48dp, touch >=48dp."""
    # Positive case: 48dp cutout, 48dp touch
    res_pos = check_material(status_bar_dp=48, touch_dp=48)
    assert res_pos["passed"] is True
    assert res_pos["platform"] == "android"
    assert res_pos["material_version"] == "Material 3"
    assert len(res_pos["errors"]) == 0

    # Negative case: touch_dp = 40dp (below 48dp Material 3 standard)
    res_neg_touch = check_material(status_bar_dp=48, touch_dp=40)
    assert res_neg_touch["passed"] is False
    assert any("48×48dp" in err for err in res_neg_touch["errors"])

    # Negative case: status_bar_dp = 16dp (below 24dp minimal cutout avoidance)
    res_neg_bar = check_material(status_bar_dp=16, touch_dp=48)
    assert res_neg_bar["passed"] is False
    assert any("24dp" in err for err in res_neg_bar["errors"])


def test_android_project_does_not_trigger_ios_checks():
    """
    CRITICAL ACCEPTANCE TEST:
    An Android design with top padding of 48dp and touch of 48dp must PASS Material check,
    and must NEVER fail on iOS Dynamic Island (>=71pt) or Apple HIG.
    """
    # 48dp is less than iOS 71pt, but perfectly valid for Android Material 3
    res_android = audit_platform_design_system(
        platform="android",
        top_safe_value=48,
        min_touch_value=48
    )
    assert res_android["passed"] is True
    assert res_android["platform"] == "android"
    assert "iOS" not in res_android["ruleset"]
    assert "Dynamic Island" not in str(res_android)

    # However, for iOS, 48pt top padding MUST fail Dynamic Island check
    res_ios = audit_platform_design_system(
        platform="ios",
        top_safe_value=48,
        min_touch_value=44
    )
    assert res_ios["passed"] is False
    assert res_ios["platform"] == "ios"
    assert any("71pt" in err for err in res_ios["errors"])


def test_client_zero_inference_strict_vs_edge_ai_permitted():
    """Verify client zero inference parameterization."""
    # Strict mode (client_zero_inference = True)
    # 0 calls -> Pass
    res_strict_pass = audit_client_zero_inference(
        client_realtime_ai_calls=0,
        enforce_zero_inference=True
    )
    assert res_strict_pass["passed"] is True
    assert res_strict_pass["zero_client_ai_compliant"] is True

    # 2 calls -> Fail
    res_strict_fail = audit_client_zero_inference(
        client_realtime_ai_calls=2,
        enforce_zero_inference=True
    )
    assert res_strict_fail["passed"] is False
    assert res_strict_fail["zero_client_ai_compliant"] is False
    assert any("零推理红线" in err for err in res_strict_fail["errors"])

    # Permitted mode (client_zero_inference = False)
    # 2 calls -> Pass!
    res_edge_pass = audit_client_zero_inference(
        client_realtime_ai_calls=2,
        enforce_zero_inference=False
    )
    assert res_edge_pass["passed"] is True
    assert res_edge_pass["zero_client_ai_compliant"] is True
    assert res_edge_pass["edge_ai_permitted"] is True
    assert len(res_edge_pass["errors"]) == 0


def test_skill_and_mcp_mounting_by_platform_and_profile(tmp_path):
    """Verify mount_role_skills_and_mcp mounts platform-specific scripts."""
    # 1. Android workspace
    ws_android = tmp_path / "ws_android"
    info_android = mount_role_skills_and_mcp(
        workspace_dir=ws_android,
        primary_role_code="ux",
        platform="android"
    )
    ux_scripts_android = ws_android / ".agents" / "skills" / "ux-hig-prototype-spec" / "scripts"
    assert (ux_scripts_android / "check_material.py").exists()
    assert not (ux_scripts_android / "check_hig.py").exists()

    # Verify MCP config contains platform env
    mcp_file_android = ws_android / ".mcp.json"
    content_android = mcp_file_android.read_text(encoding="utf-8")
    assert '"MODUFLOW_PLATFORM": "android"' in content_android

    # 2. iOS workspace
    ws_ios = tmp_path / "ws_ios"
    info_ios = mount_role_skills_and_mcp(
        workspace_dir=ws_ios,
        primary_role_code="ux",
        platform="ios"
    )
    ux_scripts_ios = ws_ios / ".agents" / "skills" / "ux-hig-prototype-spec" / "scripts"
    assert (ux_scripts_ios / "check_hig.py").exists()
    assert not (ux_scripts_ios / "check_material.py").exists()

    # 3. ENG workspace with client_zero_inference=False
    ws_eng = tmp_path / "ws_eng"
    mount_role_skills_and_mcp(
        workspace_dir=ws_eng,
        primary_role_code="eng",
        client_zero_inference=False
    )
    cost_script = ws_eng / ".agents" / "skills" / "eng-lean-architecture-coder" / "scripts" / "cost_audit.py"
    cost_content = cost_script.read_text(encoding="utf-8")
    assert "'zero_inference_enforced': False" in cost_content
    assert "'edge_ai_allowed': True" in cost_content


def test_compliance_audit_by_platform():
    """Verify compliance audit checks platform-appropriate policies."""
    # Stage 05 with ad tracking on Android -> Google Play AD_ID
    res_android_05 = audit_stage_compliance(
        stage_code="05",
        content="本项目涉及广告追踪与归因分析",
        platform="android"
    )
    items_android = [f["item"] for f in res_android_05["findings"]]
    assert any("Google Play Advertising ID" in it for it in items_android)
    assert not any("Apple App Tracking Transparency" in it for it in items_android)

    # Stage 05 with ad tracking on iOS -> Apple ATT
    res_ios_05 = audit_stage_compliance(
        stage_code="05",
        content="本项目涉及广告追踪与归因分析",
        platform="ios"
    )
    items_ios = [f["item"] for f in res_ios_05["findings"]]
    assert any("Apple App Tracking Transparency" in it for it in items_ios)

    # Stage 09 on Android -> Google Play Policy, NOT Apple 4.3
    res_android_09 = audit_stage_compliance(
        stage_code="09",
        content="提审前进行重复应用查重与换皮排查，包含隐私政策 https://example.com/privacy 与 Remote Config 降级开关与回滚预案",
        platform="android"
    )
    items_android_09 = [f["item"] for f in res_android_09["findings"]]
    assert any("Google Play" in it for it in items_android_09)
    assert not any("Apple 4.3" in it for it in items_android_09)


def test_dynamic_gate_conditions_by_profile():
    """Verify get_stage_gate_conditions adapts to platform and zero inference profile."""
    # Stage 06 iOS
    cond_ios = get_stage_gate_conditions("06", platform="ios")
    assert any("iOS 灵动岛" in c for c in cond_ios)

    # Stage 06 Android
    cond_android = get_stage_gate_conditions("06", platform="android")
    assert any("Android Material 3" in c for c in cond_android)
    assert any("48x48dp" in c for c in cond_android)
    assert not any("灵动岛" in c for c in cond_android)

    # Stage 07 strict zero inference
    cond_strict = get_stage_gate_conditions("07", client_zero_inference=True)
    assert any("强制零推理" in c for c in cond_strict)

    # Stage 07 edge AI permitted
    cond_edge = get_stage_gate_conditions("07", client_zero_inference=False)
    assert any("允许端侧本地模型" in c for c in cond_edge)


@pytest.mark.asyncio
async def test_api_product_profile_and_audits():
    """Verify REST API endpoints for product profile and dynamic audits."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Android product with client_zero_inference=False
        auth_pkg = generate_default_authorization_dict(
            product_code=f"android_{uuid.uuid4().hex[:6]}",
            product_name="Android AI Camera",
            budget_allocated=6000.0,
            platform="android",
            client_zero_inference=False
        )

        create_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Android AI Camera",
                "code": auth_pkg["project_id"],
                "platform": "android",
                "client_zero_inference": False,
                "authorization_package": auth_pkg
            },
            headers={"X-ModuFlow-Actor": "human:alice"}
        )
        assert create_resp.status_code == 200
        prod_data = create_resp.json()
        prod_id = prod_data["id"]
        assert prod_data["platform"] == "android"
        assert prod_data["client_zero_inference"] is False

        # 2. Query profile endpoint
        prof_resp = await client.get(f"/api/v1/products/{prod_id}/profile")
        assert prof_resp.status_code == 200
        prof_data = prof_resp.json()
        assert prof_data["platform"] == "android"
        assert prof_data["client_zero_inference"] is False
        assert prof_data["ruleset"] == "Google Material Design 3 (M3)"

        # 3. Create run and module for audit testing
        run_resp = await client.post(
            "/api/v1/runs",
            json={"name": "V1.0 Run", "product_id": prod_id, "template_id": "full-product-launch"}
        )
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        mods = run_data["modules"]
        mod_06 = next(m for m in mods if m["module_code"] == "06")
        mod_07 = next(m for m in mods if m["module_code"] == "07")

        # 4. Design audit on Android module 06:
        # Pass 48dp (valid on Android, invalid on iOS)
        design_resp = await client.post(
            f"/api/v1/modules/{mod_06['id']}/design-audit",
            json={"top_safe_value": 48, "min_touch_value": 48}
        )
        assert design_resp.status_code == 200
        design_data = design_resp.json()
        assert design_data["passed"] is True
        assert design_data["platform"] == "android"
        assert design_data["ruleset"] == "Google Material Design 3 (M3)"

        # 5. Zero inference audit on Android module 07 (client_zero_inference=False):
        # 3 realtime calls should PASS because client_zero_inference=False
        inf_resp = await client.post(
            f"/api/v1/modules/{mod_07['id']}/zero-inference-audit",
            json={"client_realtime_ai_calls": 3, "avg_cdn_bandwidth_mb": 10.0}
        )
        assert inf_resp.status_code == 200
        inf_data = inf_resp.json()
        assert inf_data["passed"] is True
        assert inf_data["edge_ai_permitted"] is True
        assert inf_data["enforce_zero_inference"] is False
