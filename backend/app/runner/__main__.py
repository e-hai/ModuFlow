"""工序执行器进程：`python -m backend.app.runner`

后端只往 `orchestration_jobs` 排队，CLI 一律在这里跑。于是：
- 某个产品跑工序时，后端照旧响应其他产品的请求；
- 重启后端不必等工序跑完；
- 这个进程退出时会结束自己启动的 CLI，并把任务标成中断，人能看出来要重跑。
"""

import asyncio
import signal
from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, Base, engine
from backend.app.services import job_queue

HEARTBEAT_SECONDS = 15

_stopping = asyncio.Event()


def _log(message: str) -> None:
    print(f"[runner {datetime.now():%H:%M:%S}] {message}", flush=True)


async def _beat_until_done(job_id: str, work: asyncio.Task) -> None:
    """工序可能跑好几分钟，期间持续写心跳，别被当成失联任务重排。"""
    while not work.done():
        await asyncio.sleep(HEARTBEAT_SECONDS)
        if work.done():
            return
        job_queue.touch_runner_pulse()
        async with AsyncSessionLocal() as db:
            await job_queue.heartbeat(db, job_id)


async def _run_one() -> bool:
    """领一个任务并跑完。返回是否领到了任务。"""
    from backend.app.adapters.cli_adapter import apply_saved_cli_settings

    async with AsyncSessionLocal() as db:
        await apply_saved_cli_settings(db)
        job = await job_queue.claim_next(db)
        if job is None:
            return False
        job_id, label = job.id, f"{job.task} {list(job.args or [])}"

        _log(f"开始 {label}")
        work = asyncio.create_task(job_queue.run_claimed(db, job))
        beat = asyncio.create_task(_beat_until_done(job_id, work))
        try:
            outcome = await work
        finally:
            beat.cancel()
    _log(f"结束 {label} → {outcome}")
    return True


async def _shutdown(worker: str) -> None:
    from backend.app.adapters.cli_adapter import terminate_live_cli_processes

    killed = await terminate_live_cli_processes()
    job_queue.RUNNER_PULSE_FILE.unlink(missing_ok=True)
    async with AsyncSessionLocal() as db:
        marked = await job_queue.interrupt_running_for(
            db, worker, "执行器已退出，本次工序没跑完，请重新派活。"
        )
    _log(f"已退出：结束 {killed} 个 CLI 进程，{marked} 个任务标为中断")


async def main() -> None:
    worker = job_queue.worker_identity()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stopping.set)

    # 执行器可能比后端先起来，自己把表建好，别在第一次领任务时报表不存在。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from backend.app.adapters.cli_adapter import apply_saved_cli_settings

    async with AsyncSessionLocal() as db:
        await apply_saved_cli_settings(db)
    model = settings.AGENT_CLI_MODEL or "CLI 默认"
    _log(f"已就绪（{worker}），CLI 命令 {settings.AGENT_CLI_COMMAND}，模型 {model}，轮询 {settings.RUNNER_POLL_SECONDS}s")
    async with AsyncSessionLocal() as db:
        requeued = await job_queue.reclaim_stale(db)
    if requeued:
        _log(f"把 {requeued} 个失联任务重新排队")

    try:
        while not _stopping.is_set():
            job_queue.touch_runner_pulse(worker)
            try:
                worked = await _run_one()
            except Exception as exc:
                _log(f"领任务失败：{type(exc).__name__}: {exc}")
                worked = False
            if worked:
                continue
            # 审批或检查若在半路被打断，工序会停在「等待检查」而队列是空的。空闲时把它捡回来。
            try:
                async with AsyncSessionLocal() as db:
                    resumed = await job_queue.resume_orphaned(db)
            except Exception as exc:
                _log(f"捡回中断工序失败：{type(exc).__name__}: {exc}")
                resumed = 0
            if resumed:
                _log(f"捡回 {resumed} 个停在半路的迭代")
                continue
            try:
                await asyncio.wait_for(_stopping.wait(), timeout=settings.RUNNER_POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
    finally:
        await _shutdown(worker)
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
