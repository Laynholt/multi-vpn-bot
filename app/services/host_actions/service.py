"""Service for executing host/system actions on registered servers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.executors import CommandResult, ExecutorFactory
from app.core.registry import RegisteredServer, ServerRegistry
from app.services.host_actions.registry import HostActionDefinition, HostActionRegistry


@dataclass(frozen=True, slots=True)
class HostActionExecution:
    """Normalized result of a host action run on a specific server."""

    server_key: str
    action_key: str
    result: CommandResult


class HostActionsService:
    """Runs enabled host actions through the executor layer."""

    def __init__(
        self,
        *,
        server_registry: ServerRegistry,
        executor_factory: ExecutorFactory,
        host_action_registry: HostActionRegistry,
        speedtest_timeout_seconds: int,
    ) -> None:
        self._server_registry = server_registry
        self._executor_factory = executor_factory
        self._host_action_registry = host_action_registry
        self._speedtest_timeout_seconds = speedtest_timeout_seconds

    async def run_action(self, *, server_key: str, action_key: str) -> HostActionExecution:
        server = self._server_registry.get(server_key)
        self._ensure_action_enabled(server, action_key)

        action_definition = self._host_action_registry.get(action_key)
        executor = self._executor_factory.for_server(server)
        timeout_seconds = self._resolve_timeout(action_key)
        result = await executor.run(
            action_definition.command,
            timeout_seconds=timeout_seconds,
        )
        return HostActionExecution(
            server_key=server_key,
            action_key=action_key,
            result=result,
        )

    def list_enabled_actions(self, server_key: str) -> tuple[HostActionDefinition, ...]:
        server = self._server_registry.get(server_key)
        return tuple(
            self._host_action_registry.get(action_key)
            for action_key in self._host_action_registry.list_keys()
            if hasattr(server.host_actions, action_key)
            and bool(getattr(server.host_actions, action_key))
        )

    def _ensure_action_enabled(self, server: RegisteredServer, action_key: str) -> None:
        if not self._host_action_registry.has(action_key):
            raise ValueError(f"Unsupported host action: {action_key}")

        host_actions = server.host_actions
        if not hasattr(host_actions, action_key):
            raise ValueError(f"Unknown host action flag on server config: {action_key}")
        if not getattr(host_actions, action_key):
            raise ValueError(f"Host action {action_key!r} is disabled for server {server.key!r}")

    def _resolve_timeout(self, action_key: str) -> int | None:
        if action_key == "speedtest":
            return self._speedtest_timeout_seconds
        return None
