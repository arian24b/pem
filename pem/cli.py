import inspect
import signal
import threading
import time
from enum import StrEnum

from cfui import App, Arg, Fail, ui
from faker import Faker
from sqlalchemy.future import select

from pem.commands.config import register as register_config
from pem.commands.service import register as register_service
from pem.core.executor import Executor
from pem.core.scheduler import scheduler_manager
from pem.db.database import SessionLocal, create_db_and_tables
from pem.db.models import Job
from pem.logging_utils import configure_logging
from pem.service import (
    ensure_pem_installed,
    ensure_uv_installed,
    install_service,
    start_service,
    update_uv,
)


class ScheduleTypeEnum(StrEnum):
    """Schedule type enumeration for CLI."""

    once = "once"
    interval = "interval"
    cron = "cron"
    until_done = "until_done"


app = App(
    "pem",
    repo="https://github.com/arian24b/pem",
    pypi="pemexe",
    description="Python Execution Manager - Schedule and execute Python scripts and projects with ease",
)
register_config(app)
register_service(app)


def command(name, help, args=(), db=True, **kw):  # noqa: A002
    """Register `fn(**options)` (options taken from the namespace by name); db=True inits the database."""

    def deco(fn):
        params = list(inspect.signature(fn).parameters)

        async def runner(a):
            if db:
                configure_logging()
                await create_db_and_tables()
            r = fn(**{k: getattr(a, k) for k in params})
            if inspect.isawaitable(r):
                await r

        app.command(name, help, args=args, **kw)(runner)
        return fn

    return deco


ID = Arg("-i", "--id", dest="job_id", type=int, help="Job ID")
NAME = Arg("-n", "--name", help="Job name")


async def find_job(session, job_id, name, verb):
    """Look a job up by --id or --name; ask for the name when neither was given."""
    if not job_id and not name:
        name = ui.need(None, "--name", f"Name of the job to {verb}")
    job = await session.get(Job, job_id) if job_id else await session.scalar(select(Job).filter_by(name=name))
    if job is None:
        raise Fail(f"Job with ID/Name '{job_id or name}' not found.", "Use `pem show` to list jobs.")
    return job


def report_result(result) -> None:
    ui.out(f"status:    {result['status']}\nexit code: {result['exit_code']}\nlog file:  {result['log_path']}")
    if result["status"] == "FAILED":
        ui.warning("Job execution failed. Check the log file for details.")
    else:
        ui.success("Job executed successfully.")


