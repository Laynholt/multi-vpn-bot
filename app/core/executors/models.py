"""Models used by the executor layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Normalized result of a command execution."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out
