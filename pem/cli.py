import asyncio
import inspect
from functools import partial, wraps
from typing import Annotated

import typer
from faker import Faker
from sqlalchemy.future import select

from pem.db.database import SessionLocal, create_db_and_tables
from pem.db.models import Job


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
    help="Python Execution Manager (pem)",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
async def main(ctx: typer.Context) -> None:
    await create_db_and_tables()
    # If no command is provided, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        ctx.exit()


@app.command(name="add", help="Creates a new Job record.", no_args_is_help=True)
async def add_job(
    name: Annotated[
        str | None,
        typer.Option(..., "--name", "-n", help="Job's unique name. If not provided, choose name randomly."),
    ] = None,
    path: str = typer.Option(..., "--path", "-p", help="Project's path or Script's file path."),
    is_script: Annotated[
        bool,
        typer.Option(..., "--script", "-s", help="Specifies whether the job is a script."),
    ] = False,
    dependencies: Annotated[
        list[str] | None,
        typer.Option(..., "--with", "-w", help="Get dependencies if the job is a script."),
    ] = None,
    python_version: Annotated[
        float | None,
        typer.Option(..., "--python", "-v", help="Get Python version if the job is a script."),
    ] = None,
    is_enabled: Annotated[
        bool,
        typer.Option(..., "--enabled", "-e", help="Specifies whether the job is enabled."),
    ] = True,
) -> None:
    async with SessionLocal() as session:
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
        typer.echo(f"Created job: {job.name}")


@app.command(name="show", help="Displays details of one or all jobs.")
async def show_jobs(
    name: Annotated[str | None, typer.Option(..., "--name", "-n", help="The name of the job to show.")] = None,
    job_id: Annotated[int | None, typer.Option(..., "--id", "-i", help="The ID of the job to show.")] = None,
) -> None:
    async with SessionLocal() as session:
        if not job_id and not name:
            jobs = list((await session.execute(select(Job))).scalars().all())
        else:
            if job_id:
                jobs = [(await session.get(Job, job_id))]
            if name:
                jobs = [await session.scalar(select(Job).filter_by(name=name))]

        if len(jobs) > 1:
            for job in jobs:
                typer.echo(f"Job details for {job.name}:")
                typer.echo(f"  ID: {job.id}")
                typer.echo(f"  Type: {job.job_type}")
                typer.echo(f"  Path: {job.path}")
                typer.echo(f"  Dependencies: {job.dependencies}")
                typer.echo(f"  Python Version: {job.python_version}")
                typer.echo(f"  Is Enabled: {job.is_enabled}")
        else:
            typer.echo(f"Job with ID/Name {job_id or name} not found.")


@app.command(name="update", help="Updates an existing Job record.")
async def update_job(
    job_id: Annotated[int | None, typer.Option(..., "--id", "-i", help="The ID of the job to update.")] = None,
    name: Annotated[str | None, typer.Option(..., "--name", "-n", help="The new name of the job.")] = None,
    path: Annotated[str | None, typer.Option(..., "--path", "-p", help="The new path of the job.")] = None,
    is_script: Annotated[
        bool,
        typer.Option(..., "--script", "-s", help="Specifies whether the job is a script."),
    ] = False,
    dependencies: Annotated[
        list[str] | None,
        typer.Option(..., "--with", "-w", help="Get dependencies if the job is a script."),
    ] = None,
    python_version: Annotated[
        float | None,
        typer.Option(..., "--python", "-v", help="Get Python version if the job is a script."),
    ] = None,
    is_enabled: Annotated[
        bool,
        typer.Option(..., "--enabled", "-e", help="Specifies whether the job is enabled."),
    ] = True,
) -> None:
    async with SessionLocal() as session:
        if not job_id and not name:
            typer.echo("You must provide either a job ID or a name to update.")
            return
        if job_id:
            job = await session.get(Job, job_id)
        elif name:
            job = await session.scalar(select(Job).filter_by(name=name))
        else:
            typer.echo(f"Job with ID/Name {job_id or name} not found.")
            return

        job.name = name if name else job.name
        job.path = path if path else job.path
        job.is_script = "script" if is_script else "project"
        job.dependencies = dependencies if dependencies else job.dependencies
        job.python_version = python_version if python_version else job.python_version
        job.is_enabled = is_enabled

        await session.commit()
        await session.refresh(job)
        typer.echo(f"Updated job: {job.id} - {job.name}")


@app.command(name="delete", help="Deletes a Job record.")
async def delete_job(
    job_id: Annotated[int | None, typer.Option(..., "--id", "-i", help="The ID of the job to delete.")] = None,
    name: Annotated[str | None, typer.Option(..., "--name", "-n", help="The name of the job to delete.")] = None,
) -> None:
    async with SessionLocal() as session:
        if not job_id and not name:
            typer.echo("You must provide either a job ID or a name to update.")
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
        typer.echo(f"Deleted job: {job.id} - {job.name}")


if __name__ == "__main__":
    asyncio.run(app())
