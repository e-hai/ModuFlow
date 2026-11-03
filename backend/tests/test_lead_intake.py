import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.tests.conftest import (
    test_engine as engine,
    TestingSessionLocal as AsyncSessionLocal
)
from backend.app.core.database import Base


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_lead_intake_chat_initial_greeting():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/initiatives/intake/chat", json={
            "messages": [],
            "current_draft": None
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "Lead" in data["reply"]
        assert len(data["quick_prompts"]) > 0


@pytest.mark.asyncio
async def test_lead_intake_chat_focus_track():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/initiatives/intake/chat", json={
            "messages": [
                {"role": "user", "content": "我想在北美做一款极简专注番茄钟，主打买断制与离线隐私，前期总预算控制在 15,000 美元内"}
            ],
            "current_draft": None
        })
        assert resp.status_code == 200
        data = resp.json()
        reply = data["reply"]
        proposal = data["proposal"]

        assert "已记下" in reply
        assert "15,000" in reply or "15000" in reply.replace(",", "")
        assert "Forest" not in reply
        assert "Sensor Tower" not in reply

        assert proposal["budget"] == 15000.0
        assert proposal["currency"] == "USD"
        assert "专注" in proposal["name"]
        assert "北美离线极简专注" not in proposal["name"]
        assert proposal.get("signals") in (None, [])
        assert proposal.get("stage_allocations") in (None, {})


@pytest.mark.asyncio
async def test_create_initiative_with_lead_rationale():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Intake chat
        intake_resp = await ac.post("/api/v1/initiatives/intake/chat", json={
            "messages": [
                {"role": "user", "content": "做一款出海 AI 图像修复工具，预算 18,000 美元"}
            ]
        })
        assert intake_resp.status_code == 200
        proposal = intake_resp.json()["proposal"]

        # 2. Adopt & create initiative
        create_payload = {
            "name": proposal["name"],
            "description": proposal.get("description", ""),
            "owner": "CEO",
            "budget": proposal["budget"],
            "status": "validating",
            "strategic_intent": proposal.get("strategic_intent"),
            "target_market": proposal.get("target_market"),
            "business_model_hypothesis": proposal.get("business_model_hypothesis"),
            "initiative_rationale": {
                "signals": proposal.get("signals"),
                "unverified_assumptions": proposal.get("unverified_assumptions"),
                "kill_criteria": proposal.get("kill_criteria"),
                "stage_allocations": proposal.get("stage_allocations"),
                "lead_recommendation": "approved_by_lead_intake"
            }
        }

        create_resp = await ac.post("/api/v1/initiatives", json=create_payload)
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["name"] == proposal["name"]
        assert created["initiative_rationale"] is not None
        assert created["initiative_rationale"].get("signals") in (None, [])
        assert "图像" in created["name"]
        assert created["budget"] == 18000.0
        assert created["initiative_rationale"]["lead_recommendation"] == "approved_by_lead_intake"


@pytest.mark.asyncio
async def test_intake_message_is_queued_when_orchestration_is_on(monkeypatch):
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/initiatives/intake/chat", json={
            "messages": [
                {"role": "user", "content": "做一款自媒体旅游视频工具，预算 9,000 美元"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "正在查阅可靠来源"
        assert data["job_id"]
        assert data["draft_id"]
        job = await ac.get(f"/api/v1/initiatives/intake/jobs/{data['job_id']}")
        assert job.status_code == 200
        assert job.json()["status"] == "queued"
