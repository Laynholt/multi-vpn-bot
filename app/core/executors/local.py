"""Local subprocess executor."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.core.executors.base import BaseExecutor
from app.core.executors.errors import ExecutorTimeoutError
from app.core.executors.models import CommandResult
from app.infrastructure.logging import get_logger


class LocalExecutor(BaseExecutor):
    """Executes commands on the local host without going through a shell."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    async def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        normalized_command = self.normalize_command(command)
        started_at = time.perf_counter()
        self._logger.info("LocalExecutor running command: %s", normalized_command[0])

        process = await asyncio.create_subprocess_exec(
            *normalized_command,
            cwd=str(cwd) if cwd is not None else None,
            env={**os.environ, **dict(env)} if env is not None else None,
            stdin=asyncio.subprocess.PIPE if input_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(
                    input_text.encode("utf-8") if input_text is not None else None
                ),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ExecutorTimeoutError(
                f"Local command timed out after {timeout_seconds}s: {normalized_command[0]}"
            ) from exc

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        return CommandResult(
            command=normalized_command,
            exit_code=process.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
            timed_out=False,
        )
