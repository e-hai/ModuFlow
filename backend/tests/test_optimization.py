import io
import zipfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.tests.conftest import test_engine as engine, TestingSessionLocal as AsyncSessionLocal
from backend.app.core.database import Base
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.models.entities import StrategicInitiative, Product, ModuleInstance, Artifact, ChangeReview, AgentSettingsModel
from backend.app.core.config import settings
from sqlalchemy import select
from backend.tests.test_gate_system import _PASSING_PRD

@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)

@pytest.mark.asyncio
async def test_bundle_upload_and_preview_flow():
    """Test full zip bundle upload, extraction, preview serving, and ChangeReview generation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create initiative and product
        init_res = await client.post("/api/v1/initiatives", json={
            "name": "海外设计系统测试工程",
            "owner": "DesignLead",
            "budget": 100000.0,
            "status": "validating"
        })
        assert init_res.status_code == 200
        init_id = init_res.json()["id"]

        prod_res = await client.post("/api/v1/products", json={
            "name": "TestApp",
            "code": "TEST-APP",
            "initiative_id": init_id,
            "auto_authorize": True
        })
        assert prod_res.status_code == 200
        prod_id = prod_res.json()["id"]

        # 2. Create workflow run
        run_res = await client.post("/api/v1/runs", json={
            "product_id": prod_id,
            "template_id": "fast-iteration",
            "name": "Sprint-1"
        })
        assert run_res.status_code == 200
        run_data = run_res.json()
        run_id = run_data["id"]

        # Find 05 (PRD) and 06 (Design) and 07 (Dev) modules
        m05 = next(m for m in run_data["modules"] if m["module_code"] == "05")
        m06 = next(m for m in run_data["modules"] if m["module_code"] == "06")
        m07 = next(m for m in run_data["modules"] if m["module_code"] == "07")

        # 3. Create a zip archive simulating a design prototype bundle
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "index.html",
                "top_safe_padding_pt: 74\nmin_touch_target_pt: 44\nstatus_bar_safe_dp: 32\nmin_touch_target_dp: 48\n"
                "<!DOCTYPE html><html><body><h1>Prototype v1</h1><div class='nav'>Home</div></body></html>",
            )
            zf.writestr("assets/style.css", "body { background: #fafafa; }")
            zf.writestr("preview/screen1.png", b"fake-png-bytes")
        zip_bytes = zip_buf.getvalue()

        # 4. Upload bundle to module 06 (Design)
        upload_res = await client.post(
            f"/api/v1/modules/{m06['id']}/artifacts/upload",
            files={"file": ("prototype_v1.zip", zip_bytes, "application/zip")},
            data={"change_summary": "Initial high-fidelity interactive prototype bundle"}
        )
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        artifact_id = upload_data["artifact"]["id"]
        review_id = upload_data["change_review"]["id"]

        assert upload_data["artifact"]["artifact_type"] == "html_bundle"
        assert upload_data["artifact"]["entry_file"] == "index.html"
        assert upload_data["artifact"]["version"] == 1
        assert upload_data["artifact"]["is_baseline"] is False
        assert upload_data["change_review"]["status"] == "pending_approval"

        # 5. Test static preview endpoint
        preview_res = await client.get(f"/api/v1/artifacts/{artifact_id}/preview")
        assert preview_res.status_code == 200
        assert "Prototype v1" in preview_res.text

        css_res = await client.get(f"/api/v1/artifacts/{artifact_id}/preview/assets/style.css")
        assert css_res.status_code == 200
        assert "background: #fafafa" in css_res.text

        # 6. Test change reviews query
        reviews_res = await client.get(f"/api/v1/change-reviews?module_id={m06['id']}&status=pending_approval")
        assert reviews_res.status_code == 200
        reviews_list = reviews_res.json()
        assert len(reviews_list) >= 1
        assert reviews_list[0]["id"] == review_id

        # 7. Approve the change review
        approve_res = await client.post(f"/api/v1/change-reviews/{review_id}/approve", json={
            "approver": "产品总监",
            "rejection_reason": None
        })
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "approved"
        assert approve_res.json()["approver"] == "产品总监"

        # Verify module 06 is now baselined and artifact is baseline
        m06_res = await client.get(f"/api/v1/modules/{m06['id']}")
        assert m06_res.json()["phase"] == "baselined"
        assert m06_res.json()["baseline_artifact_id"] == artifact_id

@pytest.mark.asyncio
async def test_upstream_stale_detection_and_ack_flow():
    """Test that modifying an upstream spec (v1 -> v2) causes downstream modules to detect stale status, and ack resolves it."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create initiative & product
        init_res = await client.post("/api/v1/initiatives", json={"name": "Stale Flow Test", "owner": "PM"})
        init_id = init_res.json()["id"]
        prod_res = await client.post("/api/v1/products", json={"name": "App2", "code": "APP-2", "initiative_id": init_id, "auto_authorize": True})
        prod_id = prod_res.json()["id"]

        run_res = await client.post("/api/v1/runs", json={
            "product_id": prod_id,
            "template_id": "fast-iteration",
            "name": "Sprint-Stale"
        })
        run_data = run_res.json()
        m05 = next(m for m in run_data["modules"] if m["module_code"] == "05") # PRD
        m07 = next(m for m in run_data["modules"] if m["module_code"] == "07") # Dev

        # 1. Upload PRD v1 to module 05
        prd_v1 = _PASSING_PRD + "\n- Feature A: User login with phone OTP\n- Feature B: Basic dashboard"
        up_v1_res = await client.post(
            f"/api/v1/modules/{m05['id']}/artifacts/upload",
            files={"file": ("prd_v1.md", prd_v1.encode("utf-8"), "text/markdown")},
            data={"change_summary": "Initial PRD scope"}
        )
        assert up_v1_res.status_code == 200
        rev1_id = up_v1_res.json()["change_review"]["id"]

        # Approve PRD v1
        await client.post(f"/api/v1/change-reviews/{rev1_id}/approve", json={"approver": "CEO"})

        # Unlock module 07 (simulate unlocking downstream)
        async with AsyncSessionLocal() as db:
            m07_db = (await db.execute(select(ModuleInstance).where(ModuleInstance.id == m07["id"]))).scalar_one()
            m07_db.is_unlocked = True
            # Downstream is tracking v1
            m07_db.synced_upstream_versions = {"05": 1}
            await db.commit()

        # Check m07 stale status -> should be FALSE (synced with v1)
        m07_check = await client.get(f"/api/v1/modules/{m07['id']}")
        assert m07_check.json()["is_upstream_stale"] is False

        # 2. Upload PRD v2 to module 05 with scope change
        prd_v2 = _PASSING_PRD + "\n- Feature A: User login with OAuth (Google/Apple)\n- Feature B: Basic dashboard\n- Feature C: Multi-currency wallet"
        up_v2_res = await client.post(
            f"/api/v1/modules/{m05['id']}/artifacts/upload",
            files={"file": ("prd_v2.md", prd_v2.encode("utf-8"), "text/markdown")},
            data={"change_summary": "Changed phone OTP to OAuth and added wallet"}
        )
        assert up_v2_res.status_code == 200
        rev2_id = up_v2_res.json()["change_review"]["id"]
        assert up_v2_res.json()["artifact"]["version"] == 2

        # Lead approves PRD v2
        await client.post(f"/api/v1/change-reviews/{rev2_id}/approve", json={"approver": "CEO"})

        # 3. Now check module 07 (Dev) -> MUST BE DETECTED AS STALE!
        m07_stale_res = await client.get(f"/api/v1/modules/{m07['id']}")
        m07_data = m07_stale_res.json()
        assert m07_data["is_upstream_stale"] is True
        assert len(m07_data["stale_details"]) > 0
        detail = m07_data["stale_details"][0]
        assert detail["upstream_code"] == "05"
        assert detail["current_synced_version"] == 1
        assert detail["latest_upstream_version"] == 2

        # Also verify in get_run batch endpoint
        run_batch_res = await client.get(f"/api/v1/runs/{run_data['id']}")
        run_batch_m07 = next(m for m in run_batch_res.json()["modules"] if m["module_code"] == "07")
        assert run_batch_m07["is_upstream_stale"] is True

        # 4. Dev acknowledges the upstream update
        ack_res = await client.post(f"/api/v1/modules/{m07['id']}/ack-upstream", json={"upstream_code": "05"})
        assert ack_res.status_code == 200
        assert ack_res.json()["synced_upstream_versions"]["05"] == 2
        assert ack_res.json()["is_upstream_stale"] is False

