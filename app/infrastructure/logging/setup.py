"""Logging bootstrap with redaction and truncation."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config.models import LoggingConfig

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|password|secret|api[_-]?key)\b\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)\b(private[_-]?key)\b\s*[:=]\s*(.+)"),
)


class SafeMessageFilter(logging.Filter):
    """Redacts common secrets and truncates oversized log messages."""

    def __init__(self, *, max_length: int) -> None:
        super().__init__()
        self._max_length = max_length

    def filter(self, record: logging.LogRecord) -> bool:
        rendered_message = record.getMessage()
        for pattern in SECRET_PATTERNS:
            rendered_message = pattern.sub(
                lambda match: f"{match.group(1)}=<redacted>",
                rendered_message,
            )

        if len(rendered_message) > self._max_length:
            suffix = "... <truncated>"
            rendered_message = rendered_message[: max(0, self._max_length - len(suffix))] + suffix

        record.msg = rendered_message
        record.args = ()
        return True


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT)


def _build_file_handler(
    path: Path, level: int, message_filter: logging.Filter
) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        filename=path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    handler.addFilter(message_filter)
    return handler


def _build_console_handler(level: int, message_filter: logging.Filter) -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    handler.addFilter(message_filter)
    return handler


def configure_logging(config: LoggingConfig) -> None:
    """Configure root and audit loggers."""

    log_dir = config.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, config.level.upper(), logging.INFO)
    message_filter = SafeMessageFilter(max_length=config.max_log_length)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(_build_console_handler(level, message_filter))
    root_logger.addHandler(
        _build_file_handler(log_dir / f"{config.base_log_filename}.log", level, message_filter)
    )

    audit_logger = logging.getLogger("audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(level)
    audit_logger.propagate = False
    audit_logger.addHandler(
        _build_file_handler(
            log_dir / f"{config.base_log_filename}_audit.log", level, message_filter
        )
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_audit_logger() -> logging.Logger:
    return logging.getLogger("audit")
