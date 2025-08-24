import asyncio
import inspect
from enum import Enum
from functools import partial, wraps
from typing import Annotated

import typer
from faker import Faker
from sqlalchemy.future import select

from pem.core.executor import Executor
from pem.core.scheduler import scheduler_manager
from pem.db.database import SessionLocal, create_db_and_tables
from pem.db.models import Job


class ScheduleTypeEnum(str, Enum):
    """Schedule type enumeration for CLI."""

    once = "once"
    interval = "interval"
    cron = "cron"
    until_done = "until_done"


class AsyncTyper(typer.Typer):
    @staticmethod
    def maybe_run_async(decorator, f):
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            def runner(*args, **kwargs):
                return asyncio.run(f(*args, **kwargs))

            decorator(runner)
        else:
            decorator(f)
        return f

    def callback(self, *args, **kwargs):
        decorator = super().callback(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)

    def command(self, *args, **kwargs):
        decorator = super().command(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)


app = AsyncTyper(
    help="Python Execution Manager - Schedule and execute Python scripts and projects with ease",
    no_args_is_help=True,
)

# Add config subcommand
from pem.commands.config import config_app

app.add_typer(config_app)


@app.callback()
async def main() -> None:
    """Initialize the database."""
    await create_db_and_tables()


@app.command(name="add", help="Create a new job to execute Python scripts or projects.", no_args_is_help=True)
async def add_job(
    path: Annotated[
        str,
        typer.Option("--path", "-p", help="Path to Python script file or project directory.", show_default=False),
    ] = "",
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Unique name for the job (auto-generated if not provided).",
            show_default=False,
        ),
    ] = None,
    is_script: Annotated[
        bool,
        typer.Option("--script", "-s", help="Treat as single Python script (default: project).", show_default=False),
    ] = False,
    dependencies: Annotated[
        list[str] | None,
        typer.Option("--with", "-w", help="Python dependencies to install (for scripts only).", show_default=False),
    ] = None,
    python_version: Annotated[
        float | None,
        typer.Option("--python", "-v", help="Required Python version (for scripts only).", show_default=False),
    ] = None,
    is_enabled: Annotated[
        bool,
        typer.Option("--enabled/--disabled", "-e", help="Enable job for execution.", show_default=False),
    ] = True,
    auto_run: Annotated[
        bool,
        typer.Option(
            "--auto-run/--no-auto-run",
            help="Execute immediately after creation (if enabled).",
            show_default=False,
        ),
    ] = True,
) -> None:
    async with SessionLocal() as session:
        # Validate required path parameter
        if not path:
            typer.echo("❌ Error: Path is required. Use --path to specify the Python script or project directory.")
            raise typer.Exit(1)

        job = Job(
            name=name if name else Faker().first_name(),
            job_type="script" if is_script else "project",
            path=path,
            dependencies=dependencies,
            python_version=python_version,
            is_enabled=is_enabled,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        typer.echo(f"✅ Created job: {job.name}")

        # If job is enabled and auto-run is requested, automatically execute it
        if job.is_enabled and auto_run:
            typer.echo("🚀 Job is enabled. Executing immediately...")
            try:
                executor = Executor(job)
                result = await executor.execute()

                typer.echo(f"✅ Execution completed with status: {result['status']}")
                typer.echo(f"   Exit code: {result['exit_code']}")
                typer.echo(f"   Log file: {result['log_path']}")

                if result["status"] == "FAILED":
                    typer.echo("⚠️  Job execution failed. Check the log file for details.")
                else:
                    typer.echo("🎉 Job executed successfully!")

            except Exception as e:
                typer.echo(f"❌ Failed to execute job after creation: {e}")
        elif job.is_enabled and not auto_run:
            typer.echo("💡 Job is enabled but auto-run is disabled. Use 'pem run' to execute manually.")
        else:
            typer.echo("💤 Job is disabled. Enable it with 'pem update' to allow execution.")


@app.command(name="show", help="Display details of jobs (all jobs if no filter specified).")
async def show_jobs(
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Show specific job by name.", show_default=False),
    ] = None,
    job_id: Annotated[
        int | None,
        typer.Option("--id", "-i", help="Show specific job by ID.", show_default=False),
    ] = None,
) -> None:
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
            for job in jobs:
                status_emoji = "🟢" if job.is_enabled else "🔴"
                type_emoji = "📄" if job.job_type == "script" else "📁"
                typer.echo(f"\n{status_emoji} {type_emoji} Job: {job.name}")
                typer.echo(f"   ID: {job.id}")
                typer.echo(f"   Type: {job.job_type}")
                typer.echo(f"   Path: {job.path}")
                typer.echo(f"   Status: {'Enabled' if job.is_enabled else 'Disabled'}")
                if job.dependencies:
                    typer.echo(f"   Dependencies: {', '.join(job.dependencies)}")
                if job.python_version:
                    typer.echo(f"   Python Version: {job.python_version}")
        elif job_id or name:
            typer.echo(f"❌ Job with ID/Name '{job_id or name}' not found.")
        else:
            typer.echo("📭 No jobs found. Use 'pem add' to create your first job.")


