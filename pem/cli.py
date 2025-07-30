import asyncio
from typing import Annotated

import typer

from pem.core.executor import Executor
from pem.core.scheduler import scheduler_manager
from pem.db.database import SessionLocal, create_db_and_tables
from pem.db.models import Job

app = typer.Typer(help="Python Execution Manager (pem)")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    create_db_and_tables()
    # If no command is provided, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        ctx.exit()


def _add_job(name: str, path: str, job_type: str, dependencies: list[str] | None = None) -> Job:
    """Helper function to add a job to the database."""
    db = SessionLocal()
    try:
        # Check if job with this name already exists
        existing_job = db.query(Job).filter(Job.name == name).first()
        if existing_job:
            typer.secho(f"❌ Job '{name}' already exists.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        new_job = Job(name=name, path=path, job_type=job_type, dependencies=dependencies)
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        typer.secho(f"✅ {job_type.capitalize()} job '{name}' added.", fg=typer.colors.GREEN)
        return new_job
    finally:
        db.close()


def _get_job(name: str) -> Job | None:
    """Helper function to get a job from the database."""
    db = SessionLocal()
    try:
        return db.query(Job).filter(Job.name == name).first()
    finally:
        db.close()


@app.command("run")
def run_job(
    name: Annotated[str, typer.Argument(help="Name of the job to run.")],
    path: Annotated[
        str | None,
        typer.Option("--path", help="Path to script/project (required if job doesn't exist)."),
    ] = None,
    script: Annotated[bool, typer.Option("-s", "--script", help="Add as script job type.")] = False,
    project: Annotated[bool, typer.Option("-p", "--project", help="Add as project job type.")] = False,
    dependencies: Annotated[
        list[str] | None,
        typer.Option("--with", "-w", help="Dependencies for script jobs."),
    ] = None,
    add_only: Annotated[bool, typer.Option("--add-only", help="Only add the job, don't run it.")] = False,
    run_only: Annotated[bool, typer.Option("--run-only", help="Only run existing job, don't add if missing.")] = False,
) -> None:
    """Run a job. Can add and run, or just add, or just run existing job."""
    # Validate mutually exclusive options
    if script and project:
        typer.secho("❌ Cannot specify both --script and --project.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if add_only and run_only:
        typer.secho("❌ Cannot specify both --add-only and --run-only.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Get existing job
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
    finally:
        db.close()

    # If job doesn't exist and we're in run-only mode, error
    if not job and run_only:
        typer.secho(f"❌ Job '{name}' not found and --run-only specified.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # If job doesn't exist, we need to add it
    if not job:
        if not path:
            typer.secho("❌ Path is required when adding a new job.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not script and not project:
            typer.secho("❌ Must specify either --script (-s) or --project (-p) for new jobs.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        job_type = "script" if script else "project"

        # Validate dependencies only for scripts
        if project and dependencies:
            typer.secho("❌ Dependencies are only supported for script jobs.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        job = _add_job(name, path, job_type, dependencies)

    # If we're only adding, stop here
    if add_only:
        return

    # Run the job
    async def run() -> None:
        executor = Executor(job)
        result = await executor.execute()
        if result["status"] == "SUCCEEDED":
            typer.secho(f"✅ Job '{name}' completed successfully.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"❌ Job '{name}' failed with exit code {result['exit_code']}.", fg=typer.colors.RED)
        typer.secho(f"📋 Log file: {result['log_path']}", fg=typer.colors.BLUE)

    asyncio.run(run())


@app.command("schedule")
def schedule_job(
    name: Annotated[str, typer.Argument(help="Name of the job to schedule.")],
    schedule_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Schedule type: once, interval, cron, until_done"),
    ] = "once",
    run_date: Annotated[
        str | None,
        typer.Option("--date", help="Run date (YYYY-MM-DD HH:MM:SS) for 'once' type"),
    ] = None,
    seconds: Annotated[int, typer.Option("--seconds", help="Seconds for interval type")] = 0,
    minutes: Annotated[int, typer.Option("--minutes", help="Minutes for interval type")] = 0,
    hours: Annotated[int, typer.Option("--hours", help="Hours for interval type")] = 0,
    days: Annotated[int, typer.Option("--days", help="Days for interval type")] = 0,
    cron_minute: Annotated[str | None, typer.Option("--cron-minute", help="Cron minute (0-59)")] = None,
    cron_hour: Annotated[str | None, typer.Option("--cron-hour", help="Cron hour (0-23)")] = None,
    cron_day: Annotated[str | None, typer.Option("--cron-day", help="Cron day of month (1-31)")] = None,
    cron_month: Annotated[str | None, typer.Option("--cron-month", help="Cron month (1-12)")] = None,
    cron_dow: Annotated[str | None, typer.Option("--cron-dow", help="Cron day of week (0-6, 0=Sunday)")] = None,
    max_retries: Annotated[int, typer.Option("--max-retries", help="Max retries for until_done type")] = 10,
    retry_interval: Annotated[
        int,
        typer.Option("--retry-interval", help="Retry interval in seconds for until_done"),
    ] = 60,
) -> None:
    """Schedule a job to run in the background."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
        if not job:
            typer.secho(f"❌ Job '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Validate schedule type
        valid_types = ["once", "interval", "cron", "until_done"]
        if schedule_type not in valid_types:
            typer.secho(f"❌ Invalid schedule type. Must be one of: {', '.join(valid_types)}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Prepare scheduling arguments
        schedule_kwargs = {}

        if schedule_type == "once":
            if not run_date:
                typer.secho("❌ --date is required for 'once' schedule type", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            schedule_kwargs["run_date"] = run_date

        elif schedule_type == "interval":
            if not any([seconds, minutes, hours, days]):
                typer.secho(
                    "❌ At least one interval parameter (seconds, minutes, hours, days) is required",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)
            schedule_kwargs.update({"seconds": seconds, "minutes": minutes, "hours": hours, "days": days})

        elif schedule_type == "cron":
            cron_params = {
                "minute": cron_minute,
                "hour": cron_hour,
                "day": cron_day,
                "month": cron_month,
                "day_of_week": cron_dow,
            }
            # Only include non-None values
            schedule_kwargs.update({k: v for k, v in cron_params.items() if v is not None})
            if not schedule_kwargs:
                typer.secho("❌ At least one cron parameter is required", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        elif schedule_type == "until_done":
            schedule_kwargs.update({"max_retries": max_retries, "retry_interval": retry_interval})

        # Schedule the job
        scheduler_job_id = scheduler_manager.schedule_job(job.id, schedule_type, **schedule_kwargs)  # type: ignore

        typer.secho(f"✅ Job '{name}' scheduled successfully.", fg=typer.colors.GREEN)
        typer.secho(f"📅 Scheduler ID: {scheduler_job_id}", fg=typer.colors.BLUE)

        if schedule_type == "until_done":
            typer.secho(
                f"🔄 Job will run repeatedly until successful (max {max_retries} attempts)",
                fg=typer.colors.YELLOW,
            )

    finally:
        db.close()


@app.command("list")
def list_jobs(
    scheduled: Annotated[
        bool,
        typer.Option("--scheduled", "-s", help="Show scheduled jobs instead of stored jobs"),
    ] = False,
) -> None:
    """Lists all jobs managed by pem (stored) or scheduled jobs (with --scheduled)."""
    if scheduled:
        # List scheduled jobs
        scheduled_jobs = scheduler_manager.list_scheduled_jobs()

        if not scheduled_jobs:
            typer.secho("No scheduled jobs found.", fg=typer.colors.YELLOW)
            return

        typer.secho("Scheduled Jobs:", fg=typer.colors.BLUE)
        for job in scheduled_jobs:
            typer.secho(f"- {job['id']}", fg=typer.colors.WHITE)
            typer.secho(f"  Next run: {job['next_run']}", fg=typer.colors.CYAN)
            typer.secho(f"  Trigger: {job['trigger']}", fg=typer.colors.CYAN)
            if "start_time" in job:
                typer.secho(f"  Started: {job['start_time']}", fg=typer.colors.CYAN)
            if "max_retries" in job:
                typer.secho(f"  Max retries: {job['max_retries']}", fg=typer.colors.CYAN)
            typer.secho("")
    else:
        # List stored jobs
        db = SessionLocal()
        try:
            if not (jobs := db.query(Job).all()):
                typer.secho("No jobs found.", fg=typer.colors.YELLOW)
                return

            typer.secho("Jobs:", fg=typer.colors.BLUE)
            for job in jobs:
                status = "✅ enabled" if job.is_enabled else "❌ disabled"
                dependencies = f", deps: {job.dependencies}" if job.dependencies else ""
                typer.secho(
                    f"- {job.name} ({job.job_type}) - Path: {job.path}{dependencies} - {status}",
                    fg=typer.colors.GREEN if job.is_enabled else typer.colors.RED,
                )
        finally:
            db.close()


@app.command("cancel")
def cancel_scheduled_job(scheduler_job_id: Annotated[str, typer.Argument(help="Scheduler job ID to cancel.")]) -> None:
    """Cancel a scheduled job."""
    success = scheduler_manager.cancel_job(scheduler_job_id)

    if success:
        typer.secho(f"✅ Scheduled job '{scheduler_job_id}' cancelled successfully.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"❌ Failed to cancel scheduled job '{scheduler_job_id}'. Job not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("show")
def show_job(name: Annotated[str, typer.Argument(help="Name of the job to show.")]) -> None:
    """Shows detailed information about a specific job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
        if not job:
            typer.secho(f"❌ Job '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.secho("Job Details:", fg=typer.colors.BLUE)
        typer.secho(f"  Name: {job.name}", fg=typer.colors.WHITE)
        typer.secho(f"  Type: {job.job_type}", fg=typer.colors.WHITE)
        typer.secho(f"  Path: {job.path}", fg=typer.colors.WHITE)
        typer.secho(f"  Dependencies: {job.dependencies or 'None'}", fg=typer.colors.WHITE)
        typer.secho(f"  Enabled: {'Yes' if job.is_enabled else 'No'}", fg=typer.colors.WHITE)
        typer.secho(f"  ID: {job.id}", fg=typer.colors.WHITE)
    finally:
        db.close()


@app.command("update")
def update_job(
    name: Annotated[str, typer.Argument(help="Name of the job to update.")],
    new_name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    path: Annotated[str | None, typer.Option("--path", "-p")] = None,
    dependencies: Annotated[list[str] | None, typer.Option("--with", "-w")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled")] = None,
) -> None:
    """Updates an existing job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
        if not job:
            typer.secho(f"❌ Job '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Update fields if provided
        if new_name:
            job.name = new_name
        if path:
            job.path = path
        if dependencies is not None:
            job.dependencies = dependencies
        if enabled is not None:
            job.is_enabled = enabled

        db.commit()
        typer.secho(f"✅ Job '{name}' updated successfully.", fg=typer.colors.GREEN)
    finally:
        db.close()


@app.command("delete")
def delete_job(
    name: Annotated[str, typer.Argument(help="Name of the job to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Deletes a job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
        if not job:
            typer.secho(f"❌ Job '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not force:
            confirm = typer.confirm(f"Are you sure you want to delete job '{name}'?")
            if not confirm:
                typer.secho("❌ Operation cancelled.", fg=typer.colors.YELLOW)
                return

        db.delete(job)
        db.commit()
        typer.secho(f"✅ Job '{name}' deleted successfully.", fg=typer.colors.GREEN)
    finally:
        db.close()


@app.command("enable")
def enable_job(name: Annotated[str, typer.Argument(help="Name of the job to enable.")]) -> None:
    """Enables a job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
        if not job:
            typer.secho(f"❌ Job '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        job.is_enabled = True
        db.commit()
        typer.secho(f"✅ Job '{name}' enabled.", fg=typer.colors.GREEN)
    finally:
        db.close()


@app.command("disable")
def disable_job(name: Annotated[str, typer.Argument(help="Name of the job to disable.")]) -> None:
    """Disables a job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.name == name).first()
        if not job:
            typer.secho(f"❌ Job '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        job.is_enabled = False
        db.commit()
        typer.secho(f"✅ Job '{name}' disabled.", fg=typer.colors.GREEN)
    finally:
        db.close()
