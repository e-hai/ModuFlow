"""
ModuFlow Phase 7: Hotfix Documentation SLA & Portfolio Weekly Digest Tests
(backend/tests/test_hotfix_portfolio.py)

Validates:
1. Hotfix release automatically triggers 3 mandatory follow-up tasks (补 CR + 复盘 + PRD 更新).
2. Deterministic 24h completion SLA tracking:
   - Within 24h: no alert.
   - Overdue (> 24h) with pending tasks: automatically creates 🔴 critical ExecutiveRisk alert
     and writes an audit log into decisions/.
3. Completing all tasks resolves the SLA and prevents overdue alerts.
4. Non-hotfix runs cannot trigger hotfix followup creation (negative test).
5. Portfolio Executive Weekly Report (一页周报):
   - Reads stage, budget/spent, KPIs, risks, and recommendations across all products in DB.
   - Enforces strict redline: recommendations ONLY, NO autonomous budget/killing action.
   - Persists report to data/workspaces/{initiative_id}/portfolio_weekly_report.md and logs decisions/.
6. REST API endpoints for hotfix lifecycle and portfolio report.
"""

import os
import uuid
import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from sqlalchemy import select
from backend.app.core.database import Base
from backend.tests.conftest import test_engine as engine, TestingSessionLocal as AsyncSessionLocal, ensure_test_product_authorization
from backend.app.main import app
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowTemplate,
    WorkflowRun,
    HotfixFollowupTask,
    ExecutiveRisk
)
from backend.app.services.agent_roles import (
    migrate_db_for_roles,
    seed_agent_roles_if_empty
)
from backend.app.services.workflow_engine import seed_templates_if_empty
from backend.app.services.portfolio_and_hotfix_service import (
    create_hotfix_followup_tasks,
    check_hotfix_documentation_sla,
    complete_hotfix_task,
    generate_portfolio_weekly_report
)
from scripts.migrate_legacy_project_auth import generate_default_authorization_dict


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await migrate_db_for_roles(db)
        await seed_agent_roles_if_empty(db)
        await seed_templates_if_empty(db)
    yield


@pytest.mark.asyncio
async def test_hotfix_followup_tasks_creation_and_idempotency():
    """Verify that hotfix release provisions 3 mandatory tasks with 24h deadline."""
    async with AsyncSessionLocal() as db:
        # Create initiative & product
        init = StrategicInitiative(
            id=f"init_hf_{uuid.uuid4().hex[:6]}",
            name="Hotfix Initiative",
            target_market="全球",
            budget=10000.0
        )
        db.add(init)
        prod = Product(
            id=f"prod_hf_{uuid.uuid4().hex[:6]}",
            initiative_id=init.id,
            name="Hotfix Product",
            code=f"HF_{uuid.uuid4().hex[:4]}",
            platform="ios",
            client_zero_inference=True,
            budget_allocated=5000.0,
            stage="growth"
        )
        db.add(prod)
        run = WorkflowRun(
            id=f"run_hf_{uuid.uuid4().hex[:6]}",
            product_id=prod.id,
            template_id="hotfix",
            name="Emergency Hotfix V1.0.1",
            status="completed"
        )
        db.add(run)
        await db.commit()

        # 1. Trigger follow-up task creation
        res = await create_hotfix_followup_tasks(db, run.id, actor_id="human:sponsor")
        assert res["status"] == "created"
        assert res["tasks_count"] == 3
        tasks = res["tasks"]
        task_types = {t["task_type"] for t in tasks}
        assert task_types == {"cr_patch", "postmortem", "prd_update"}

        # Verify 24h deadline
        deadline_dt = datetime.fromisoformat(res["deadline"])
        now_dt = datetime.now(timezone.utc)
        diff_hours = (deadline_dt - now_dt).total_seconds() / 3600
        assert 23.5 <= diff_hours <= 24.5

        # 2. Idempotency check: calling again returns already_exists without duplicating
        res2 = await create_hotfix_followup_tasks(db, run.id, actor_id="human:sponsor")
        assert res2["status"] == "already_exists"
        assert res2["tasks_count"] == 3


