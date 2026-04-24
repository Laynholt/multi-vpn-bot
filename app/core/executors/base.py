"""Abstract executor contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.core.executors.models import CommandResult


class BaseExecutor(ABC):
    """Unified interface for local and remote command execution."""

    @abstractmethod
    async def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """Execute a command and return its normalized result."""

    @staticmethod
    def normalize_command(command: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(arg for arg in command if arg is not None)
        if not normalized:
            raise ValueError("command must contain at least one argument")
        if any(arg == "" for arg in normalized):
            raise ValueError("command arguments must not be empty strings")
        return normalized