@app.command(name="update", help="Update properties of an existing job.")
async def update_job(
    job_id: Annotated[
        int | None,
        typer.Option("--id", "-i", help="ID of the job to update.", show_default=False),
    ] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name for the job.", show_default=False)] = None,
    path: Annotated[str | None, typer.Option("--path", "-p", help="New path for the job.", show_default=False)] = None,
    is_script: Annotated[
        bool,
        typer.Option("--script", "-s", help="Change job type to script.", show_default=False),
    ] = False,
    dependencies: Annotated[
        list[str] | None,
        typer.Option("--with", "-w", help="Update dependencies (scripts only).", show_default=False),
    ] = None,
    python_version: Annotated[
        float | None,
        typer.Option("--python", "-v", help="Update Python version requirement.", show_default=False),
    ] = None,
    is_enabled: Annotated[
        bool,
        typer.Option("--enabled/--disabled", "-e", help="Enable or disable the job.", show_default=False),
    ] = True,
) -> None:
    async with SessionLocal() as session:
        if not job_id and not name:
            typer.echo("❌ You must provide either --id or --name to specify which job to update.")
            return

        if job_id:
            job = await session.get(Job, job_id)
        elif name:
            job = await session.scalar(select(Job).filter_by(name=name))
        else:
            typer.echo(f"Job with ID/Name {job_id or name} not found.")
            return

        if name:
            job.name = name
        if path:
            job.path = path
        job.job_type = "script" if is_script else "project"
        if dependencies:
            job.dependencies = dependencies
        if python_version:
            job.python_version = python_version
        job.is_enabled = is_enabled

        await session.commit()
        await session.refresh(job)
        typer.echo(f"✅ Updated job: {job.id} - {job.name}")


@app.command(name="delete", help="Remove a job permanently from the system.")
async def delete_job(
    job_id: Annotated[
        int | None,
        typer.Option("--id", "-i", help="ID of the job to delete.", show_default=False),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Name of the job to delete.", show_default=False),
    ] = None,
) -> None:
    async with SessionLocal() as session:
        if not job_id and not name:
            typer.echo("❌ You must provide either --id or --name to specify which job to delete.")
            return

        if job_id:
            job = await session.get(Job, job_id)
        elif name:
            job = await session.scalar(select(Job).filter_by(name=name))
        else:
            typer.echo(f"Job with ID/Name {job_id or name} not found.")
            return

        await session.delete(job)
        await session.commit()
        typer.echo(f"🗑️  Deleted job: {job.id} - {job.name}")


@app.command(name="run", help="Execute a job immediately, with optional recurring schedule setup.")
async def run_job(
    job_id: Annotated[
        int | None,
        typer.Option("--id", "-i", help="ID of the job to execute.", show_default=False),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Name of the job to execute.", show_default=False),
    ] = None,
    schedule: Annotated[
        bool,
        typer.Option("--schedule/--no-schedule", "-s", help="Set up recurring execution schedule.", show_default=False),
    ] = False,
    schedule_type: Annotated[
        ScheduleTypeEnum,
        typer.Option("--type", "-t", help="Schedule type (for --schedule option).", show_default=False),
    ] = ScheduleTypeEnum.interval,
    minutes: Annotated[
        int,
        typer.Option("--minutes", "-m", help="Interval in minutes (for interval scheduling).", show_default=False),
    ] = 60,
) -> None:
    """Execute a job immediately and optionally schedule it for future execution."""
    async with SessionLocal() as session:
        if not job_id and not name:
            typer.echo("❌ You must provide either --id or --name to specify which job to execute.")
            return

        if job_id:
            job = await session.get(Job, job_id)
        elif name:
            job = await session.scalar(select(Job).filter_by(name=name))
        else:
            typer.echo(f"❌ Job with ID/Name '{job_id or name}' not found.")
            return

        if not job.is_enabled:
            typer.echo(f"⚠️  Job '{job.name}' is disabled. Enable it first with 'pem update --enabled'.")
            return

        typer.echo(f"🚀 Executing job: {job.name}")
        executor = Executor(job)
        result = await executor.execute()

        typer.echo(f"✅ Execution completed with status: {result['status']}")
        typer.echo(f"   Exit code: {result['exit_code']}")
        typer.echo(f"   Log file: {result['log_path']}")

        if result["status"] == "FAILED":
            typer.echo("⚠️  Job execution failed. Check the log file for details.")
        else:
            typer.echo("🎉 Job executed successfully!")

        # Schedule if requested
        if schedule:
            typer.echo("\n⏰ Setting up recurring schedule...")
            await schedule_job(job_id=job_id, name=name, schedule_type=schedule_type, minutes=minutes)


