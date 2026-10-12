"""Service management commands for PEM."""

from cfui import ui

from pem.service import install_service, start_service, status_service, stop_service, uninstall_service


def register(app) -> None:
    service = app.group("service", "Manage the PEM background service")

    @service.command("install", "Install and start the PEM service")
    def service_install(a) -> None:
        install_service()
        start_service()
        ui.success("PEM service installed and started")

    @service.command("uninstall", "Uninstall the PEM service")
    def service_uninstall(a) -> None:
        uninstall_service()
        ui.success("PEM service removed")

    @service.command("start", "Start the PEM service")
    def service_start(a) -> None:
        start_service()
        ui.success("PEM service started")

    @service.command("stop", "Stop the PEM service")
    def service_stop(a) -> None:
        stop_service()
        ui.success("PEM service stopped")

    @service.command("restart", "Restart the PEM service")
    def service_restart(a) -> None:
        stop_service()
        start_service()
        ui.success("PEM service restarted")

    @service.command("status", "Show PEM service status")
    def service_status(a) -> None:
        ui.out(f"PEM service status: {status_service()}")
