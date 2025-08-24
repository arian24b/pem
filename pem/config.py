"""Configuration management for PEM."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class PEMConfig(BaseModel):
    """PEM application configuration model."""

    # Application info
    app_name: str = "PEM"
    version: str = "1.4.1"

    # Database configuration
    database_url: str = "sqlite+aiosqlite:///pem.db"
    database_path: str | None = None

    # Performance settings
    max_concurrent_processes: int | None = None
    cache_size: int | None = None
    pool_size: int | None = None
    process_timeout: int = 1800  # 30 minutes
    buffer_limit: int = 1048576  # 1MB
    job_cache_size: int = 1000
    log_buffer_size: int = 8192

    # Execution settings
    auto_run: bool = True
    default_python_version: str | None = None
    logs_directory: str = "./logs"

    # UI/UX settings
    show_progress: bool = True
    colored_output: bool = True
    emoji_output: bool = True

    # Development settings
    debug: bool = False
    verbose_logging: bool = False

    # Cache for expensive operations
    _cached_config_dir: Path | None = None
    _cached_logs_dir: Path | None = None

    def get_database_url(self) -> str:
        """Get the database URL with environment variable override."""
        if db_url := os.getenv("PEM_DATABASE_URL"):
            return db_url

        if self.database_path:
            return f"sqlite+aiosqlite:///{self.database_path}"

        return self.database_url

    def get_logs_directory(self) -> Path:
        """Get the logs directory path (cached)."""
        if self._cached_logs_dir:
            return self._cached_logs_dir

        logs_path = Path(self.logs_directory).resolve()
        logs_path.mkdir(parents=True, exist_ok=True)
        self._cached_logs_dir = logs_path
        return logs_path

    def get_config_dir(self) -> Path:
        """Get the configuration directory (cached)."""
        if self._cached_config_dir:
            return self._cached_config_dir

        # Try environment variable first
        if config_path := os.getenv("PEM_CONFIG_DIR"):
            config_dir = Path(config_path)
        else:
            try:
                from platformdirs import user_config_dir

                config_dir = Path(user_config_dir("pem"))
            except ImportError:
                config_dir = Path.home() / ".config" / "pem"

        config_dir.mkdir(parents=True, exist_ok=True)
        self._cached_config_dir = config_dir
        return config_dir

    def model_dump_user_settings(self) -> dict[str, Any]:
        """Get only user-configurable settings (excluding app info and cache)."""
        dump = self.model_dump()

        # Remove non-user-configurable fields
        excluded_fields = {
            "app_name",
            "version",
            "_cached_config_dir",
            "_cached_logs_dir",
        }

        return {k: v for k, v in dump.items() if k not in excluded_fields}


class ConfigurationError(Exception):
    """Configuration-related error."""


class ConfigManager:
    """Configuration manager for loading and saving PEM settings."""

    def __init__(self) -> None:
        self._config: PEMConfig = PEMConfig()
        self._config_file: Path = self._config.get_config_dir() / "config.json"
        self.load()

    @property
    def config(self) -> PEMConfig:
        """Get the current configuration."""
        return self._config

    def load(self) -> None:
        """Load configuration from file."""
        if not self._config_file.exists():
            self.save()  # Create default config
            return

        try:
            with open(self._config_file, encoding="utf-8") as f:
                config_data = json.load(f)
                # Only load user-configurable settings
                user_settings = {}
                for key, value in config_data.items():
                    if hasattr(self._config, key) and not key.startswith("_"):
                        user_settings[key] = value

                # Create new config with loaded settings
                self._config = PEMConfig(**user_settings)
        except Exception as e:
            msg = f"Failed to load configuration from {self._config_file}: {e}"
            raise ConfigurationError(msg) from e

    def save(self) -> None:
        """Save current configuration to file."""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._config.model_dump_user_settings(), f, indent=2)
        except Exception as e:
            msg = f"Failed to save configuration to {self._config_file}: {e}"
            raise ConfigurationError(msg) from e

    def get(self, key: str) -> Any:
        """Get a configuration value."""
        try:
            return getattr(self._config, key)
        except AttributeError:
            msg = f"Unknown configuration key: {key}"
            raise ConfigurationError(msg) from None

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        if not hasattr(self._config, key):
            msg = f"Unknown configuration key: {key}"
            raise ConfigurationError(msg)

        if key.startswith("_") or key in {"app_name", "version"}:
            msg = f"Cannot modify read-only configuration key: {key}"
            raise ConfigurationError(msg)

        try:
            # Create a new config with the updated value
            config_dict = self._config.model_dump()
            config_dict[key] = value
            self._config = PEMConfig(**config_dict)
            self.save()
        except Exception as e:
            msg = f"Failed to set configuration {key}={value}: {e}"
            raise ConfigurationError(msg) from e

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = PEMConfig()
        self.save()

    def list_all(self) -> dict[str, Any]:
        """Get all user-configurable configuration values."""
        return self._config.model_dump_user_settings()

    def get_config_file_path(self) -> Path:
        """Get the path to the configuration file."""
        return self._config_file

    def validate_config(self) -> bool:
        """Validate the current configuration."""
        try:
            # Check if logs directory is writable
            logs_dir = self._config.get_logs_directory()
            test_file = logs_dir / ".pem_write_test"
            test_file.touch()
            test_file.unlink()

            # Check database path if specified
            if self._config.database_path:
                db_path = Path(self._config.database_path)
                if db_path.exists() and not os.access(db_path, os.R_OK | os.W_OK):
                    return False

            # Validate numeric settings
            if self._config.max_concurrent_processes is not None and not (
                1 <= self._config.max_concurrent_processes <= 64
            ):
                return False

            return not (self._config.cache_size is not None and not 1000 <= self._config.cache_size <= 1000000)
        except Exception:
            return False


# Global configuration manager
_config_manager: ConfigManager | None = None


def get_config() -> PEMConfig:
    """Get the global configuration instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reset_config_manager() -> None:
    """Reset the global configuration manager (useful for testing)."""
    global _config_manager
    _config_manager = None