@pytest.mark.asyncio
async def test_agent_settings_persistence():
    """Test that agent settings are correctly persisted into database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Fetch current settings
        res = await client.get("/api/v1/settings/agent")
        assert res.status_code == 200
        data = res.json()
        assert "available_presets" in data

        # Update settings to agy CLI with 180s timeout
        update_res = await client.patch("/api/v1/settings/agent", json={
            "adapter_type": "cli",
            "cli_command": "agy",
            "cli_model": "gemini-4-argon-low",
            "timeout": 180
        })
        assert update_res.status_code == 200
        assert update_res.json()["adapter_type"] == "cli"
        assert update_res.json()["cli_command"] == "agy"
        assert update_res.json()["cli_model"] == "gemini-4-argon-low"
        assert update_res.json()["timeout"] == 180

        cleared = await client.patch("/api/v1/settings/agent", json={"cli_model": ""})
        assert cleared.status_code == 200
        assert cleared.json()["cli_model"] in (None, "")

        invalid = await client.patch("/api/v1/settings/agent", json={"cli_model": "bad model"})
        assert invalid.status_code == 400

        # Verify DB directly
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(AgentSettingsModel).where(AgentSettingsModel.id == "default"))).scalar_one()
            assert row.adapter_type == "cli"
            assert row.cli_command == "agy"
            assert row.cli_model in (None, "")
            assert row.timeout == 180

@pytest.mark.asyncio
async def test_requirement_cr_feedback_loop_and_prd_revision():
    """Test end-to-end CR feedback loop: Downstream raises CR, Stage 05 retains baseline, revises PRD to v2, closes CR, and alerts downstream."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create initiative & product with fast-iteration template
        init_res = await client.post("/api/v1/initiatives", json={"name": "CR Loop Test", "owner": "PO"})
        init_id = init_res.json()["id"]
        prod_res = await client.post("/api/v1/products", json={"name": "WnPager", "code": "WN-PG", "initiative_id": init_id, "auto_authorize": True})
        prod_id = prod_res.json()["id"]

        run_res = await client.post("/api/v1/runs", json={
            "product_id": prod_id,
            "template_id": "fast-iteration",
            "name": "Sprint-CR-Loop"
        })
        run_data = run_res.json()
        m05 = next(m for m in run_data["modules"] if m["module_code"] == "05")
        m06 = next(m for m in run_data["modules"] if m["module_code"] == "06")

        # 2. Stage 05 uploads & baselines PRD v1
        prd_v1 = (
            "# PRD v1\n- Feature: Double-column paginated view with fixed page sizes\n"
            + _PASSING_PRD
        )
        up_v1_res = await client.post(
            f"/api/v1/modules/{m05['id']}/artifacts/upload",
            files={"file": ("prd_v1.md", prd_v1.encode("utf-8"), "text/markdown")},
            data={"change_summary": "Initial PRD v1 baseline"}
        )
        assert up_v1_res.status_code == 200
        rev1_id = up_v1_res.json()["change_review"]["id"]
        art1_id = up_v1_res.json()["artifact"]["id"]

        # Approve PRD v1
        await client.post(f"/api/v1/change-reviews/{rev1_id}/approve", json={"approver": "CPO"})

        # Check m05 is baselined
        m05_data = (await client.get(f"/api/v1/modules/{m05['id']}")).json()
        assert m05_data["phase"] == "baselined"
        assert m05_data["baseline_artifact_id"] == art1_id

        # 3. Stage 06 syncs with PRD v1
        async with AsyncSessionLocal() as db:
            m06_db = (await db.execute(select(ModuleInstance).where(ModuleInstance.id == m06["id"]))).scalar_one()
            m06_db.synced_upstream_versions = {"05": 1}
            await db.commit()

        # 4. Stage 06 finds pagination conflicting with mobile layout, raises a requirement_cr issue targeting 05
        issue_res = await client.post("/api/v1/issues", json={
            "title": "建议将双列分页调整为下拉瀑布流，规避单手触控拥挤",
            "source_module_id": m06["id"],
            "target_module_id": m05["id"],
            "reporter": "UI/UX 设计师",
            "reporter_role": "ux",
            "category": "requirement_cr",
            "severity": "major",
            "priority": "P1",
            "description": {
                "summary": "双列翻页按钮挤占底部安全区",
                "unreasonable_point": "双列排版导致翻页按钮在灵动岛机型上触控热区不足 44pt",
                "constraint": "iOS HIG 规范与单手拇指热区",
                "suggested_change": "采用下拉无限滚动与触底预加载",
                "affected_modules": ["05", "06", "07"]
            }
        })
        assert issue_res.status_code == 200
        issue_id = issue_res.json()["id"]

        # Verify Stage 05 phase enters discussing, BUT baseline_artifact_id is NOT wiped
        m05_after_issue = (await client.get(f"/api/v1/modules/{m05['id']}")).json()
        assert m05_after_issue["phase"] == "discussing"
        assert m05_after_issue["baseline_artifact_id"] == art1_id # Preserved!

        # 5. Stage 05 adopts CR and runs Agent revision with issue_ref_id
        sess_res = await client.get(f"/api/v1/modules/{m05['id']}/session")
        session_id = sess_res.json()["id"]

        # Ensure settings use simulator for fast test execution
        await client.patch("/api/v1/settings/agent", json={"adapter_type": "simulator"})

        send_res = await client.post(
            f"/api/v1/sessions/{session_id}/messages?trigger_agent=true",
            json={
                "sender": "CPO",
                "sender_role": "human",
                "message_type": "feedback",
                "content": f"采纳来自工序 06 的需求变更单 [{issue_id}]，将双列分页调整为无限瀑布流。",
                "issue_ref_id": issue_id
            }
        )
        assert send_res.status_code == 200

        # Verify issue is now auto-closed
        issue_check = (await client.get(f"/api/v1/issues/{issue_id}")).json()
        assert issue_check["status"] == "closed"
        assert "完成修订" in issue_check["resolution"]

        # 6. Stage 05 now has artifact v2
        arts = (await client.get(f"/api/v1/modules/{m05['id']}/artifacts")).json()
        assert len(arts) >= 2
        art_v2 = next(a for a in arts if a["version"] == 2)
        assert f"[{issue_id}]" in (art_v2["change_summary"] or "")

        # 7. Baseline v2
        baseline_v2_res = await client.patch(
            f"/api/v1/modules/{m05['id']}/phase",
            json={"phase": "baselined", "artifact_id": art_v2["id"]}
        )
        assert baseline_v2_res.status_code == 200

        # 8. Check downstream module 06 -> Detected as stale with upstream_change_summary!
        m06_stale = (await client.get(f"/api/v1/modules/{m06['id']}")).json()
        assert m06_stale["is_upstream_stale"] is True
        assert len(m06_stale["stale_details"]) > 0
        detail = m06_stale["stale_details"][0]
        assert detail["upstream_code"] == "05"
        assert detail["current_synced_version"] == 1
        assert detail["latest_upstream_version"] == 2
        assert f"[{issue_id}]" in detail["upstream_change_summary"]
