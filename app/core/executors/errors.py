"""Executor-specific exceptions."""

from __future__ import annotations

from app.core.exceptions import ApplicationError


class ExecutorError(ApplicationError):
    """Base exception for executor layer failures."""


class ExecutorTimeoutError(ExecutorError):
    """Raised when a command exceeds the allowed timeout."""


class ExecutorConnectionError(ExecutorError):
    """Raised when an SSH connection cannot be established."""


class UnsupportedExecutorModeError(ExecutorError):
    """Raised when the connection mode cannot be mapped to an executor."""
