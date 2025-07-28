import asyncio
from typing import Annotated

import typer

from pem.core.executor import JobExecutor
from pem.db.database import SessionLocal, create_db_and_tables
from pem.db.models import Project

app = typer.Typer(help="Python Execution Manager (pem)")


@app.callback()
def main() -> None:
    """Manage Python projects. Call a command like 'project add' or 'project run'."""
    create_db_and_tables()


# Create a sub-command for 'project'
project_app = typer.Typer(help="Manage projects.")
app.add_typer(project_app, name="project")


@project_app.command("add")
def add_project(
    name: Annotated[str, typer.Option(prompt=True)],
    path: Annotated[str, typer.Argument(help="Path to the project directory.")],
) -> None:
    """Adds a new project to be managed by pem."""
    db = SessionLocal()
    try:
        new_project = Project(name=name, project_path=path)
        db.add(new_project)
        db.commit()
        typer.secho(f"✅ Project '{name}' added.", fg=typer.colors.GREEN)
    finally:
        db.close()


@project_app.command("run")
def run_project(name: Annotated[str, typer.Argument(help="Name of the project to run.")]) -> None:
    """Manually runs a project now."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == name).first()
        if not project:
            typer.secho(f"❌ Project '{name}' not found.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        executor = JobExecutor(project_path=project.project_path, project_name=project.name)
        asyncio.run(executor.execute())
    finally:
        db.close()


if __name__ == "__main__":
    app()
