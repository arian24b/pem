"""Configuration management commands for PEM CLI."""

from cfui import Arg, Fail, ui

from pem.config import ConfigurationError, get_config_manager

DESCRIPTIONS = {
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
    "log_rotate_max_bytes": "Log rotation max size (bytes)",
    "log_rotate_backups": "Log rotation backup count",
    "show_progress": "Show progress indicators",
    "colored_output": "Use colored output",
    "emoji_output": "Use emoji in output",
    "debug": "Debug mode",
    "verbose_logging": "Verbose logging",
}


def parse_value(value: str):
    """Turn a CLI string into bool / None / int / float / list / str."""
    low = value.lower()
    if low in ("true", "yes", "1", "on", "enable", "enabled"):
        return True
    if low in ("false", "no", "0", "off", "disable", "disabled"):
        return False
    if low in ("none", "null", "auto"):
        return None
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    if "." in value and value.replace(".", "").replace("-", "").isdigit():
        return float(value)
    if "," in value:
        return [item.strip() for item in value.split(",")]
    return value


def show(value) -> str:
    if value is None:
        return "None (auto)"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def register(app) -> None:
    config = app.group("config", "Manage PEM configuration settings")

    def guarded(fn):
        """Run fn(a) turning ConfigurationError into a boxed error."""

        def wrapper(a):
            try:
                return fn(a, get_config_manager())
            except ConfigurationError as e:
                raise Fail(f"Configuration error: {e}") from e

        return wrapper

    @config.command("show", "Show current configuration")
    @guarded
    def show_config(a, cm) -> None:
        ui.table(
            [(k, show(v), DESCRIPTIONS.get(k, "")) for k, v in cm.list_all().items()],
            ["Setting", "Value", "Description"],
        )
        ui.hint(f"Config file: {cm.get_config_file_path()}")

    @config.command(
        "get",
        "Get a specific configuration value",
        args=[Arg("key", required=True, prompt="Configuration key", help="Configuration key to retrieve")],
    )
    @guarded
    def get_config_value(a, cm) -> None:
        ui.out(show(cm.get(a.key)))

    @config.command(
        "set",
        "Set a configuration value",
        args=[
            Arg("key", required=True, prompt="Configuration key", help="Configuration key to set"),
            Arg("value", required=True, prompt="New value", help="New value for the configuration key"),
        ],
    )
    @guarded
    def set_config_value(a, cm) -> None:
        parsed = parse_value(a.value)
        cm.set(a.key, parsed)
        ui.success(f"Set {a.key} = {show(parsed)}")

    @config.command(
        "reset",
        "Reset configuration to defaults",
        args=[Arg("-y", "--yes", action="store_true", help="Do not ask for confirmation")],
    )
    @guarded
    def reset_config(a, cm) -> None:
        if not a.yes and not (ui.interactive() and ui.confirm("Reset all configuration to defaults?", default=False)):
            raise Fail("Reset cancelled.", "Pass --yes to reset without asking.")
        cm.reset()
        ui.success("Configuration reset to defaults")

    @config.command("validate", "Validate the current configuration")
    @guarded
    def validate_config(a, cm) -> None:
        if not cm.validate_config():
            raise Fail(
                "Configuration validation failed.",
                "Some settings may be invalid or files/directories may not be accessible.",
            )
        ui.success("Configuration is valid")

    @config.command("path", "Show configuration file path")
    @guarded
    def show_config_path(a, cm) -> None:
        config_file = cm.get_config_file_path()
        ui.out(config_file)
        if not config_file.exists():
            ui.warning("Configuration file does not exist (will be created on first save).")

    @config.command("edit", "Create the configuration file if needed and print its path for editing")
    @guarded
    def edit_config(a, cm) -> None:
        config_file = cm.get_config_file_path()
        if not config_file.exists():
            cm.save()
        ui.out(config_file)
        ui.hint("Edit this file with your editor; changes load on the next command.")