@command(
    "add",
    "Create a new job to execute Python scripts or projects",
    args=[
        Arg(
            "-p",
            "--path",
            dest="path",
            required=True,
            prompt="Path to a Python script or project directory",
            help="Path to Python script file or project directory",
        ),
        Arg("-n", "--name", help="Unique name for the job (auto-generated if not provided)"),
        Arg(
            "-s",
            "--script",
            dest="is_script",
            action="store_true",
            help="Treat as single Python script (default: project)",
        ),
        Arg("-w", "--with", dest="dependencies", action="append", help="Python dependencies to install (scripts only)"),
        Arg("-v", "--python", dest="python_version", type=float, help="Required Python version (scripts only)"),
        Arg(
            "-e",
            "--enabled",
            dest="is_enabled",
            action="store_const",
            const=True,
            default=True,
            help="Enable job for execution (default)",
        ),
        Arg("--disabled", dest="is_enabled", action="store_const", const=False, help="Create the job disabled"),
        Arg(
            "--auto-run",
            dest="auto_run",
            action="store_const",
            const=True,
            default=True,
            help="Execute immediately after creation (default)",
        ),
        Arg("--no-auto-run", dest="auto_run", action="store_const", const=False, help="Do not execute after creation"),
    ],
)
async def add_job(path, name, is_script, dependencies, python_version, is_enabled, auto_run) -> None:
    async with SessionLocal() as session:
        job = Job(
            name=name or Faker().first_name(),
            job_type="script" if is_script else "project",
            path=path,
            dependencies=dependencies,
            python_version=python_version,
            is_enabled=is_enabled,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        ui.success(f"Created job: {job.name}")

        if job.is_enabled and auto_run:
            ui.info("Job is enabled. Executing immediately...")
            try:
                report_result(await Executor(job).execute())
            except Exception as e:
                ui.error(f"Failed to execute job after creation: {e}")
        elif job.is_enabled:
            ui.hint("Job is enabled but auto-run is disabled. Use 'pem run' to execute manually.")
        else:
            ui.hint("Job is disabled. Enable it with 'pem edit --enabled' to allow execution.")


@command("show", "Display details of jobs (all jobs if no filter specified)", args=[NAME, ID], aliases=("jobs",))
async def show_jobs(name, job_id) -> None:
    async with SessionLocal() as session:
        if not job_id and not name:
            jobs = list((await session.execute(select(Job))).scalars().all())
        else:
            jobs = []
            if (job_id and (job := await session.get(Job, job_id))) or (
                name and (job := await session.scalar(select(Job).filter_by(name=name)))
            ):
                jobs.append(job)

        if jobs:
            ui.table(
                [
                    (
                        j.id,
                        j.name,
                        j.job_type,
                        "enabled" if j.is_enabled else "disabled",
                        j.path,
                        ", ".join(j.dependencies or []),
                        j.python_version or "",
                    )
                    for j in jobs
                ],
                ["ID", "Name", "Type", "Status", "Path", "Dependencies", "Python"],
            )
        elif job_id or name:
            raise Fail(f"Job with ID/Name '{job_id or name}' not found.")
        else:
            ui.warning("No jobs found. Use 'pem add' to create your first job.")


@command(
    "edit",
    "Update properties of an existing job",
    args=[
        ID,
        NAME,
        Arg("-p", "--path", help="New path for the job"),
        Arg("-s", "--script", dest="is_script", action="store_const", const=True, help="Change job type to script"),
        Arg("--project", dest="is_script", action="store_const", const=False, help="Change job type to project"),
        Arg("-w", "--with", dest="dependencies", action="append", help="Update dependencies (scripts only)"),
        Arg("-v", "--python", dest="python_version", type=float, help="Update Python version requirement"),
        Arg("-e", "--enabled", dest="is_enabled", action="store_const", const=True, help="Enable the job"),
        Arg("--disabled", dest="is_enabled", action="store_const", const=False, help="Disable the job"),
    ],
)
async def edit_job(job_id, name, path, is_script, dependencies, python_version, is_enabled) -> None:
    async with SessionLocal() as session:
        job = await find_job(session, job_id, None if job_id else name, "update")
        if job_id and name:
            job.name = name
        if path:
            job.path = path
        if is_script is not None:
            job.job_type = "script" if is_script else "project"
        if dependencies:
            job.dependencies = dependencies
        if python_version:
            job.python_version = python_version
        if is_enabled is not None:
            job.is_enabled = is_enabled

        await session.commit()
        await session.refresh(job)
        ui.success(f"Updated job: {job.id} - {job.name}")


@command("delete", "Remove a job permanently from the system", args=[ID, NAME])
async def delete_job(job_id, name) -> None:
    async with SessionLocal() as session:
        job = await find_job(session, job_id, name, "delete")
        await session.delete(job)
        await session.commit()
        ui.success(f"Deleted job: {job.id} - {job.name}")


@command(
    "run",
    "Execute a job immediately, with optional recurring schedule setup",
    args=[
        ID,
        NAME,
        Arg("-s", "--schedule", action="store_true", help="Set up recurring execution schedule"),
        Arg(
            "-t",
            "--type",
            dest="schedule_type",
            type=ScheduleTypeEnum,
            choices=list(ScheduleTypeEnum),
            default=ScheduleTypeEnum.interval,
            help="Schedule type (for --schedule)",
        ),
        Arg("-m", "--minutes", type=int, default=60, help="Interval in minutes (for interval scheduling)"),
    ],
)
async def run_job(job_id, name, schedule, schedule_type, minutes) -> None:
    async with SessionLocal() as session:
        job = await find_job(session, job_id, name, "execute")
        if not job.is_enabled:
            raise Fail(f"Job '{job.name}' is disabled.", "Enable it first with 'pem edit --enabled'.")

        ui.info(f"Executing job: {job.name}")
        report_result(await Executor(job).execute())

        if schedule:
            ui.info("Setting up recurring schedule...")
            await schedule_job(job_id=job.id, name=None, schedule_type=schedule_type, minutes=minutes)


@command(
    "cron",
    "Schedule a job for automatic execution using various timing options",
    aliases=("schedule",),
    args=[
        ID,
        NAME,
        Arg(
            "-t",
            "--type",
            dest="schedule_type",
            type=ScheduleTypeEnum,
            choices=list(ScheduleTypeEnum),
            default=ScheduleTypeEnum.once,
            help="Schedule type",
        ),
        Arg("-d", "--date", dest="run_date", help="Date/time to run (ISO format, e.g. '2024-01-01T10:00:00')"),
        Arg("--seconds", type=int, default=0, help="Interval in seconds"),
        Arg("--minutes", type=int, default=0, help="Interval in minutes"),
        Arg("--hours", type=int, default=0, help="Interval in hours"),
        Arg("--days", type=int, default=0, help="Interval in days"),
        Arg("--cron-minute", help="Cron minute field"),
        Arg("--cron-hour", help="Cron hour field"),
        Arg("--cron-day", help="Cron day field"),
        Arg("--cron-month", help="Cron month field"),
        Arg("--cron-dow", dest="cron_day_of_week", help="Cron day of week field"),
        Arg("--max-retries", type=int, default=10, help="Maximum retry attempts"),
        Arg("--retry-interval", type=int, default=60, help="Retry interval in seconds"),
    ],
)
async def schedule_job(
    job_id=None,
    name=None,
    schedule_type=ScheduleTypeEnum.once,
    run_date=None,
    seconds=0,
    minutes=0,
    hours=0,
    days=0,
    cron_minute=None,
    cron_hour=None,
    cron_day=None,
    cron_month=None,
    cron_day_of_week=None,
    max_retries=10,
    retry_interval=60,
) -> None:
    async with SessionLocal() as session:
        job = await find_job(session, job_id, name, "schedule")
        if not job.is_enabled:
            raise Fail(f"Job '{job.name}' is disabled.", "Enable it first with 'pem edit --enabled'.")

        kwargs = {}
        match schedule_type.value:
            case "once":
                run_date = ui.need(run_date, "--date", "Date/time to run (ISO, e.g. 2024-01-01T10:00:00)")
                kwargs["run_date"] = run_date
            case "interval":
                if not any([seconds, minutes, hours, days]):
                    raise Fail(
                        "For 'interval' scheduling, provide at least one interval.",
                        "Use --seconds, --minutes, --hours or --days.",
                    )
                kwargs.update({"seconds": seconds, "minutes": minutes, "hours": hours, "days": days})
            case "cron":
                cron_fields = {
                    "minute": cron_minute,
                    "hour": cron_hour,
                    "day": cron_day,
                    "month": cron_month,
                    "day_of_week": cron_day_of_week,
                }
                kwargs = {k: v for k, v in cron_fields.items() if v is not None}
                if not kwargs:
                    raise Fail(
                        "For 'cron' scheduling, provide at least one cron field.",
                        "Use --cron-minute, --cron-hour, --cron-day, ...",
                    )
            case "until_done":
                kwargs.update({"max_retries": max_retries, "retry_interval": retry_interval})

        try:
            scheduler_job_id = scheduler_manager.schedule_job(job.id, schedule_type.value, **kwargs)
        except Exception as e:
            raise Fail(f"Failed to schedule job: {e}") from e
        ui.success(f"Scheduled job '{job.name}'")
        ui.table([("Scheduler ID", scheduler_job_id), ("Schedule type", schedule_type.value), ("Details", kwargs)])


@command("crons", "List all jobs currently scheduled for automatic execution", aliases=("schedules",))
def list_scheduled_jobs() -> None:
    jobs = scheduler_manager.list_scheduled_jobs()
    if not jobs:
        ui.warning("No scheduled jobs found.")
        ui.hint("Use 'pem cron' to schedule jobs for automatic execution.")
        return
    ui.table(
        [(j["id"], j["next_run"], j["trigger"], j["func"]) for j in jobs],
        ["Schedule ID", "Next run", "Trigger", "Function"],
    )


@command(
    "cancel",
    "Cancel a scheduled job by its scheduler ID",
    args=[
        Arg(
            "-s",
            "--scheduler-id",
            dest="scheduler_job_id",
            required=True,
            prompt="Scheduler ID (see 'pem crons')",
            help="The scheduler job ID to cancel (from 'pem crons')",
        )
    ],
)
def cancel_scheduled_job(scheduler_job_id) -> None:
    if not scheduler_manager.cancel_job(scheduler_job_id):
        raise Fail(
            f"Failed to cancel scheduled job: {scheduler_job_id}",
            "Use 'pem crons' to see all scheduled jobs and their IDs.",
        )
    ui.success(f"Canceled scheduled job: {scheduler_job_id}")


@command("daemon", "Run the PEM scheduler daemon", db=False)
def run_daemon() -> None:
    """Run the PEM scheduler daemon in the foreground."""
    stop_event = threading.Event()

    def _handle_stop(*_args) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    ui.info("PEM daemon running. Press Ctrl+C to stop.")
    while not stop_event.is_set():
        time.sleep(1)

    scheduler_manager.shutdown()
    ui.info("PEM daemon stopped")


@command("install", "Install PEM and set up the background service", db=False, banner=True)
def install_pem() -> None:
    ui.info("Ensuring PEM is installed...")
    ensure_pem_installed()
    ui.info("Ensuring uv is installed...")
    ensure_uv_installed()
    ui.info("Installing PEM service...")
    install_service()
    start_service()
    ui.success("PEM installed and service started")


@command("update-uv", "Update the uv tool PEM relies on", db=False)
def update_uv_cmd() -> None:
    update_uv()
    ui.success("uv updated")


@command("status", "Display system overview with job counts and scheduling statistics")
async def show_status() -> None:
    async with SessionLocal() as session:
        all_jobs = (await session.execute(select(Job))).scalars().all()
    scheduled_jobs = scheduler_manager.list_scheduled_jobs()
    enabled = sum(1 for j in all_jobs if j.is_enabled)
    ui.table(
        [
            ("Total jobs", len(all_jobs)),
            ("Enabled", enabled),
            ("Disabled", len(all_jobs) - enabled),
            ("Scripts", sum(1 for j in all_jobs if j.job_type == "script")),
            ("Projects", sum(1 for j in all_jobs if j.job_type == "project")),
            ("Scheduled", len(scheduled_jobs)),
        ]
    )
    if scheduled_jobs:
        ui.out()
        ui.table([(j["id"], j["next_run"]) for j in scheduled_jobs], ["Schedule ID", "Next run"])
    else:
        ui.hint("No jobs are currently scheduled. Use 'pem cron' to schedule jobs.")


def run() -> None:
    app.main()


if __name__ == "__main__":
    run()
