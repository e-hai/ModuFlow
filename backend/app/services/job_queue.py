"""派活队列。

后端只往 `orchestration_jobs` 写一行就返回，不在请求进程里跑 CLI。
独立的执行器进程（`python -m backend.app.runner`）领任务并执行工序，
所以某个产品跑工序时，后端照旧响应其他产品的请求，重启也不会被工序拖住。
"""

import os
import socket
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.entities import OrchestrationJob

ACTIVE_STATUSES = ("queued", "running")

# 任务名到编排入口的映射。只有这张表里的任务能被执行器跑。
TASKS = {
    "advance_run": "advance_run",
    "on_artifact_created": "on_artifact_created",
    "on_gate_reviewed": "on_gate_reviewed",
    "finalize_and_advance": "finalize_and_advance",
    "resolve_dispute": "resolve_dispute",
}


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


# 执行器的在岗信号。后端和执行器是两个进程，队列里没有"在跑的任务"时
# 光看任务行判断不出执行器死活，所以它每轮循环都刷一下这个文件的时间戳。
RUNNER_PULSE_FILE = settings.DATA_DIR / "runner.pulse"


def touch_runner_pulse(worker: Optional[str] = None) -> None:
    try:
        RUNNER_PULSE_FILE.write_text(
            f"{worker or worker_identity()}\n{datetime.utcnow().isoformat()}\n", encoding="utf-8"
        )
    except OSError:
        pass


def runner_is_alive() -> bool:
    try:
        seen = datetime.utcfromtimestamp(RUNNER_PULSE_FILE.stat().st_mtime)
    except OSError:
        return False
    return seen >= datetime.utcnow() - timedelta(seconds=settings.RUNNER_STALE_SECONDS)


def _resolve(task: str):
    from backend.app.services import orchestrator

    if task not in TASKS:
        raise ValueError(f"未注册的编排任务：{task}")
    return getattr(orchestrator, TASKS[task])


