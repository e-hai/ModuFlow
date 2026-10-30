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

        # Check Lead's sharp reply
        assert "战略定位定性" in reply
        assert "真实市场与竞品信号" in reply
        assert "红队挑战" in reply

        # Check proposal parameters
        assert proposal["budget"] == 15000.0
        assert proposal["currency"] == "USD"
        assert "专注" in proposal["name"] or "Focus" in proposal["name"]
        assert len(proposal["signals"]) >= 2
        assert len(proposal["unverified_assumptions"]) >= 1
        assert len(proposal["kill_criteria"]) >= 1
        assert "01_market_research" in proposal["stage_allocations"]


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
        assert len(created["initiative_rationale"]["signals"]) >= 1
        assert created["initiative_rationale"]["lead_recommendation"] == "approved_by_lead_intake"
