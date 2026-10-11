"""Configuration commands for PEM: the shared cfui `config` group plus `edit`."""

from cfui import Fail, add_config, ui

from pem.config import ConfigurationError, get_config_manager


def register(app) -> None:
    def cm():
        try:
            return get_config_manager()
        except ConfigurationError as e:
            raise Fail(f"Configuration error: {e}") from e

    def guarded(fn):
        def wrapper(*a):
            try:
                return fn(*a)
            except ConfigurationError as e:
                raise Fail(f"Configuration error: {e}") from e

        return wrapper

    config = add_config(
        app,
        items=guarded(lambda: cm().list_all()),
        get=guarded(lambda k: cm().get(k)),
        set=guarded(lambda k, v: cm().set(k, v)),
        reset=guarded(lambda: cm().reset()),
        path=guarded(lambda: cm().get_config_file_path()),
        validate=guarded(lambda: cm().validate_config()),
        help="Manage PEM configuration settings",
    )

    @config.command("edit", "Create the configuration file if needed and print its path for editing")
    @guarded
    def edit_config(a) -> None:
        manager = cm()
        config_file = manager.get_config_file_path()
        if not config_file.exists():
            manager.save()
        ui.out(config_file)
        ui.hint("Edit this file with your editor; changes load on the next command.")
