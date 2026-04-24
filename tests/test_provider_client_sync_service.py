from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.core.config.models import (
    ConnectionConfig,
    ConnectionMode,
    DatabaseConfig,
    HostActionsConfig,
    ProviderConfig,
    ProviderType,
)
from app.core.registry import RegisteredServer, ServerRegistry
from app.domain.enums.common import ClientStatus
from app.infrastructure.db import DatabaseManager
from app.services.client_inventory import ClientInventoryService
from app.services.provider_clients import ProviderClientSyncService


@pytest.fixture
async def database(tmp_path) -> AsyncIterator[DatabaseManager]:  # noqa: ANN001
    manager = DatabaseManager(DatabaseConfig(sqlite_path=tmp_path / "test.db"))
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.dispose()


class FakeProvider:
    def __init__(self, clients: list[dict[str, object]]) -> None:
        self.clients = clients
        self.list_calls = 0
        self.create_calls: list[dict[str, object]] = []
        self.delete_calls: list[str] = []

    async def list_clients(self) -> list[dict[str, object]]:
        self.list_calls += 1
        return self.clients

    async def create_client(self, payload: dict[str, object]) -> dict[str, object]:
        self.create_calls.append(payload)
        created = {
            "provider_client_id": "peer-created",
            "display_name": "Created Client",
            "status": "active",
            "metadata": {"public_key": "pub-created"},
        }
        self.clients.append(created)
        return created

    async def delete_client(self, client_id: str) -> None:
        self.delete_calls.append(client_id)
        self.clients = [
            client for client in self.clients if client["provider_client_id"] != client_id
        ]


class FakeProviderFactory:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider
        self.calls: list[tuple[ProviderConfig, object]] = []

    def create(self, config: ProviderConfig, *, executor: object | None = None) -> FakeProvider:
        self.calls.append((config, executor))
        return self.provider


class FakeExecutorFactory:
    def __init__(self) -> None:
        self.executor = object()
        self.calls: list[str] = []

    def for_server(self, server: RegisteredServer) -> object:
        self.calls.append(server.key)
        return self.executor


def _registry() -> ServerRegistry:
    return ServerRegistry(
        {
            "vps-nl": RegisteredServer(
                key="vps-nl",
                title="VPS NL",
                connection=ConnectionConfig(mode=ConnectionMode.LOCAL),
                host_actions=HostActionsConfig(),
                providers=(
                    ProviderConfig(type=ProviderType.WIREGUARD),
                    ProviderConfig(type=ProviderType.X3UI, enabled=False),
                ),
                icon=None,
                sort_order=0,
                tags=(),
            )
        }
    )


def _registry_with_two_enabled_providers() -> ServerRegistry:
    return ServerRegistry(
        {
            "vps-nl": RegisteredServer(
                key="vps-nl",
                title="VPS NL",
                connection=ConnectionConfig(mode=ConnectionMode.LOCAL),
                host_actions=HostActionsConfig(),
                providers=(
                    ProviderConfig(type=ProviderType.WIREGUARD),
                    ProviderConfig(type=ProviderType.X3UI),
                ),
                icon=None,
                sort_order=0,
                tags=(),
            )
        }
    )


@pytest.mark.asyncio
async def test_sync_server_clients_persists_enabled_provider_clients(
    database: DatabaseManager,
) -> None:
    provider = FakeProvider(
        [
            {
                "provider_client_id": "peer-1",
                "display_name": "Alice Phone",
                "status": "active",
                "metadata": {"public_key": "pub1"},
            },
            {
                "provider_client_id": "peer-2",
                "status": "disabled",
            },
        ]
    )
    provider_factory = FakeProviderFactory(provider)
    executor_factory = FakeExecutorFactory()
    inventory_service = ClientInventoryService(database)
    service = ProviderClientSyncService(
        server_registry=_registry(),
        executor_factory=executor_factory,
        provider_factory=provider_factory,
        client_inventory_service=inventory_service,
    )

    result = await service.sync_server_clients("vps-nl")
    assert len(result) == 1
    assert result[0].server_key == "vps-nl"
    assert result[0].provider_type == ProviderType.WIREGUARD
    assert [client.provider_client_id for client in result[0].clients] == ["peer-1", "peer-2"]
    assert result[0].clients[0].display_name == "Alice Phone"
    assert result[0].clients[0].metadata == {"public_key": "pub1"}
    assert result[0].clients[1].display_name == "peer-2"
    assert result[0].clients[1].status == ClientStatus.DISABLED
    assert provider.list_calls == 1
    assert executor_factory.calls == ["vps-nl"]
    assert provider_factory.calls == [
        (ProviderConfig(type=ProviderType.WIREGUARD), executor_factory.executor)
    ]


@pytest.mark.asyncio
async def test_sync_provider_clients_syncs_only_selected_provider(
    database: DatabaseManager,
) -> None:
    provider = FakeProvider(
        [
            {
                "provider_client_id": "peer-1",
                "display_name": "Alice Phone",
            }
        ]
    )
    provider_factory = FakeProviderFactory(provider)
    service = ProviderClientSyncService(
        server_registry=_registry_with_two_enabled_providers(),
        executor_factory=FakeExecutorFactory(),
        provider_factory=provider_factory,
        client_inventory_service=ClientInventoryService(database),
    )

    result = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
    )

    assert result.provider_type == ProviderType.WIREGUARD
    assert [client.provider_client_id for client in result.clients] == ["peer-1"]
    assert [config.type for config, _executor in provider_factory.calls] == [
        ProviderType.WIREGUARD
    ]


@pytest.mark.asyncio
async def test_sync_server_clients_rejects_unknown_provider_status(
    database: DatabaseManager,
) -> None:
    provider = FakeProvider(
        [
            {
                "provider_client_id": "peer-1",
                "status": "paused",
            }
        ]
    )
    service = ProviderClientSyncService(
        server_registry=_registry(),
        executor_factory=FakeExecutorFactory(),
        provider_factory=FakeProviderFactory(provider),
        client_inventory_service=ClientInventoryService(database),
    )

    with pytest.raises(ValueError, match="Unsupported provider client status"):
        await service.sync_server_clients("vps-nl")


@pytest.mark.asyncio
async def test_create_client_syncs_provider_inventory_after_action(
    database: DatabaseManager,
) -> None:
    provider = FakeProvider([])
    service = ProviderClientSyncService(
        server_registry=_registry(),
        executor_factory=FakeExecutorFactory(),
        provider_factory=FakeProviderFactory(provider),
        client_inventory_service=ClientInventoryService(database),
    )

    result = await service.create_client(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        payload={"client_id": "alice"},
    )

    assert provider.create_calls == [{"client_id": "alice"}]
    assert result.provider_client["provider_client_id"] == "peer-created"
    assert result.sync_result.provider_type == ProviderType.WIREGUARD
    assert [client.provider_client_id for client in result.sync_result.clients] == [
        "peer-created"
    ]


@pytest.mark.asyncio
async def test_delete_client_syncs_provider_inventory_after_action(
    database: DatabaseManager,
) -> None:
    provider = FakeProvider(
        [
            {
                "provider_client_id": "peer-1",
                "display_name": "Alice Phone",
            }
        ]
    )
    service = ProviderClientSyncService(
        server_registry=_registry(),
        executor_factory=FakeExecutorFactory(),
        provider_factory=FakeProviderFactory(provider),
        client_inventory_service=ClientInventoryService(database),
    )

    result = await service.delete_client(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        provider_client_id="peer-1",
    )

    assert provider.delete_calls == ["peer-1"]
    assert result.provider_client_id == "peer-1"
    assert result.sync_result.clients == ()
