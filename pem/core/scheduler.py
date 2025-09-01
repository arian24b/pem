"""Scheduler manager for handling background job execution."""

import asyncio
import contextlib
import logging
import threading
from datetime import UTC, datetime
from typing import Any, Literal

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from pem.core.executor import Executor
from pem.db.database import SessionLocal
from pem.db.models import Job
from pem.settings import DATABASE_URL, get_optimized_config

ScheduleType = Literal["once", "interval", "cron", "until_done"]

# Set up logging for better performance monitoring
logger = logging.getLogger(__name__)

# Get optimized configuration
config = get_optimized_config()
JOB_CACHE_SIZE = config["job_cache_size"]
EXECUTION_TIMEOUT = 300  # 5 minutes

# Job cache for better performance with size limit
_job_cache = {}
_cache_lock = threading.Lock()


def _get_cached_job(job_id: int) -> Job | None:
    """Get job from cache or database with LRU-style management."""
    with _cache_lock:
        if job_id in _job_cache:
            # Move to end (most recently accessed)
            job = _job_cache.pop(job_id)
            _job_cache[job_id] = job
            return job

    # Not in cache, load from database
    try:
        # Use sync session for scheduler compatibility
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Create sync engine for scheduler operations
        sync_engine = create_engine(DATABASE_URL.replace("aiosqlite", "sqlite"))
        sync_session = sessionmaker(bind=sync_engine)

        with sync_session() as session:
            job = session.query(Job).get(job_id)
            if job:
                with _cache_lock:
                    # Implement cache size limit
                    if len(_job_cache) >= JOB_CACHE_SIZE:
                        # Remove oldest item (first item)
                        oldest_key = next(iter(_job_cache))
                        del _job_cache[oldest_key]
                    _job_cache[job_id] = job
            return job
    except Exception as e:
        logger.exception(f"Failed to load job {job_id}: {e}")
        return None


def _invalidate_job_cache(job_id: int) -> None:
    """Remove job from cache."""
    with _cache_lock:
        _job_cache.pop(job_id, None)


async def _execute_job_async(job_id: int) -> dict[str, Any]:
    """Execute a job asynchronously with optimized database access."""
    job = _get_cached_job(job_id)
    if not job:
        return {"status": "FAILED", "error": "Job not found"}

    try:
        executor = Executor(job)
        return await executor.execute()
    except Exception as e:
        logger.exception(f"Job execution failed for job {job_id}: {e}")
        return {"status": "FAILED", "error": str(e)}


def execute_job_standalone(job_id: int) -> dict[str, Any]:
    """Optimized standalone function to execute a job."""
    # Reuse existing event loop if available
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an event loop, create a task
        future = asyncio.run_coroutine_threadsafe(_execute_job_async(job_id), loop)
        return future.result(timeout=300)  # 5 minute timeout
    except RuntimeError:
        # No running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_execute_job_async(job_id))
        finally:
            loop.close()


def execute_until_done_standalone(job_id: int, max_retries: int = 10, retry_interval: int = 60) -> None:
    """Optimized standalone function to execute a job repeatedly until it succeeds."""
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        logger.info(f"Attempt {attempt}/{max_retries} for job {job_id}")

        result = execute_job_standalone(job_id)

        if result.get("status") == "SUCCESS":
            logger.info(f"Job {job_id} completed successfully after {attempt} attempts")
            return

        if attempt < max_retries:
            logger.info(f"Job {job_id} failed, retrying in {retry_interval} seconds...")
            import time

            time.sleep(retry_interval)

    logger.error(f"Job {job_id} failed after {max_retries} attempts")