@app.command(name="cron", help="Schedule a job for automatic execution using various timing options.")
async def schedule_job(
    job_id: Annotated[
        int | None,
        typer.Option("--id", "-i", help="ID of the job to schedule.", show_default=False),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Name of the job to schedule.", show_default=False),
    ] = None,
    schedule_type: Annotated[
        ScheduleTypeEnum,
        typer.Option("--type", "-t", help="Schedule type: once, interval, cron, or until_done.", show_default=False),
    ] = ScheduleTypeEnum.once,
    # For 'once' scheduling
    run_date: Annotated[
        str | None,
        typer.Option(..., "--date", "-d", help="Date/time to run (ISO format, e.g., '2024-01-01T10:00:00')"),
    ] = None,
    # For 'interval' scheduling
    seconds: Annotated[int, typer.Option(..., "--seconds", help="Interval in seconds")] = 0,
    minutes: Annotated[int, typer.Option(..., "--minutes", help="Interval in minutes")] = 0,
    hours: Annotated[int, typer.Option(..., "--hours", help="Interval in hours")] = 0,
    days: Annotated[int, typer.Option(..., "--days", help="Interval in days")] = 0,
    # For 'cron' scheduling
    cron_minute: Annotated[str | None, typer.Option(..., "--cron-minute", help="Cron minute field")] = None,
    cron_hour: Annotated[str | None, typer.Option(..., "--cron-hour", help="Cron hour field")] = None,
    cron_day: Annotated[str | None, typer.Option(..., "--cron-day", help="Cron day field")] = None,
    cron_month: Annotated[str | None, typer.Option(..., "--cron-month", help="Cron month field")] = None,
    cron_day_of_week: Annotated[str | None, typer.Option(..., "--cron-dow", help="Cron day of week field")] = None,
    # For 'until_done' scheduling
    max_retries: Annotated[int, typer.Option(..., "--max-retries", help="Maximum retry attempts")] = 10,
    retry_interval: Annotated[int, typer.Option(..., "--retry-interval", help="Retry interval in seconds")] = 60,
) -> None:
    """Schedule a job for execution with various scheduling options."""
    async with SessionLocal() as session:
        if not job_id and not name:
            typer.echo("❌ You must provide either --id or --name to specify which job to schedule.")
            return

        if job_id:
            job = await session.get(Job, job_id)
        elif name:
            job = await session.scalar(select(Job).filter_by(name=name))
        else:
            typer.echo(f"❌ Job with ID/Name '{job_id or name}' not found.")
            return

        if not job.is_enabled:
            typer.echo(f"⚠️  Job '{job.name}' is disabled. Enable it first with 'pem update --enabled'.")
            return

        # Prepare scheduling kwargs based on schedule type
        kwargs = {}

        match schedule_type.value:
            case "once":
                if not run_date:
                    typer.echo("❌ For 'once' scheduling, you must provide --date parameter.")
                    return
                kwargs["run_date"] = run_date

            case "interval":
                if not any([seconds, minutes, hours, days]):
                    typer.echo("❌ For 'interval' scheduling, provide at least one time interval:")
                    typer.echo("   Use --seconds, --minutes, --hours, or --days")
                    return
                kwargs.update({"seconds": seconds, "minutes": minutes, "hours": hours, "days": days})

            case "cron":
                cron_fields = {
                    "minute": cron_minute,
                    "hour": cron_hour,
                    "day": cron_day,
                    "month": cron_month,
                    "day_of_week": cron_day_of_week,
                }
                # Only include fields that are provided
                kwargs = {k: v for k, v in cron_fields.items() if v is not None}
                if not kwargs:
                    typer.echo("❌ For 'cron' scheduling, provide at least one cron field:")
                    typer.echo("   Use --cron-minute, --cron-hour, --cron-day, etc.")
                    return

            case "until_done":
                kwargs.update({"max_retries": max_retries, "retry_interval": retry_interval})

        try:
            scheduler_job_id = scheduler_manager.schedule_job(job.id, schedule_type.value, **kwargs)
            typer.echo(f"⏰ Successfully scheduled job '{job.name}'")
            typer.echo(f"   Scheduler ID: {scheduler_job_id}")
            typer.echo(f"   Schedule type: {schedule_type.value}")

            if schedule_type == "once":
                typer.echo(f"   Run date: {run_date}")
            elif schedule_type.value == "interval":
                interval_str = []
                if days:
                    interval_str.append(f"{days}d")
                if hours:
                    interval_str.append(f"{hours}h")
                if minutes:
                    interval_str.append(f"{minutes}m")
                if seconds:
                    interval_str.append(f"{seconds}s")
                typer.echo(f"   Interval: {' '.join(interval_str)}")
            elif schedule_type.value == "cron":
                typer.echo(f"   Cron schedule: {kwargs}")
            elif schedule_type.value == "until_done":
                typer.echo(f"   Max retries: {max_retries}, Retry interval: {retry_interval}s")

        except Exception as e:
            typer.echo(f"❌ Failed to schedule job: {e}")


