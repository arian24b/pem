"""Configuration management commands for PEM CLI."""

import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pem.config import ConfigurationError, get_config_manager

console = Console()

config_app = typer.Typer(
    name="config",
    help="Manage PEM configuration settings",
    no_args_is_help=True,
)


def confirm_action(message: str) -> bool:
    """Confirm an action with the user."""
    return typer.confirm(f"🤔 {message}")


@config_app.command("show")
def show_config() -> None:
    """Show current configuration."""
    try:
        config_manager = get_config_manager()
        config_data = config_manager.list_all()

        table = Table(title="⚙️ PEM Configuration")
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="green")
        table.add_column("Description", style="dim")

        # Define descriptions for settings
        descriptions = {
            "database_url": "Database connection URL",
            "database_path": "Custom database file path",
            "max_concurrent_processes": "Max concurrent job processes",
            "cache_size": "Database cache size (bytes)",
            "pool_size": "Database connection pool size",
            "process_timeout": "Job execution timeout (seconds)",
            "buffer_limit": "Process buffer limit (bytes)",
            "job_cache_size": "Job cache size",
            "log_buffer_size": "Log buffer size (bytes)",
            "auto_run": "Auto-run jobs after creation",
            "default_python_version": "Default Python version",
            "logs_directory": "Logs directory path",
            "show_progress": "Show progress indicators",
            "colored_output": "Use colored output",
            "emoji_output": "Use emoji in output",
            "debug": "Debug mode",
            "verbose_logging": "Verbose logging",
        }

        for key, value in config_data.items():
            # Format the display value
            if isinstance(value, bool):
                display_value = "✅ True" if value else "❌ False"
            elif isinstance(value, list):
                display_value = ", ".join(str(v) for v in value)
            elif value is None:
                display_value = "[dim]None (auto)[/dim]"
            else:
                display_value = str(value)

            description = descriptions.get(key, "")
            table.add_row(key, display_value, description)

        console.print(table)

        # Show config file location
        config_file = config_manager.get_config_file_path()
        console.print(f"\n📁 Config file: [dim]{config_file}[/dim]")

    except ConfigurationError as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        sys.exit(1)


@config_app.command("get")
def get_config_value(
    key: Annotated[str, typer.Argument(help="Configuration key to retrieve")],
) -> None:
    """Get a specific configuration value."""
    try:
        config_manager = get_config_manager()
        value = config_manager.get(key)

        # Format the output nicely
        if isinstance(value, bool):
            display_value = "✅ True" if value else "❌ False"
        elif value is None:
            display_value = "[dim]None (auto)[/dim]"
        else:
            display_value = str(value)

        console.print(f"⚙️ [cyan]{key}[/cyan]: {display_value}")

    except ConfigurationError as e:
        console.print(f"❌ {e}", style="red")
        sys.exit(1)


@config_app.command("set")
def set_config_value(
    key: Annotated[str, typer.Argument(help="Configuration key to set")],
    value: Annotated[str, typer.Argument(help="New value for the configuration key")],
) -> None:
    """Set a configuration value."""
    try:
        config_manager = get_config_manager()

        # Try to parse the value as the appropriate type
        parsed_value = value

        # Handle boolean values
        if value.lower() in ("true", "yes", "1", "on", "enable", "enabled"):
            parsed_value = True
        elif value.lower() in ("false", "no", "0", "off", "disable", "disabled"):
            parsed_value = False
        # Handle None/null values
        elif value.lower() in ("none", "null", "auto"):
            parsed_value = None
        # Handle integers (positive and negative)
        elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            parsed_value = int(value)
        # Handle floats
        elif "." in value and value.replace(".", "").replace("-", "").isdigit():
            parsed_value = float(value)
        # Handle lists (comma-separated)
        elif "," in value:
            parsed_value = [item.strip() for item in value.split(",")]

        config_manager.set(key, parsed_value)

        # Format the display value
        if isinstance(parsed_value, bool):
            display_value = "✅ True" if parsed_value else "❌ False"
        elif parsed_value is None:
            display_value = "[dim]None (auto)[/dim]"
        else:
            display_value = str(parsed_value)

        console.print(f"✅ Set [cyan]{key}[/cyan] = {display_value}", style="green")

    except ConfigurationError as e:
        console.print(f"❌ {e}", style="red")
        sys.exit(1)


@config_app.command("reset")
def reset_config() -> None:
    """Reset configuration to defaults."""
    if not confirm_action("Reset all configuration to defaults?"):
        console.print("🛑 Reset cancelled", style="yellow")
        return

    try:
        config_manager = get_config_manager()
        config_manager.reset()
        console.print("✅ Configuration reset to defaults", style="green")

    except ConfigurationError as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        sys.exit(1)


@config_app.command("validate")
def validate_config() -> None:
    """Validate the current configuration."""
    try:
        config_manager = get_config_manager()

        if config_manager.validate_config():
            console.print("✅ Configuration is valid", style="green")
        else:
            console.print("❌ Configuration validation failed", style="red")
            console.print("Some settings may be invalid or files/directories may not be accessible")
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        sys.exit(1)


@config_app.command("path")
def show_config_path() -> None:
    """Show configuration file path."""
    try:
        config_manager = get_config_manager()
        config_file = config_manager.get_config_file_path()

        console.print(f"📁 Configuration file: [green]{config_file}[/green]")

        if config_file.exists():
            size = config_file.stat().st_size
            console.print(f"📊 File size: {size} bytes")
        else:
            console.print("⚠️ Configuration file does not exist (will be created on first save)")

    except ConfigurationError as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        sys.exit(1)


@config_app.command("edit")
def edit_config() -> None:
    """Show configuration file path for manual editing."""
    try:
        config_manager = get_config_manager()
        config_file = config_manager.get_config_file_path()

        # Ensure config file exists
        if not config_file.exists():
            config_manager.save()  # Create default config

        console.print(f"� Configuration file: [green]{config_file}[/green]")
        console.print("💡 Edit this file with your preferred text editor")
        console.print("� Changes will be loaded automatically on next command")

    except ConfigurationError as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        sys.exit(1)
