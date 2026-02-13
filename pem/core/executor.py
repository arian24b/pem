"""Execution manager for pem."""

import asyncio
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pem.config import get_config
from pem.db.models import Job
from pem.settings import get_optimized_config

# Set up logging for performance monitoring
logger = logging.getLogger(__name__)

# Get optimized configuration
config = get_optimized_config()
MAX_CONCURRENT_PROCESSES = config["max_concurrent_processes"]
PROCESS_TIMEOUT = config["process_timeout"]
BUFFER_LIMIT = config["buffer_limit"]

# Process pool for better performance
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_PROCESSES)


class Executor:
    """Unified executor for handling both script and project jobs."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self.app_config = get_config()
        self.logs_dir = self.app_config.get_logs_directory()
        self.log_path = self.logs_dir / f"{self.job.name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
        self.python_version = self.job.python_version or self.app_config.default_python_version

        # Set up paths based on job type
        match self.job.job_type:
            case "script":
                self.script_path = Path(self.job.path).resolve()
            case "project":
                self.project_path = Path(self.job.path).resolve()
                self.venv_path = self.project_path / ".venv"
                self.venv_python = self.venv_path / "bin" / "python"
            case _:
                msg = f"Unsupported job type: {self.job.job_type}, it must be either 'script' or 'project'."
                raise ValueError(msg)

    async def _run_command(self, command: list[str], log_file_handle, cwd: Path | None = None) -> int:
        """Run a command and write output to log file with performance optimizations."""
        async with SEMAPHORE:  # Limit concurrent processes
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=log_file_handle,
                    stderr=subprocess.STDOUT,
                    cwd=cwd,
                    # Performance optimizations
                    limit=BUFFER_LIMIT,
                )

                # Set timeout to prevent hanging processes
                try:
                    await asyncio.wait_for(process.wait(), timeout=PROCESS_TIMEOUT)
                except TimeoutError:
                    logger.warning(f"Process timeout for job {self.job.name}, terminating...")
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=10)
                    except TimeoutError:
                        process.kill()
                        await process.wait()
                    return -1

                return process.returncode or 0
            except Exception as e:
                logger.exception(f"Command execution failed: {e}")
                return -1

    def _build_uv_run_command(self, args: list[str], *, no_project: bool, python: str | None) -> list[str]:
        command = ["uv", "run"]
        if no_project:
            command.append("--no-project")
        if python:
            command.extend(["--python", str(python)])
        command.extend(args)
        return command

    async def _execute_script_path(self, log_file, script_path: Path, dependencies: list[str] | None) -> int:
        """Execute a script path using uv run."""
        command = ["uv", "run", "--no-project"]
        if self.python_version:
            command.extend(["--python", str(self.python_version)])
        if dependencies:
            for dep in dependencies:
                command.extend(["--with", dep])
        command.append(str(script_path))
        log_file.write(f"--- Running command: {' '.join(command)} ---\n\n")
        return await self._run_command(command, log_file)

    def _project_context(self) -> tuple[bool, bool]:
        pyproject = self.project_path / "pyproject.toml"
        requirements = self.project_path / "requirements.txt"
        return pyproject.exists(), requirements.exists()

    def _project_entry_command(self) -> list[str]:
        if (self.project_path / "main.py").exists():
            return ["python", "main.py"]
        if (self.project_path / "app.py").exists():
            return ["python", "app.py"]
        if (self.project_path / "__main__.py").exists():
            return ["python", "-m", self.project_path.name]
        return ["python", "-m", self.project_path.name]

    async def _ensure_project_environment(self, log_file, has_pyproject: bool, has_requirements: bool) -> bool:
        if has_pyproject:
            if not self.venv_path.exists():
                command = ["uv", "sync"]
                if self.python_version:
                    command.extend(["--python", str(self.python_version)])
                log_file.write(f"--- Preparing environment: {' '.join(command)} ---\n\n")
                return await self._run_command(command, log_file, cwd=self.project_path) == 0
            return True

        if has_requirements:
            if not self.venv_python.exists():
                command = ["uv", "venv"]
                if self.python_version:
                    command.extend(["--python", str(self.python_version)])
                log_file.write(f"--- Preparing environment: {' '.join(command)} ---\n\n")
                if await self._run_command(command, log_file, cwd=self.project_path) != 0:
                    return False

                install_command = [
                    "uv",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                    "--python",
                    str(self.venv_python),
                ]
                log_file.write(f"--- Installing requirements: {' '.join(install_command)} ---\n\n")
                return await self._run_command(install_command, log_file, cwd=self.project_path) == 0
            return True

        return True

    async def _execute_script(self, log_file) -> int:
        """Execute a script job using 'uv run' with optimizations."""
        return await self._execute_script_path(log_file, self.script_path, self.job.dependencies)

    async def _execute_project(self, log_file) -> int:
        """Execute a project job with optimizations."""
        if self.project_path.is_file():
            return await self._execute_script_path(log_file, self.project_path, None)

        has_pyproject, has_requirements = self._project_context()
        if not has_pyproject and not has_requirements:
            entry_command = self._project_entry_command()
            if entry_command[:2] == ["python", "-m"]:
                command = self._build_uv_run_command(entry_command, no_project=True, python=self.python_version)
                log_file.write(f"--- Running command: {' '.join(command)} ---\n\n")
                return await self._run_command(command, log_file, cwd=self.project_path)

            entry_path = self.project_path / entry_command[-1]
            return await self._execute_script_path(log_file, entry_path, None)

        if not await self._ensure_project_environment(log_file, has_pyproject, has_requirements):
            return -1

        entry_command = self._project_entry_command()
        if has_requirements:
            python_path = str(self.venv_python) if self.venv_python.exists() else None
            command = self._build_uv_run_command(entry_command, no_project=True, python=python_path)
        else:
            command = self._build_uv_run_command(entry_command, no_project=False, python=self.python_version)

        log_file.write(f"--- Running command: {' '.join(command)} ---\n\n")
        return await self._run_command(command, log_file, cwd=self.project_path)

    async def execute(self) -> dict[str, Any]:
        """Execute the job and return execution details with performance monitoring."""
        start_time = datetime.now(UTC)
        logger.info(f"Starting execution of job {self.job.name} (ID: {self.job.id})")

        try:
            # Use regular file I/O (async file I/O is complex for this use case)
            with open(self.log_path, "w") as log_file:
                log_file.write("=== PEM Job Execution Log ===\n")
                log_file.write(f"Job: {self.job.name} (ID: {self.job.id})\n")
                log_file.write(f"Type: {self.job.job_type}\n")
                log_file.write(f"Started: {start_time}\n")
                log_file.write("=== Output ===\n\n")
                log_file.flush()

                if self.job.job_type == "script":
                    exit_code = await self._execute_script(log_file)
                elif self.job.job_type == "project":
                    exit_code = await self._execute_project(log_file)
                else:
                    msg = f"Unsupported job type: {self.job.job_type}"
                    raise ValueError(msg)

        except Exception as e:
            logger.exception(f"Job execution failed for {self.job.name}: {e}")
            exit_code = -1
            # Write error to log file
            try:
                with open(self.log_path, "a") as log_file:
                    log_file.write(f"\nError: {e!s}\n")
            except Exception as log_error:
                logger.exception(f"Failed to write error to log: {log_error}")

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        status = "SUCCESS" if exit_code == 0 else "FAILED"
        logger.info(f"Job {self.job.name} completed with status {status} in {duration:.2f}s")

        return {
            "job_id": self.job.id,
            "status": status,
            "exit_code": exit_code,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "log_path": str(self.log_path),
        }
