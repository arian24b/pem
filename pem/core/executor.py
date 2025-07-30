import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from pem.db.models import Job


class Executor:
    """Unified executor for handling both script and project jobs."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self.logs_dir = Path("./logs").resolve()
        self.logs_dir.mkdir(exist_ok=True)

        # Set up paths based on job type
        if self.job.job_type == "script":
            self.script_path = Path(self.job.path).resolve()
        elif self.job.job_type == "project":
            self.project_path = Path(self.job.path).resolve()
            self.venv_path = self.project_path / ".pem_venv"
        else:
            msg = f"Unsupported job type: {self.job.job_type}, it must be either 'script' or 'project'."
            raise ValueError(msg)

    async def _run_command(self, command: list[str], log_file_handle, cwd: Path | None = None) -> int:
        """Run a command and write output to log file."""
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=log_file_handle,
            stderr=subprocess.STDOUT,
            cwd=cwd,
        )
        await process.wait()
        return process.returncode or 0

    async def _execute_script(self, log_file) -> int:
        """Execute a script job using 'uv run'."""
        command = ["uv", "run"]  # TODO: Add python version
        if self.job.dependencies:
            for dep in self.job.dependencies:
                command.extend(["--with", dep])
        command.extend(["--script", str(self.script_path)])

        log_file.write(f"--- Running command: {' '.join(command)} ---\n\n")
        return await self._run_command(command, log_file)

    async def _execute_project(self, log_file) -> int:
        """Execute a project job using a dedicated venv."""
        await self._run_command(
            ["uv", "sync", "--directory", str(self.venv_path)],
            log_file,
            self.project_path,
        )

        return await self._run_command(
            ["uv", "run", "--directory", str(self.venv_path), "main.py"],  # TODO: get python file
            log_file,
            self.project_path,
        )

    async def execute(self) -> dict[str, Any]:
        """Execute the job based on its type."""
        start_time = datetime.utcnow()
        log_filename = f"{self.job.name}_{start_time.strftime('%Y%m%d_%H%M%S')}.log"
        log_path = self.logs_dir / log_filename

        with open(log_path, "w") as log_file:
            log_file.write(f"--- Starting execution at {start_time.isoformat()} ---\n")

            if self.job.job_type == "script":
                exit_code = await self._execute_script(log_file)
            elif self.job.job_type == "project":
                exit_code = await self._execute_project(log_file)
            else:
                msg = f"Unsupported job type: {self.job.job_type}"
                raise ValueError(msg)

        status = "SUCCEEDED" if exit_code == 0 else "FAILED"
        return {"status": status, "exit_code": exit_code, "log_path": str(log_path)}