@app.command(name="crons", help="List all jobs currently scheduled for automatic execution.")
async def list_scheduled_jobs() -> None:
    """List all currently scheduled jobs."""
    jobs = scheduler_manager.list_scheduled_jobs()

    if not jobs:
        typer.echo("📅 No scheduled jobs found.")
        typer.echo("💡 Use 'pem cron' to schedule jobs for automatic execution.")
        return

    typer.echo("📅 Scheduled Jobs:")
    typer.echo("-" * 80)

    for job in jobs:
        typer.echo(f"⏰ Schedule ID: {job['id']}")
        typer.echo(f"   Next Run: {job['next_run']}")
        typer.echo(f"   Trigger: {job['trigger']}")
        typer.echo(f"   Function: {job['func']}")

        if "start_time" in job:
            typer.echo(f"   Start Time: {job['start_time']}")
        if "max_retries" in job:
            typer.echo(f"   Max Retries: {job['max_retries']}")

        typer.echo("")


@app.command(name="cancel", help="Cancel a scheduled job by its scheduler ID.")
async def cancel_scheduled_job(
    scheduler_job_id: Annotated[
        str,
        typer.Option(
            "--scheduler-id",
            "-s",
            help="The scheduler job ID to cancel (from 'pem crons' output).",
            show_default=False,
        ),
    ],
) -> None:
    """Cancel a scheduled job by its scheduler ID."""
    if scheduler_manager.cancel_job(scheduler_job_id):
        typer.echo(f"✅ Successfully canceled scheduled job: {scheduler_job_id}")
    else:
        typer.echo(f"❌ Failed to cancel scheduled job: {scheduler_job_id}")
        typer.echo("💡 Use 'pem crons' to see all scheduled jobs and their IDs.")


@app.command(name="status", help="Display system overview with job counts and scheduling statistics.")
async def show_status() -> None:
    """Show system status including job counts and scheduled jobs."""
    async with SessionLocal() as session:
        # Get job statistics
        all_jobs = (await session.execute(select(Job))).scalars().all()
        total_jobs = len(all_jobs)
        enabled_jobs = len([job for job in all_jobs if job.is_enabled])
        disabled_jobs = total_jobs - enabled_jobs
        script_jobs = len([job for job in all_jobs if job.job_type == "script"])
        project_jobs = len([job for job in all_jobs if job.job_type == "project"])

    # Get scheduled job count
    scheduled_jobs = scheduler_manager.list_scheduled_jobs()
    scheduled_count = len(scheduled_jobs)

    typer.echo("📊 PEM System Status")
    typer.echo("=" * 50)
    typer.echo(f"📋 Total Jobs: {total_jobs}")
    typer.echo(f"   🟢 Enabled: {enabled_jobs}")
    typer.echo(f"   🔴 Disabled: {disabled_jobs}")
    typer.echo(f"   📄 Scripts: {script_jobs}")
    typer.echo(f"   📁 Projects: {project_jobs}")
    typer.echo(f"⏰ Scheduled Jobs: {scheduled_count}")
    typer.echo("")

    if scheduled_count > 0:
        typer.echo("🗓️  Active Schedules:")
        for job in scheduled_jobs:
            typer.echo(f"   {job['id']} - Next: {job['next_run']}")
    else:
        typer.echo("💡 No jobs are currently scheduled. Use 'pem cron' to schedule jobs.")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
