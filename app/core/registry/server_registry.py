"""Registry of enabled servers from the application config."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config.models import AppConfig, ConnectionConfig, HostActionsConfig, ProviderConfig
from app.core.exceptions import RegistryError


@dataclass(frozen=True, slots=True)
class RegisteredServer:
    key: str
    title: str
    connection: ConnectionConfig
    host_actions: HostActionsConfig
    providers: tuple[ProviderConfig, ...]
    icon: str | None
    sort_order: int
    tags: tuple[str, ...]


class ServerRegistry:
    """Read-only access to enabled servers."""

    def __init__(self, servers: dict[str, RegisteredServer]) -> None:
        self._servers = servers

    @classmethod
    def from_config(cls, config: AppConfig) -> ServerRegistry:
        servers = {
            server.key: RegisteredServer(
                key=server.key,
                title=server.title,
                connection=server.connection,
                host_actions=server.host_actions,
                providers=tuple(server.providers),
                icon=server.ui.icon,
                sort_order=server.ui.sort_order,
                tags=tuple(server.tags),
            )
            for server in config.servers
            if server.enabled
        }
        return cls(servers)

    def get(self, key: str) -> RegisteredServer:
        try:
            return self._servers[key]
        except KeyError as exc:
            raise RegistryError(f"Server {key!r} is not registered") from exc

    def list_servers(self) -> list[RegisteredServer]:
        return sorted(
            self._servers.values(),
            key=lambda item: (item.sort_order, item.title.lower(), item.key),
        )

    def __len__(self) -> int:
        return len(self._servers)
