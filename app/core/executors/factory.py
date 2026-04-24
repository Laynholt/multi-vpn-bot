"""Factory for building executors from server connection config."""

from __future__ import annotations

from app.core.config.models import ConnectionConfig, ConnectionMode, TransportsConfig
from app.core.executors.base import BaseExecutor
from app.core.executors.errors import UnsupportedExecutorModeError
from app.core.executors.local import LocalExecutor
from app.core.executors.ssh import SSHExecutor
from app.core.registry import RegisteredServer


class ExecutorFactory:
    """Creates executors for enabled server connections."""

    def __init__(self, transports: TransportsConfig) -> None:
        self._transports = transports

    def create(self, connection: ConnectionConfig) -> BaseExecutor:
        if connection.mode == ConnectionMode.LOCAL:
            return LocalExecutor()

        if connection.mode == ConnectionMode.SSH:
            assert connection.ssh_alias is not None
            return SSHExecutor(
                ssh_alias=connection.ssh_alias,
                transport_config=self._transports.ssh,
            )

        raise UnsupportedExecutorModeError(f"Unsupported executor mode: {connection.mode!r}")

    def for_server(self, server: RegisteredServer) -> BaseExecutor:
        return self.create(server.connection)