async def enqueue(
    db: AsyncSession,
    task: str,
    *args: Any,
    run_id: Optional[str] = None,
    requested_by: str = "system",
) -> Optional[OrchestrationJob]:
    """排一次派活。同样的任务已在排队或正在跑时不重复排。"""
    from backend.app.services import orchestrator

    if not orchestrator.orchestration_enabled():
        return None
    _resolve(task)

    arg_list = [str(a) for a in args]
    existing = (await db.execute(select(OrchestrationJob).where(and_(
        OrchestrationJob.task == task,
        OrchestrationJob.status.in_(("queued", "running")),
    )))).scalars().all()
    for job in existing:
        if list(job.args or []) == arg_list:
            return job

    job = OrchestrationJob(
        task=task,
        args=arg_list,
        run_id=run_id,
        requested_by=requested_by,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def claim_next(db: AsyncSession, worker: Optional[str] = None) -> Optional[OrchestrationJob]:
    """领一个任务。同一迭代已有任务在跑时跳过，避免两个执行器同时推同一条流水线。"""
    worker = worker or worker_identity()
    busy_runs = {
        row for (row,) in (await db.execute(
            select(OrchestrationJob.run_id).where(and_(
                OrchestrationJob.status == "running",
                OrchestrationJob.run_id.is_not(None),
            ))
        )).all()
    }
    candidates = (await db.execute(
        select(OrchestrationJob)
        .where(OrchestrationJob.status == "queued")
        .order_by(OrchestrationJob.created_at.asc())
    )).scalars().all()

    for job in candidates:
        if job.run_id and job.run_id in busy_runs:
            continue
        now = datetime.utcnow()
        claimed = await db.execute(
            update(OrchestrationJob)
            .where(and_(OrchestrationJob.id == job.id, OrchestrationJob.status == "queued"))
            .values(
                status="running",
                worker=worker,
                started_at=now,
                heartbeat_at=now,
                attempts=OrchestrationJob.attempts + 1,
            )
        )
        await db.commit()
        if claimed.rowcount:
            await db.refresh(job)
            return job
    return None


async def job_view(db: AsyncSession, job_id: str) -> Optional[Dict[str, Any]]:
    """One queue row, so the decision center can wait for a click to finish."""
    job = (await db.execute(
        select(OrchestrationJob).where(OrchestrationJob.id == job_id)
    )).scalar_one_or_none()
    if job is None:
        return None
    return {
        "id": job.id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "runner_alive": runner_is_alive(),
    }


async def heartbeat(db: AsyncSession, job_id: str) -> None:
    await db.execute(
        update(OrchestrationJob)
        .where(OrchestrationJob.id == job_id)
        .values(heartbeat_at=datetime.utcnow())
    )
    await db.commit()


async def finish(
    db: AsyncSession,
    job_id: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    await db.execute(
        update(OrchestrationJob)
        .where(OrchestrationJob.id == job_id)
        .values(
            status=status,
            result=(result or "")[:2000] or None,
            error=(error or "")[:20000] or None,
            finished_at=datetime.utcnow(),
        )
    )
    await db.commit()


async def run_claimed(db: AsyncSession, job: OrchestrationJob) -> str:
    """跑一个已领到的任务。失败只记在这一行上，不影响其他产品。"""
    try:
        outcome = await _resolve(job.task)(db, *(job.args or []))
        task_error = outcome.get("task_error") if isinstance(outcome, dict) else None
        await finish(
            db, job.id, "done", result=str(outcome),
            error=task_error if isinstance(task_error, str) and task_error else None,
        )
        return "done"
    except Exception as exc:
        traceback.print_exc()
        await finish(db, job.id, "failed", error=f"{type(exc).__name__}: {exc}")
        return "failed"


async def claim_and_run_once(db: AsyncSession, worker: Optional[str] = None) -> Optional[OrchestrationJob]:
    """执行器的一轮循环，也是测试里把队列跑干的入口。"""
    job = await claim_next(db, worker)
    if job is None:
        return None
    await run_claimed(db, job)
    return job


async def drain(db: AsyncSession, limit: int = 50, worker: Optional[str] = None) -> List[OrchestrationJob]:
    done: List[OrchestrationJob] = []
    for _ in range(limit):
        job = await claim_and_run_once(db, worker)
        if job is None:
            break
        done.append(job)
    return done


async def reclaim_stale(db: AsyncSession, stale_seconds: Optional[int] = None) -> int:
    """执行器被杀或断电后，`running` 的任务不会自己恢复，重新排一次队。"""
    limit = stale_seconds or settings.RUNNER_STALE_SECONDS
    cutoff = datetime.utcnow() - timedelta(seconds=limit)
    stale = (await db.execute(select(OrchestrationJob).where(and_(
        OrchestrationJob.status == "running",
        OrchestrationJob.heartbeat_at.is_not(None),
        OrchestrationJob.heartbeat_at < cutoff,
    )))).scalars().all()
    for job in stale:
        job.status = "queued"
        job.worker = None
        job.started_at = None
        job.heartbeat_at = None
        job.error = f"执行器失联，已重新排队（上次心跳早于 {limit} 秒前）"
        db.add(job)
    if stale:
        await db.commit()
    return len(stale)


async def interrupt_running_for(db: AsyncSession, worker: str, note: str) -> int:
    """执行器收到退出信号时，把自己正在跑的任务标成中断，人能看出来需要重跑。"""
    running = (await db.execute(select(OrchestrationJob).where(and_(
        OrchestrationJob.status == "running",
        OrchestrationJob.worker == worker,
    )))).scalars().all()
    for job in running:
        job.status = "interrupted"
        job.error = note
        job.finished_at = datetime.utcnow()
        db.add(job)
    if running:
        await db.commit()
    return len(running)


async def resume_orphaned(db: AsyncSession) -> int:
    """把停在半路、队列里却没任务的迭代重新排上。

    最近一次任务是失败的就不再自动重试，免得同一个错误把 CLI 反复拉起来；
    那种情况等人点「立即推进」。
    """
    from backend.app.services import orchestrator

    if not orchestrator.orchestration_enabled():
        return 0
    resumed = 0
    for run_id in await orchestrator.runs_waiting_for_push(db):
        jobs = (await db.execute(
            select(OrchestrationJob)
            .where(OrchestrationJob.run_id == run_id)
            .order_by(OrchestrationJob.created_at.desc())
        )).scalars().all()
        if any(job.status in ACTIVE_STATUSES for job in jobs):
            continue
        if jobs and jobs[0].status == "failed":
            continue
        job = await enqueue(db, "advance_run", run_id, run_id=run_id, requested_by="runner:resume")
        if job is not None:
            resumed += 1
    return resumed


async def queue_snapshot(db: AsyncSession, run_id: Optional[str] = None) -> Dict[str, Any]:
    """给界面看的队列状态：排了几个、谁在跑、执行器是否还活着。"""
    stmt = select(OrchestrationJob).where(OrchestrationJob.status.in_(ACTIVE_STATUSES))
    if run_id:
        stmt = stmt.where(OrchestrationJob.run_id == run_id)
    jobs = (await db.execute(stmt.order_by(OrchestrationJob.created_at.asc()))).scalars().all()
    running = [j for j in jobs if j.status == "running"]
    queued = [j for j in jobs if j.status == "queued"]
    return {
        "queued": len(queued),
        "running": len(running),
        "runner_alive": runner_is_alive(),
        "current": (
            {
                "job_id": running[0].id,
                "task": running[0].task,
                "worker": running[0].worker,
                "started_at": running[0].started_at,
            }
            if running else None
        ),
    }
