import asyncio
import subprocess
from datetime import datetime
from pathlib import Path


class JobExecutor:
    """Handles the execution of a single project run."""

    def __init__(self, project_path: str, project_name: str = "default_project") -> None:
        self.project_path = Path(project_path).resolve()
        self.project_name = project_name
        self.venv_path = self.project_path / ".pem_venv"
        self.logs_dir = Path("./logs").resolve()
        self.logs_dir.mkdir(exist_ok=True)

    async def _run_command(self, command: list[str], log_file_handle):
        """Asynchronously runs a shell command."""
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=log_file_handle,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout
            cwd=self.project_path,  # Run commands from the project's directory
        )
        await process.wait()
        return process.returncode

    async def execute(self):
        """Main execution flow: setup venv, install deps, and run."""
        start_time = datetime.utcnow()
        log_filename = f"{self.project_name}_{start_time.strftime('%Y%m%d_%H%M%S')}.log"
        log_path = self.logs_dir / log_filename

        with open(log_path, "w") as log_file:
            log_file.write(f"--- Starting execution at {start_time.isoformat()} ---\n")

            # 1. Create venv
            log_file.write("\n--- Creating venv with uv ---\n")
            await self._run_command(["uv", "venv", str(self.venv_path)], log_file)

            # 2. Install dependencies
            log_file.write("\n--- Installing dependencies with uv ---\n")
            await self._run_command(["uv", "sync"], log_file)

            # 3. Run the project
            log_file.write("\n--- Executing project ---\n")
            exit_code = await self._run_command(
                ["uv", "run", "--directory", str(self.project_path), "main.py"],
                log_file,
            )

        status = "SUCCEEDED" if exit_code == 0 else "FAILED"
        return {"status": status, "exit_code": exit_code, "log_path": str(log_path)}