@pytest.mark.asyncio
async def test_negative_non_hotfix_run_rejected():
    """Negative test: non-hotfix run cannot trigger hotfix followup tasks."""
    async with AsyncSessionLocal() as db:
        prod = Product(
            id=f"prod_{uuid.uuid4().hex[:6]}",
            name="Normal Product",
            code=f"NORM_{uuid.uuid4().hex[:4]}",
            budget_allocated=5000.0
        )
        db.add(prod)
        run = WorkflowRun(
            id=f"run_norm_{uuid.uuid4().hex[:6]}",
            product_id=prod.id,
            template_id="full-product-launch",
            name="Regular Launch",
            status="completed"
        )
        db.add(run)
        await db.commit()

        with pytest.raises(Exception) as excinfo:
            await create_hotfix_followup_tasks(db, run.id)
        assert "hotfix" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_hotfix_sla_within_window_no_alert():
    """Within 24 hours of release, SLA check reports not overdue and raises no alert."""
    async with AsyncSessionLocal() as db:
        prod = Product(
            id=f"prod_{uuid.uuid4().hex[:6]}",
            name="Product A",
            code=f"PA_{uuid.uuid4().hex[:4]}",
            budget_allocated=5000.0
        )
        db.add(prod)
        run = WorkflowRun(
            id=f"run_{uuid.uuid4().hex[:6]}",
            product_id=prod.id,
            template_id="hotfix",
            name="Hotfix Run",
            status="completed"
        )
        db.add(run)
        await db.commit()

        await create_hotfix_followup_tasks(db, run.id)

        # Check at 2 hours after release (well within 24h SLA)
        simulated_time = datetime.now(timezone.utc) + timedelta(hours=2)
        sla_res = await check_hotfix_documentation_sla(db, run.id, check_time=simulated_time)

        assert sla_res["is_overdue"] is False
        assert sla_res["alert_created"] is False
        assert sla_res["pending_count"] == 3


@pytest.mark.asyncio
async def test_hotfix_sla_overdue_triggers_critical_alert():
    """
    CRITICAL ACCEPTANCE TEST:
    If 24h passes and tasks remain pending, system automatically creates 🔴 critical ExecutiveRisk
    and logs decision.
    """
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(
            id=f"init_{uuid.uuid4().hex[:6]}",
            name="Initiative With Hotfix Risk",
            target_market="全球"
        )
        db.add(init)
        prod = Product(
            id=f"prod_{uuid.uuid4().hex[:6]}",
            initiative_id=init.id,
            name="Risk Product",
            code=f"RP_{uuid.uuid4().hex[:4]}",
            budget_allocated=5000.0
        )
        db.add(prod)
        run = WorkflowRun(
            id=f"run_{uuid.uuid4().hex[:6]}",
            product_id=prod.id,
            template_id="hotfix",
            name="Overdue Hotfix",
            status="completed"
        )
        db.add(run)
        await db.commit()

        await create_hotfix_followup_tasks(db, run.id)

        # Simulate 25 hours later (> 24h deadline)
        simulated_overdue_time = datetime.now(timezone.utc) + timedelta(hours=25)
        sla_res = await check_hotfix_documentation_sla(db, run.id, check_time=simulated_overdue_time)

        assert sla_res["is_overdue"] is True
        assert sla_res["alert_created"] is True
        assert sla_res["pending_count"] == 3

        # Verify critical ExecutiveRisk exists in database
        risk_stmt = select(ExecutiveRisk).where(
            ExecutiveRisk.initiative_id == init.id,
            ExecutiveRisk.severity == "critical"
        )
        risk_res = await db.execute(risk_stmt)
        risk = risk_res.scalar_one_or_none()
        assert risk is not None
        assert "热修补档超期告警" in risk.title
        assert risk.is_resolved is False


@pytest.mark.asyncio
async def test_hotfix_tasks_completed_prevents_alert():
    """When all 3 tasks are completed within or before SLA check, no alert is raised."""
    async with AsyncSessionLocal() as db:
        prod = Product(
            id=f"prod_{uuid.uuid4().hex[:6]}",
            name="Completed Product",
            code=f"CP_{uuid.uuid4().hex[:4]}",
            budget_allocated=5000.0
        )
        db.add(prod)
        run = WorkflowRun(
            id=f"run_{uuid.uuid4().hex[:6]}",
            product_id=prod.id,
            template_id="hotfix",
            name="Fast Hotfix",
            status="completed"
        )
        db.add(run)
        await db.commit()

        creation_res = await create_hotfix_followup_tasks(db, run.id)
        for t in creation_res["tasks"]:
            await complete_hotfix_task(db, t["id"], actor_id="human:engineer", notes="Finished cleanly")

        # Simulate check at 30 hours later
        simulated_time = datetime.now(timezone.utc) + timedelta(hours=30)
        sla_res = await check_hotfix_documentation_sla(db, run.id, check_time=simulated_time)

        assert sla_res["is_overdue"] is False
        assert sla_res["all_completed"] is True
        assert sla_res["pending_count"] == 0
        assert sla_res.get("alert_created", False) is False


