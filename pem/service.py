"""Service management for PEM."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pem.config import get_config


@dataclass(frozen=True)
class ServicePaths:
    service_file: Path
    log_dir: Path


SERVICE_LABEL = "com.pem.daemon"


def _run_command(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _service_paths() -> ServicePaths:
    config = get_config()
    log_dir = config.get_logs_directory()

    system = platform.system()
    if system == "Darwin":
        service_file = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"
    elif system == "Linux":
        service_file = Path.home() / ".config" / "systemd" / "user" / "pem.service"
    else:
        msg = f"Unsupported platform for service install: {system}"
        raise RuntimeError(msg)

    service_file.parent.mkdir(parents=True, exist_ok=True)
    return ServicePaths(service_file=service_file, log_dir=log_dir)


def ensure_uv_installed() -> None:
    if shutil.which("uv"):
        return

    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        msg = f"UV install is not supported on {system}."
        raise RuntimeError(msg)

    install_script = "curl -LsSf https://astral.sh/uv/install.sh | sh"
    result = _run_command(["/bin/sh", "-c", install_script])
    if result.returncode != 0:
        msg = f"UV install failed: {result.stderr.strip() or result.stdout.strip()}"
        raise RuntimeError(msg)

    possible_paths = [str(Path.home() / ".local" / "bin"), str(Path.home() / ".cargo" / "bin")]
    current_path = os.environ.get("PATH", "")
    for path in possible_paths:
        if path not in current_path:
            os.environ["PATH"] = f"{path}:{current_path}"


def ensure_pem_installed() -> None:
    result = _run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pemexe"])
    if result.returncode != 0:
        msg = f"PEM install failed: {result.stderr.strip() or result.stdout.strip()}"
        raise RuntimeError(msg)


def update_uv() -> None:
    if shutil.which("uv"):
        result = _run_command(["uv", "self", "update"])
        if result.returncode != 0:
            msg = f"UV update failed: {result.stderr.strip() or result.stdout.strip()}"
            raise RuntimeError(msg)
        return

    ensure_uv_installed()


def _plist_content(python_executable: str, log_dir: Path) -> str:
    stdout_log = log_dir / "pem-daemon.out.log"
    stderr_log = log_dir / "pem-daemon.err.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>{SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
      <string>{python_executable}</string>
      <string>-m</string>
      <string>pem.cli</string>
      <string>daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PYTHONUNBUFFERED</key>
      <string>1</string>
    </dict>
  </dict>
</plist>
"""


def _systemd_content(python_executable: str) -> str:
    return """[Unit]
Description=PEM Scheduler Daemon
After=network.target

[Service]
Type=simple
ExecStart={python} -m pem.cli daemon
Restart=always
Environment=PYTHONUNBUFFERED=1
WorkingDirectory={cwd}

[Install]
WantedBy=default.target
""".format(
        python=python_executable,
        cwd=os.path.expanduser("~"),
    )


def install_service() -> None:
    paths = _service_paths()
    python_executable = sys.executable

    system = platform.system()
    if system == "Darwin":
        content = _plist_content(python_executable, paths.log_dir)
        paths.service_file.write_text(content, encoding="utf-8")
        _run_command(["launchctl", "load", "-w", str(paths.service_file)])
        return

    if system == "Linux":
        content = _systemd_content(python_executable)
        paths.service_file.write_text(content, encoding="utf-8")
        _run_command(["systemctl", "--user", "daemon-reload"])
        _run_command(["systemctl", "--user", "enable", "--now", "pem.service"])
        return

    msg = f"Unsupported platform for service install: {system}"
    raise RuntimeError(msg)


def uninstall_service() -> None:
    system = platform.system()
    paths = _service_paths()

    if system == "Darwin":
        _run_command(["launchctl", "unload", "-w", str(paths.service_file)])
        if paths.service_file.exists():
            paths.service_file.unlink()
        return

    if system == "Linux":
        _run_command(["systemctl", "--user", "disable", "--now", "pem.service"])
        if paths.service_file.exists():
            paths.service_file.unlink()
        _run_command(["systemctl", "--user", "daemon-reload"])
        return

    msg = f"Unsupported platform for service uninstall: {system}"
    raise RuntimeError(msg)


def start_service() -> None:
    system = platform.system()
    paths = _service_paths()

    if system == "Darwin":
        _run_command(["launchctl", "load", "-w", str(paths.service_file)])
        return

    if system == "Linux":
        _run_command(["systemctl", "--user", "start", "pem.service"])
        return

    msg = f"Unsupported platform for service start: {system}"
    raise RuntimeError(msg)


def stop_service() -> None:
    system = platform.system()
    paths = _service_paths()

    if system == "Darwin":
        _run_command(["launchctl", "unload", "-w", str(paths.service_file)])
        return

    if system == "Linux":
        _run_command(["systemctl", "--user", "stop", "pem.service"])
        return

    msg = f"Unsupported platform for service stop: {system}"
    raise RuntimeError(msg)


def status_service() -> str:
    system = platform.system()
    _service_paths()

    if system == "Darwin":
        result = _run_command(["launchctl", "list", SERVICE_LABEL])
        if result.returncode == 0:
            return "running"
        return "stopped"

    if system == "Linux":
        result = _run_command(["systemctl", "--user", "is-active", "pem.service"])
        if result.returncode == 0:
            return result.stdout.strip() or "active"
        return "inactive"

    msg = f"Unsupported platform for service status: {system}"
    raise RuntimeError(msg)
