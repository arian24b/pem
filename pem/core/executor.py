"""Execution manager for pem."""

import asyncio
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
        self.logs_dir = Path("./logs").resolve()
        self.logs_dir.mkdir(exist_ok=True)
        self.log_path = self.logs_dir / f"{self.job.name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"

        # Set up paths based on job type
        match self.job.job_type:
            case "script":
                self.script_path = Path(self.job.path).resolve()
            case "project":
                self.project_path = Path(self.job.path).resolve()
                self.venv_path = self.project_path / ".pem_venv"
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

    async def _execute_script(self, log_file) -> int:
        """Execute a script job using 'uv run' with optimizations."""
        command = ["uv", "run", "--no-project"]
        if self.job.python_version:
            command.extend(["--python", str(self.job.python_version)])
        if self.job.dependencies:
            for dep in self.job.dependencies:
                command.extend(["--with", dep])

        command.append(str(self.script_path))
        log_file.write(f"--- Running command: {' '.join(command)} ---\n\n")
        return await self._run_command(command, log_file)

    async def _execute_project(self, log_file) -> int:
        """Execute a project job with optimizations."""
        # Change to project directory and run the main module
        if (self.project_path / "main.py").exists():
            command = ["uv", "run", "python", "main.py"]
        elif (self.project_path / "app.py").exists():
            command = ["uv", "run", "python", "app.py"]
        elif (self.project_path / "__main__.py").exists():
            command = ["uv", "run", "python", "-m", self.project_path.name]
        else:
            # Fallback: try to run the project as a module
            command = ["uv", "run", "python", "-m", self.project_path.name]

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
