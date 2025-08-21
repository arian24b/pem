"""Performance configuration for PEM."""

import os
from typing import Optional, Union

# Database performance settings
DATABASE_PERFORMANCE_CONFIG = {
    # SQLite pragmas for better performance
    "journal_mode": "WAL",
    "cache_size": -64000,  # 64MB cache
    "synchronous": "NORMAL",
    "mmap_size": 268435456,  # 256MB
    "temp_store": "MEMORY",
    "foreign_keys": "ON",
    "auto_vacuum": "INCREMENTAL",
    
    # Connection pool settings
    "pool_size": 20,
    "max_overflow": 0,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

# Executor performance settings
EXECUTOR_PERFORMANCE_CONFIG = {
    # Process concurrency limits
    "max_concurrent_processes": 4,
    "process_timeout": 1800,  # 30 minutes
    "process_kill_timeout": 10,
    "buffer_limit": 1024 * 1024,  # 1MB
    
    # Logging settings
    "log_buffer_size": 8192,
    "log_flush_interval": 1.0,
}

# Scheduler performance settings
SCHEDULER_PERFORMANCE_CONFIG = {
    # Job cache settings
    "job_cache_size": 1000,
    "job_cache_ttl": 300,  # 5 minutes
    
    # Execution settings
    "max_retries": 10,
    "retry_interval": 60,
    "execution_timeout": 300,  # 5 minutes
}

# Binary optimization settings
BINARY_OPTIMIZATION_CONFIG = {
    # Modules to exclude from binary
    "excluded_modules": [
        "tkinter", "matplotlib", "numpy", "pandas", "PIL",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "jupyter",
        "IPython", "sphinx", "pytest", "mypy", "ruff",
        "black", "flake8", "coverage", "tox"
    ],
    
    # PyInstaller optimization flags
    "optimization_level": 2,
    "strip_debug": True,
    "upx_compression": False,  # Can cause issues on some systems
}

# CLI performance settings
CLI_PERFORMANCE_CONFIG = {
    # Lazy loading settings
    "lazy_imports": True,
    "import_cache": True,
    
    # Database connection caching
    "db_connection_cache": True,
    "cache_timeout": 60,
}

# Environment variable overrides
def get_performance_setting(config_dict: dict, key: str, env_var: Optional[str] = None) -> Union[str, int, float, bool]:
    """Get performance setting with environment variable override."""
    if env_var and env_var in os.environ:
        try:
            value = os.environ[env_var]
            # Try to convert to appropriate type
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'
            elif value.isdigit():
                return int(value)
            elif '.' in value and value.replace('.', '').isdigit():
                return float(value)
            return value
        except (ValueError, AttributeError):
            pass
    return config_dict.get(key)

# Dynamic configuration based on system resources
def get_optimized_config() -> dict:
    """Get configuration optimized for current system."""
    try:
        import psutil
        
        # Get system resources
        cpu_count = psutil.cpu_count(logical=False) or 2
        memory_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        # Fallback if psutil is not available
        cpu_count = 2
        memory_gb = 4.0

    # Adjust settings based on resources
    optimized_config = {
        "max_concurrent_processes": min(max(2, cpu_count), 8),
        "cache_size": min(int(memory_gb * 16000), 128000),  # 16MB per GB, max 128MB
        "pool_size": min(max(10, cpu_count * 2), 50),
    }

    return optimized_config

# Performance monitoring
PERFORMANCE_MONITORING = {
    "enable_timing_logs": True,
    "enable_memory_monitoring": False,
    "enable_process_monitoring": True,
    "log_slow_operations": True,
    "slow_operation_threshold": 5.0,  # seconds
}
