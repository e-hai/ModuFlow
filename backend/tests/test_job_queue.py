"""派活只排队，CLI 跑在执行器进程里：一个产品跑工序不再占住整个后端。"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.adapters.base import AgentEventType, AgentStreamEvent, BaseAgentAdapter
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.main import app
from backend.app.models.entities import Artifact, ModuleInstance, OrchestrationJob, Product, StrategicInitiative
from backend.app.services import agent_runner, job_queue
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.services.workflow_engine import create_workflow_run_from_template, seed_templates_if_empty
from backend.tests.conftest import TestingSessionLocal as AsyncSessionLocal
from backend.tests.conftest import ensure_test_product_authorization
from backend.tests.conftest import test_engine as engine

_SOM_DOC = (
    '{"monthly_search_volume": 120000, "target_capture_rate": 0.04, '
    '"blended_arpu_usd": 1.8, "source": "测试夹具：假设/待验证"}\n'
)


class _StageAdapter(BaseAgentAdapter):
    def __init__(self, outputs: Dict[str, str]):
        self.outputs = outputs
        self.calls: List[str] = []

    async def execute_task(self, task_id, workspace_dir, system_context, user_instruction,
                           message_type="instruction", metadata: Optional[Dict[str, Any]] = None):
        code = (metadata or {}).get("module_code", "")
        self.calls.append(code)
        event = AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED
        yield AgentStreamEvent(event_type=event, content=self.outputs.get(code, "没有可复核的数字。"))
        yield AgentStreamEvent(event_type=AgentEventType.DONE, content="done")

    async def cancel_task(self, task_id: str) -> bool:
        return True


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)


async def _make_product(db, suffix: str) -> Product:
    init = StrategicInitiative(id=f"jq-init-{suffix}", name="派活队列测试")
    prod = Product(
        id=f"jq-p-{suffix}", initiative_id=init.id, name="队列产品",
        code=f"JQ-{suffix.upper()}", stage="growth", shadow_mode=False,
    )
    db.add_all([init, prod])
    await db.commit()
    ensure_test_product_authorization(init.id, prod.code)
    return prod


async def _make_run(db, suffix: str):
    prod = await _make_product(db, suffix)
    run = await create_workflow_run_from_template(db, prod.id, "full-product-launch", f"Sprint-{suffix}")
    return prod, run


@pytest.mark.asyncio
async def test_creating_a_run_queues_work_without_running_the_cli(monkeypatch):
    adapter = _StageAdapter({"01": _SOM_DOC})
    monkeypatch.setattr(agent_runner, "get_agent_adapter", lambda adapter_type=None: adapter)
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)

    async with AsyncSessionLocal() as db:
        prod = await _make_product(db, "http")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/runs", json={
            "product_id": prod.id, "template_id": "full-product-launch", "name": "Sprint-queued",
        })
        assert res.status_code == 200, res.text

    # The request returned with nothing dispatched; the job is waiting for the runner.
    assert adapter.calls == []
    async with AsyncSessionLocal() as db:
        jobs = (await db.execute(select(OrchestrationJob))).scalars().all()
        assert [j.status for j in jobs] == ["queued"]
        assert jobs[0].task == "advance_run"

        assert len(await job_queue.drain(db)) == 1
        assert adapter.calls[:1] == ["01"]
        refreshed = (await db.execute(select(OrchestrationJob))).scalars().all()
        assert [j.status for j in refreshed] == ["done"]


@pytest.mark.asyncio
async def test_same_request_twice_queues_one_job(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "dedup")
        first = await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        second = await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        assert first is not None and second is not None
        assert first.id == second.id
        first.status = "running"
        await db.commit()
        third = await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        assert third is not None and third.id == first.id
        assert len((await db.execute(select(OrchestrationJob))).scalars().all()) == 1

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            watched = await ac.get(f"/api/v1/orchestration-jobs/{first.id}")
        assert watched.status_code == 200
        assert watched.json()["status"] == "running"
        assert watched.json()["id"] == first.id


@pytest.mark.asyncio
async def test_a_failing_stage_only_marks_its_own_job(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)

    async def _boom(db, run_id):
        raise RuntimeError("CLI 挂了")

    monkeypatch.setattr("backend.app.services.orchestrator.advance_run", _boom)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "fail")
        await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        done = await job_queue.drain(db)
        assert len(done) == 1
        job = (await db.execute(select(OrchestrationJob))).scalars().one()
        assert job.status == "failed"
        assert "CLI 挂了" in job.error


@pytest.mark.asyncio
async def test_queue_is_skipped_when_orchestration_is_off(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", False)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "off")
        assert await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id) is None
        assert (await db.execute(select(OrchestrationJob))).scalars().all() == []


@pytest.mark.asyncio
async def test_dead_runner_leaves_the_job_recoverable(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "stale")
        await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        claimed = await job_queue.claim_next(db, worker="host:999")
        assert claimed is not None and claimed.status == "running"

        # No heartbeat for longer than the limit means the runner died mid-stage.
        claimed.heartbeat_at = datetime.utcnow() - timedelta(seconds=settings.RUNNER_STALE_SECONDS + 60)
        db.add(claimed)
        await db.commit()

        assert await job_queue.reclaim_stale(db) == 1
        again = (await db.execute(select(OrchestrationJob))).scalars().one()
        assert again.status == "queued" and again.worker is None


@pytest.mark.asyncio
async def test_runner_exit_marks_its_running_job_interrupted(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "sigterm")
        await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        await job_queue.claim_next(db, worker="host:555")

        assert await job_queue.interrupt_running_for(db, "host:555", "执行器已退出") == 1
        job = (await db.execute(select(OrchestrationJob))).scalars().one()
        assert job.status == "interrupted"
        assert job.finished_at is not None


@pytest.mark.asyncio
async def test_one_run_is_not_advanced_by_two_runners_at_once(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "serial")
        await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        await job_queue.enqueue(db, "on_artifact_created", "mod-x", "agent", run_id=run.id)

        first = await job_queue.claim_next(db, worker="host:1")
        second = await job_queue.claim_next(db, worker="host:2")
        assert first is not None
        assert second is None


@pytest.mark.asyncio
async def test_a_revision_killed_midway_does_not_spend_the_budget():
    from backend.app.models.entities import CollaborationSession, SessionMessage
    from backend.app.services import orchestrator

    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "revbudget")
        mod = (await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id, ModuleInstance.module_code == "01")
        )).scalar_one()
        session = CollaborationSession(module_id=mod.id, title="预算")
        db.add(session)
        await db.commit()
        await db.refresh(session)

        def _msg(at: datetime, message_type: str, kind: str, role: str = "agent") -> SessionMessage:
            return SessionMessage(
                session_id=session.id, sender="lead", sender_role=role, message_type=message_type,
                content=kind, metadata_json={"orchestrator": kind}, created_at=at,
            )

        base = datetime(2026, 10, 29, 3, 0, 0)
        db.add(_msg(base, "instruction", "human_resume", role="system"))
        db.add(_msg(base + timedelta(seconds=1), "feedback", "revision"))
        await db.commit()
        assert await orchestrator._revisions_since_boundary(db, session.id) == 0

        db.add(_msg(base + timedelta(seconds=2), "error", "agent_error"))
        await db.commit()
        assert await orchestrator._revisions_since_boundary(db, session.id) == 1


@pytest.mark.asyncio
async def test_idle_runner_resumes_a_stage_left_waiting_and_stops_after_failure(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    from backend.app.services import orchestrator

    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "resume")
        assert run.id in await orchestrator.runs_waiting_for_push(db)

        assert await job_queue.resume_orphaned(db) == 1
        assert await job_queue.resume_orphaned(db) == 0

        job = (await db.execute(select(OrchestrationJob))).scalars().one()
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        db.add(job)
        await db.commit()
        assert await job_queue.resume_orphaned(db) == 0

        job.status = "interrupted"
        db.add(job)
        await db.commit()
        assert await job_queue.resume_orphaned(db) == 1


@pytest.mark.asyncio
async def test_status_tells_the_human_work_is_queued_with_no_runner(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    monkeypatch.setattr(job_queue, "RUNNER_PULSE_FILE", tmp_path / "runner.pulse")
    from backend.app.services import orchestrator

    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "status")
        await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)

        # No runner has ever reported in: queued work would sit there forever.
        status = await orchestrator.get_run_orchestration_status(db, run.id)
        assert status["queue"]["queued"] == 1
        assert status["queue"]["running"] == 0
        assert status["queue"]["runner_alive"] is False

        job_queue.touch_runner_pulse("host:42")
        status = await orchestrator.get_run_orchestration_status(db, run.id)
        assert status["queue"]["runner_alive"] is True


@pytest.mark.asyncio
async def test_a_running_job_shows_the_waiting_stage_as_in_progress(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    from backend.app.services import orchestrator

    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "busy")
        stage = (await db.execute(select(ModuleInstance).where(
            ModuleInstance.run_id == run.id, ModuleInstance.module_code == "01"
        ))).scalar_one()
        db.add(Artifact(
            module_id=stage.id, version=1, title="工序 01", content="草稿", content_hash="busy",
        ))
        db.add(OrchestrationJob(
            task="on_artifact_created", args=["mod", "human_confirmed"],
            run_id=run.id, status="running", requested_by="human:submit",
        ))
        await db.commit()

        status = await orchestrator.get_run_orchestration_status(db, run.id)
        current = status["current_stage"]
        assert current["module_code"] == "01"
        assert current["state"] == "running"
        assert current["detail"] == "正在检查这一版交付物"


@pytest.mark.asyncio
async def test_task_error_is_stored_in_full_on_the_job(monkeypatch):
    long_error = "Agent CLI 执行出错 " + ("y" * 500)

    async def boom(db, run_id):
        return {"status": "idle", "task_error": long_error}

    monkeypatch.setattr(settings, "ORCHESTRATOR_ENABLED", True)
    monkeypatch.setattr(job_queue, "_resolve", lambda task: boom)
    async with AsyncSessionLocal() as db:
        _prod, run = await _make_run(db, "taskerr")
        await job_queue.enqueue(db, "advance_run", run.id, run_id=run.id)
        claimed = await job_queue.claim_and_run_once(db)
        fresh = (await db.execute(select(OrchestrationJob).where(OrchestrationJob.id == claimed.id))).scalar_one()
        assert fresh.status == "done"
        assert fresh.error == long_error
