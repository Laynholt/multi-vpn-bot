"""SSH executor backed by asyncssh."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

import asyncssh

from app.core.config.models import SshTransportConfig
from app.core.executors.base import BaseExecutor
from app.core.executors.errors import ExecutorConnectionError, ExecutorTimeoutError
from app.core.executors.models import CommandResult
from app.infrastructure.logging import get_logger


def _coerce_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


class SSHExecutor(BaseExecutor):
    """Executes commands on a remote host via SSH."""

    def __init__(self, *, ssh_alias: str, transport_config: SshTransportConfig) -> None:
        self._ssh_alias = ssh_alias
        self._transport_config = transport_config
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
        if cwd is not None:
            raise ValueError("SSHExecutor does not support cwd yet")
        if env is not None:
            raise ValueError("SSHExecutor does not support env overrides yet")

        connect_timeout = self._transport_config.connect_timeout_seconds
        command_timeout = timeout_seconds or self._transport_config.command_timeout_seconds
        started_at = time.perf_counter()
        self._logger.info(
            "SSHExecutor running command on %s: %s", self._ssh_alias, normalized_command[0]
        )

        ssh_config_path = (
            Path.home() / ".ssh" / "config"
            if self._transport_config.use_system_ssh_config
            else None
        )

        try:
            connection = await asyncio.wait_for(
                asyncssh.connect(
                    self._ssh_alias,
                    config=ssh_config_path
                    if ssh_config_path and ssh_config_path.exists()
                    else None,
                ),
                timeout=connect_timeout,
            )
        except TimeoutError as exc:
            raise ExecutorConnectionError(
                f"SSH connection to {self._ssh_alias!r} timed out after {connect_timeout}s"
            ) from exc
        except (asyncssh.Error, OSError) as exc:
            raise ExecutorConnectionError(
                f"SSH connection to {self._ssh_alias!r} failed: {exc}"
            ) from exc

        try:
            try:
                completed = await asyncio.wait_for(
                    connection.run(*normalized_command, input=input_text, check=False),
                    timeout=command_timeout,
                )
            except TimeoutError as exc:
                raise ExecutorTimeoutError(
                    f"SSH command timed out after {command_timeout}s on {self._ssh_alias!r}"
                ) from exc
        finally:
            connection.close()
            await connection.wait_closed()

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        exit_code = completed.returncode if completed.returncode is not None else 0
        return CommandResult(
            command=normalized_command,
            exit_code=exit_code,
            stdout=_coerce_output(completed.stdout),
            stderr=_coerce_output(completed.stderr),
            duration_ms=duration_ms,
            timed_out=False,
        )
