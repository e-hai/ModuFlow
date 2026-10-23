import io
import zipfile
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.tests.conftest import test_engine as engine, TestingSessionLocal as AsyncSessionLocal
from backend.app.core.database import Base
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.models.entities import StrategicInitiative, Product, ModuleInstance, Artifact, ChangeReview, AgentSettingsModel
from backend.app.core.config import settings
from sqlalchemy import select

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
            "initiative_id": init_id
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

        # Find 06 (PRD) and 07 (Design) and 09 (Dev) modules
        m06 = next(m for m in run_data["modules"] if m["module_code"] == "06")
        m07 = next(m for m in run_data["modules"] if m["module_code"] == "07")
        m09 = next(m for m in run_data["modules"] if m["module_code"] == "09")

        # 3. Create a zip archive simulating a design prototype bundle
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", "<!DOCTYPE html><html><body><h1>Prototype v1</h1><div class='nav'>Home</div></body></html>")
            zf.writestr("assets/style.css", "body { background: #fafafa; }")
            zf.writestr("preview/screen1.png", b"fake-png-bytes")
        zip_bytes = zip_buf.getvalue()

        # 4. Upload bundle to module 07 (Design)
        upload_res = await client.post(
            f"/api/v1/modules/{m07['id']}/artifacts/upload",
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
        reviews_res = await client.get(f"/api/v1/change-reviews?module_id={m07['id']}&status=pending_approval")
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

        # Verify module 07 is now baselined and artifact is baseline
        m07_res = await client.get(f"/api/v1/modules/{m07['id']}")
        assert m07_res.json()["phase"] == "baselined"
        assert m07_res.json()["baseline_artifact_id"] == artifact_id

@pytest.mark.asyncio
async def test_upstream_stale_detection_and_ack_flow():
    """Test that modifying an upstream spec (v1 -> v2) causes downstream modules to detect stale status, and ack resolves it."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create initiative & product
        init_res = await client.post("/api/v1/initiatives", json={"name": "Stale Flow Test", "owner": "PM"})
        init_id = init_res.json()["id"]
        prod_res = await client.post("/api/v1/products", json={"name": "App2", "code": "APP-2", "initiative_id": init_id})
        prod_id = prod_res.json()["id"]

        run_res = await client.post("/api/v1/runs", json={
            "product_id": prod_id,
            "template_id": "fast-iteration",
            "name": "Sprint-Stale"
        })
        run_data = run_res.json()
        m06 = next(m for m in run_data["modules"] if m["module_code"] == "06") # PRD
        m09 = next(m for m in run_data["modules"] if m["module_code"] == "09") # Dev

        # 1. Upload PRD v1 to module 06
        prd_v1 = "# PRD v1\n- Feature A: User login with phone OTP\n- Feature B: Basic dashboard"
        up_v1_res = await client.post(
            f"/api/v1/modules/{m06['id']}/artifacts/upload",
            files={"file": ("prd_v1.md", prd_v1.encode("utf-8"), "text/markdown")},
            data={"change_summary": "Initial PRD scope"}
        )
        assert up_v1_res.status_code == 200
        rev1_id = up_v1_res.json()["change_review"]["id"]

        # Approve PRD v1
        await client.post(f"/api/v1/change-reviews/{rev1_id}/approve", json={"approver": "CEO"})

        # Unlock module 09 (simulate unlocking downstream)
        async with AsyncSessionLocal() as db:
            m09_db = (await db.execute(select(ModuleInstance).where(ModuleInstance.id == m09["id"]))).scalar_one()
            m09_db.is_unlocked = True
            # Downstream is tracking v1
            m09_db.synced_upstream_versions = {"06": 1}
            await db.commit()

        # Check m09 stale status -> should be FALSE (synced with v1)
        m09_check = await client.get(f"/api/v1/modules/{m09['id']}")
        assert m09_check.json()["is_upstream_stale"] is False

        # 2. Upload PRD v2 to module 06 with scope change
        prd_v2 = "# PRD v2\n- Feature A: User login with OAuth (Google/Apple)\n- Feature B: Basic dashboard\n- Feature C: Multi-currency wallet"
        up_v2_res = await client.post(
            f"/api/v1/modules/{m06['id']}/artifacts/upload",
            files={"file": ("prd_v2.md", prd_v2.encode("utf-8"), "text/markdown")},
            data={"change_summary": "Changed phone OTP to OAuth and added wallet"}
        )
        assert up_v2_res.status_code == 200
        rev2_id = up_v2_res.json()["change_review"]["id"]
        assert up_v2_res.json()["artifact"]["version"] == 2

        # Lead approves PRD v2
        await client.post(f"/api/v1/change-reviews/{rev2_id}/approve", json={"approver": "CEO"})

        # 3. Now check module 09 (Dev) -> MUST BE DETECTED AS STALE!
        m09_stale_res = await client.get(f"/api/v1/modules/{m09['id']}")
        m09_data = m09_stale_res.json()
        assert m09_data["is_upstream_stale"] is True
        assert len(m09_data["stale_details"]) > 0
        detail = m09_data["stale_details"][0]
        assert detail["upstream_code"] == "06"
        assert detail["current_synced_version"] == 1
        assert detail["latest_upstream_version"] == 2

        # Also verify in get_run batch endpoint
        run_batch_res = await client.get(f"/api/v1/runs/{run_data['id']}")
        run_batch_m09 = next(m for m in run_batch_res.json()["modules"] if m["module_code"] == "09")
        assert run_batch_m09["is_upstream_stale"] is True

        # 4. Dev acknowledges the upstream update
        ack_res = await client.post(f"/api/v1/modules/{m09['id']}/ack-upstream", json={"upstream_code": "06"})
        assert ack_res.status_code == 200
        assert ack_res.json()["synced_upstream_versions"]["06"] == 2
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
            "timeout": 180
        })
        assert update_res.status_code == 200
        assert update_res.json()["adapter_type"] == "cli"
        assert update_res.json()["cli_command"] == "agy"
        assert update_res.json()["timeout"] == 180

        # Verify DB directly
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(AgentSettingsModel).where(AgentSettingsModel.id == "default"))).scalar_one()
            assert row.adapter_type == "cli"
            assert row.cli_command == "agy"
            assert row.timeout == 180
