"""Scheduler manager for handling background job execution."""

import asyncio
import contextlib
import threading
from datetime import datetime
from typing import Any, Literal

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from pem.core.executor import Executor
from pem.db.database import SessionLocal
from pem.db.models import Job
from pem.settings import DATABASE_URL

ScheduleType = Literal["once", "interval", "cron", "until_done"]


def execute_job_standalone(job_id: int) -> dict[str, Any]:
    """Standalone function to execute a job (for scheduler serialization)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_execute_job_async(job_id))
    finally:
        loop.close()


async def _execute_job_async(job_id: int) -> dict[str, Any]:
    """Execute a job asynchronously."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"status": "FAILED", "error": "Job not found"}

        executor = Executor(job)
        return await executor.execute()
    finally:
        db.close()


def execute_until_done_standalone(job_id: int, max_retries: int = 10, retry_interval: int = 60) -> None:
    """Standalone function to execute a job repeatedly until it succeeds."""
    attempt = 0
    while attempt < max_retries:
        attempt += 1

        result = execute_job_standalone(job_id)

        if result["status"] == "SUCCEEDED":
            break
        if attempt < max_retries:
            threading.Event().wait(retry_interval)
        else:
            pass


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
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {"status": "FAILED", "error": "Job not found"}

            executor = Executor(job)
            return await executor.execute()
        finally:
            db.close()

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

            if result["status"] == "SUCCEEDED":
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
        scheduler_job_id = f"pem_job_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if schedule_type == "once":
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

        elif schedule_type == "interval":
            # Schedule to run at regular intervals
            seconds = kwargs.get("seconds", 0)
            minutes = kwargs.get("minutes", 0)
            hours = kwargs.get("hours", 0)
            days = kwargs.get("days", 0)

            self.scheduler.add_job(
                func=execute_job_standalone,
                trigger="interval",
                seconds=seconds,
                minutes=minutes,
                hours=hours,
                days=days,
                args=[job_id],
                id=scheduler_job_id,
                replace_existing=True,
            )

        elif schedule_type == "cron":
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

        elif schedule_type == "until_done":
            # Run in background thread until success
            max_retries = kwargs.get("max_retries", 10)
            retry_interval = kwargs.get("retry_interval", 60)

            # Track this job
            self.running_jobs[job_id] = {
                "scheduler_job_id": scheduler_job_id,
                "start_time": datetime.now(),
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
