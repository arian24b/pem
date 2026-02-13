"""Logging configuration for PEM."""

import logging
from logging.handlers import RotatingFileHandler

from pem.config import get_config


def configure_logging() -> None:
    """Configure rotating file logging for PEM."""
    config = get_config()
    logs_dir = config.get_logs_directory()
    log_path = logs_dir / "pem.log"

    root_logger = logging.getLogger()
    if any(isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers):
        return

    level = logging.DEBUG if config.debug or config.verbose_logging else logging.INFO
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.log_rotate_max_bytes,
        backupCount=config.log_rotate_backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