@pytest.mark.asyncio
async def test_portfolio_weekly_report_generation_and_strict_redline():
    """
    CRITICAL ACCEPTANCE TEST:
    Portfolio weekly report reads from all product DBs, outputs recommendations ONLY,
    and enforces the strict redline against autonomous fund transfer or termination.
    """
    async with AsyncSessionLocal() as db:
        init = StrategicInitiative(
            id=f"init_port_{uuid.uuid4().hex[:6]}",
            name="Global Expansion Matrix",
            target_market="欧美与东南亚",
            budget=50000.0
        )
        db.add(init)

        # Product 1: healthy growth
        p1 = Product(
            id=f"p1_{uuid.uuid4().hex[:6]}",
            initiative_id=init.id,
            name="Widget Camera",
            code=f"WC_{uuid.uuid4().hex[:4]}",
            platform="ios",
            client_zero_inference=True,
            stage="growth",
            budget_allocated=20000.0,
            actual_spent=6500.0,
            revenue_contribution=12000.0,
            kpi_name="D7 Retention",
            kpi_target=30.0,
            kpi_actual=34.2,
            kpi_unit="%"
        )
        # Product 2: paused on stop-loss
        p2 = Product(
            id=f"p2_{uuid.uuid4().hex[:6]}",
            initiative_id=init.id,
            name="Crypto Scanner",
            code=f"CS_{uuid.uuid4().hex[:4]}",
            platform="android",
            client_zero_inference=False,
            stage="paused",
            budget_allocated=15000.0,
            actual_spent=14200.0,
            revenue_contribution=1800.0,
            kpi_name="CAC",
            kpi_target=1.5,
            kpi_actual=3.8,
            kpi_unit="USD"
        )
        db.add_all([p1, p2])
        await db.commit()

        # Generate portfolio weekly report
        report_res = await generate_portfolio_weekly_report(db, initiative_id=init.id)

        assert report_res["status"] == "generated"
        assert report_res["total_products"] >= 2
        assert report_res["paused_products"] >= 1

        md = report_res["markdown_report"]

        # 1. Two-layer deliverable format
        assert "## 负责人 30 秒拍板摘要卡 (Executive Gate)" in md
        assert "## 完整执行细节 (Execution Reference)" in md

        # 2. Strict Redline Banner
        assert "组合层战略红线 (Strategic Redline Guardrail)" in md
        assert "严禁系统或 Agent 自动执行加码、砍项目或跨产品划转资金" in md
        assert "人类战略决策人" in md

        # 3. Product table entries
        assert p1.code in md
        assert p2.code in md
        assert "Widget Camera" in md
        assert "Crypto Scanner" in md

        # 4. Physical report file persistence
        file_path = Path(report_res["report_file_path"])
        assert file_path.exists()
        assert len(file_path.read_text(encoding="utf-8")) > 500


@pytest.mark.asyncio
async def test_api_hotfix_and_portfolio_endpoints():
    """Verify REST API endpoints for hotfix lifecycle and portfolio weekly report."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a product and a hotfix run
        auth_pkg = generate_default_authorization_dict(
            product_code=f"api_hf_{uuid.uuid4().hex[:6]}",
            product_name="API Hotfix Product",
            budget_allocated=7000.0
        )
        create_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "API Hotfix Product",
                "code": auth_pkg["project_id"],
                "authorization_package": auth_pkg
            },
            headers={"X-ModuFlow-Actor": "human:bob"}
        )
        assert create_resp.status_code == 200
        prod_id = create_resp.json()["id"]

        run_resp = await client.post(
            "/api/v1/runs",
            json={"name": "Hotfix V1.0.2", "product_id": prod_id, "template_id": "hotfix"}
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["id"]

        # 2. Trigger hotfix release endpoint
        rel_resp = await client.post(
            f"/api/v1/runs/{run_id}/hotfix-release",
            headers={"X-ModuFlow-Actor": "human:bob"}
        )
        assert rel_resp.status_code == 200
        rel_data = rel_resp.json()
        assert rel_data["tasks_count"] == 3

        # 3. Query hotfix tasks endpoint
        tasks_resp = await client.get(f"/api/v1/runs/{run_id}/hotfix-tasks")
        assert tasks_resp.status_code == 200
        tasks_data = tasks_resp.json()
        assert tasks_data["has_tasks"] is True
        assert tasks_data["is_overdue"] is False
        assert tasks_data["pending_count"] == 3

        task_id = tasks_data["tasks"][0]["id"]

        # 4. Complete a hotfix task endpoint
        comp_resp = await client.post(
            f"/api/v1/hotfix-tasks/{task_id}/complete",
            json={"notes": "Completed by PM"},
            headers={"X-ModuFlow-Actor": "human:pm_lead"}
        )
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert comp_data["status"] == "completed"
        assert comp_data["completed_by"] == "human:pm_lead"

        # 5. Query portfolio weekly report endpoint
        port_resp = await client.get("/api/v1/portfolio/weekly-report")
        assert port_resp.status_code == 200
        port_data = port_resp.json()
        assert port_data["status"] == "generated"
        assert "markdown_report" in port_data
        assert "严禁系统或 Agent 自动执行加码、砍项目或跨产品划转资金" in port_data["markdown_report"]
