"""Service management commands for PEM."""

import typer

from pem.service import install_service, start_service, status_service, stop_service, uninstall_service

service_app = typer.Typer(
    name="service",
    help="Manage the PEM background service",
    no_args_is_help=True,
)


@service_app.command("install")
def service_install() -> None:
    """Install and start the PEM service."""
    install_service()
    start_service()
    typer.echo("✅ PEM service installed and started")


@service_app.command("uninstall")
def service_uninstall() -> None:
    """Uninstall the PEM service."""
    uninstall_service()
    typer.echo("🗑️  PEM service removed")


@service_app.command("start")
def service_start() -> None:
    """Start the PEM service."""
    start_service()
    typer.echo("▶️ PEM service started")


@service_app.command("stop")
def service_stop() -> None:
    """Stop the PEM service."""
    stop_service()
    typer.echo("⏹️ PEM service stopped")


@service_app.command("restart")
def service_restart() -> None:
    """Restart the PEM service."""
    stop_service()
    start_service()
    typer.echo("🔄 PEM service restarted")


@service_app.command("status")
def service_status() -> None:
    """Show PEM service status."""
    status = status_service()
    typer.echo(f"📌 PEM service status: {status}")