class SchedulerManager:
    """Manages background scheduling of jobs."""

    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_jobstore(SQLAlchemyJobStore(url=DATABASE_URL), "default")
        self.running_jobs = {}  # Track running until_done jobs
        self._setup_scheduler()

    def _setup_scheduler(self) -> None:
        """Initialize and start the scheduler."""
        with contextlib.suppress(Exception):
            self.scheduler.start()

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def _execute_job_async(self, job_id: int) -> dict[str, Any]:
        """Execute a job asynchronously."""
        async with SessionLocal() as db:
            try:
                from sqlalchemy import select

                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()

                if not job:
                    return {"status": "FAILED", "error": "Job not found"}

                return await Executor(job).execute()
            except Exception as e:
                logger.exception(f"Database error: {e}")
                return {"status": "FAILED", "error": str(e)}

    def _execute_job_sync(self, job_id: int) -> dict[str, Any]:
        """Execute a job synchronously (wrapper for scheduler)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._execute_job_async(job_id))
        finally:
            loop.close()

    def _execute_until_done(self, job_id: int, max_retries: int = 10, retry_interval: int = 60) -> None:
        """Execute a job repeatedly until it succeeds or max retries reached."""
        attempt = 0
        while attempt < max_retries:
            attempt += 1

            result = self._execute_job_sync(job_id)

            if result["status"] == "SUCCESS":
                # Remove from running jobs tracker
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
                break
            if attempt < max_retries:
                threading.Event().wait(retry_interval)
            elif job_id in self.running_jobs:
                del self.running_jobs[job_id]

    def schedule_job(self, job_id: int, schedule_type: ScheduleType, **kwargs) -> str:
        """Schedule a job with different scheduling options.

        Args:
            job_id: The job ID to schedule
            schedule_type: Type of scheduling (once, interval, cron, until_done)
            **kwargs: Additional scheduling parameters

        Returns:
            scheduler_job_id: The APScheduler job ID

        """
        scheduler_job_id = f"pem_job_{schedule_type}_{job_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        match schedule_type:
            case "once":
                # Schedule to run once at a specific time
                run_date = kwargs.get("run_date")
                if isinstance(run_date, str):
                    run_date = datetime.fromisoformat(run_date)

                self.scheduler.add_job(
                    func=execute_job_standalone,
                    trigger="date",
                    run_date=run_date,
                    args=[job_id],
                    id=scheduler_job_id,
                    replace_existing=True,
                )

            case "interval":
                # Schedule to run at regular intervals
                self.scheduler.add_job(
                    func=execute_job_standalone,
                    trigger="interval",
                    seconds=kwargs.get("seconds", 0),
                    minutes=kwargs.get("minutes", 0),
                    hours=kwargs.get("hours", 0),
                    days=kwargs.get("days", 0),
                    args=[job_id],
                    id=scheduler_job_id,
                    replace_existing=True,
                )

            case "cron":
                # Schedule using cron expression
                cron_kwargs = {
                    k: v for k, v in kwargs.items() if k in ["second", "minute", "hour", "day", "month", "day_of_week"]
                }

                self.scheduler.add_job(
                    func=execute_job_standalone,
                    trigger="cron",
                    args=[job_id],
                    id=scheduler_job_id,
                    replace_existing=True,
                    **cron_kwargs,
                )

            case "until_done":
                # Run in background thread until success
                max_retries = kwargs.get("max_retries", 10)
                retry_interval = kwargs.get("retry_interval", 60)

                # Track this job
                self.running_jobs[job_id] = {
                    "scheduler_job_id": scheduler_job_id,
                    "start_time": datetime.now(UTC),
                    "max_retries": max_retries,
                    "retry_interval": retry_interval,
                }

                # Run in a separate thread
                thread = threading.Thread(
                    target=execute_until_done_standalone,
                    args=[job_id, max_retries, retry_interval],
                    daemon=True,
                )
                thread.start()

        return scheduler_job_id

    def list_scheduled_jobs(self) -> list[dict]:
        """List all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith("pem_job_"):
                jobs.append(
                    {
                        "id": job.id,
                        "next_run": job.next_run_time,
                        "trigger": str(job.trigger),
                        "func": job.func.__name__,
                    },
                )

        # Add until_done jobs
        for info in self.running_jobs.values():
            jobs.append(
                {
                    "id": info["scheduler_job_id"],
                    "next_run": "running until done",
                    "trigger": "until_done",
                    "func": "_execute_until_done",
                    "start_time": info["start_time"],
                    "max_retries": info["max_retries"],
                },
            )

        return jobs

    def cancel_job(self, scheduler_job_id: str) -> bool:
        """Cancel a scheduled job."""
        try:
            # Check if it's an until_done job
            for job_id, info in list(self.running_jobs.items()):
                if info["scheduler_job_id"] == scheduler_job_id:
                    del self.running_jobs[job_id]
                    return True

            # Remove from scheduler
            self.scheduler.remove_job(scheduler_job_id)
            return True
        except Exception:
            return False


# Global scheduler instance
scheduler_manager = SchedulerManager()
