"""Configuration settings for the PEM application."""

import os
from typing import Any

DATABASE_URL = "sqlite+aiosqlite:///pem.db"


# Cache the optimized config to avoid repeated system calls
_cached_config = None


def get_optimized_config() -> dict[str, Any]:
    """Get configuration optimized for current system."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    # Try to get user configuration first
    try:
        from pem.config import get_config

        user_config = get_config()

        # Use user-configured values if available, otherwise auto-detect
        config = {
            "max_concurrent_processes": user_config.max_concurrent_processes or _get_auto_processes(),
            "cache_size": user_config.cache_size or _get_auto_cache_size(),
            "pool_size": user_config.pool_size or _get_auto_pool_size(),
            "process_timeout": user_config.process_timeout,
            "buffer_limit": user_config.buffer_limit,
            "job_cache_size": user_config.job_cache_size,
            "log_buffer_size": user_config.log_buffer_size,
        }
    except ImportError:
        # Fallback to auto-detection if config module not available
        config = _get_auto_config()

    _cached_config = config
    return config


def _get_auto_config() -> dict[str, Any]:
    """Get auto-detected configuration based on system resources."""
    return {
        "max_concurrent_processes": _get_auto_processes(),
        "cache_size": _get_auto_cache_size(),
        "pool_size": _get_auto_pool_size(),
        "process_timeout": 1800,
        "buffer_limit": 1024 * 1024,
        "job_cache_size": 1000,
        "log_buffer_size": 8192,
    }


def _get_auto_processes() -> int:
    """Get optimal number of concurrent processes."""
    try:
        from psutil import cpu_count

        cpu_count_number = cpu_count(logical=False) or 2
    except ImportError:
        cpu_count_number = 2

    return int(_get_env_setting("PEM_MAX_PROCESSES", min(max(2, cpu_count_number), 8)))


def _get_auto_cache_size() -> int:
    """Get optimal cache size based on available memory."""
    try:
        from psutil import virtual_memory

        memory_gb = virtual_memory().total / (1024**3)
    except ImportError:
        memory_gb = 4.0

    return int(_get_env_setting("PEM_CACHE_SIZE", min(int(memory_gb * 16000), 128000)))


def _get_auto_pool_size() -> int:
    """Get optimal database pool size."""
    try:
        from psutil import cpu_count

        cpu_count_number = cpu_count(logical=False) or 2
    except ImportError:
        cpu_count_number = 2

    return int(_get_env_setting("PEM_POOL_SIZE", min(max(10, cpu_count_number * 2), 50)))


def _get_env_setting(env_var: str, default: float) -> int | float:
    """Get setting from environment variable with fallback to default."""
    if env_var in os.environ:
        try:
            value = os.environ[env_var]
            return float(value) if "." in value else int(value)
        except (ValueError, TypeError):
            pass
    return default


def get_database_config() -> dict[str, Any]:
    """Get database-specific performance configuration."""
    config = get_optimized_config()

    # Try to get database URL from user config
    try:
        from pem.config import get_config

        database_url = get_config().get_database_url()
    except ImportError:
        database_url = DATABASE_URL

    return {
        "database_url": database_url,
        "journal_mode": "WAL",
        "cache_size": -config["cache_size"] // 1000,  # Convert to KB for SQLite
        "synchronous": "NORMAL",
        "mmap_size": min(config["cache_size"] * 4, 268435456),  # 4x cache size, max 256MB
        "temp_store": "MEMORY",
        "foreign_keys": "ON",
        "auto_vacuum": "INCREMENTAL",
        "pool_size": config["pool_size"],
        "max_overflow": 0,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
