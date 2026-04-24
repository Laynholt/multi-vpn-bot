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
from app.infrastructure.db import DatabaseManager
from app.services.client_inventory import ClientInventoryService, VpnClientSyncItem
from app.services.config_delivery import ConfigDeliveryService


@pytest.fixture
async def database(tmp_path) -> AsyncIterator[DatabaseManager]:  # noqa: ANN001
    manager = DatabaseManager(DatabaseConfig(sqlite_path=tmp_path / "test.db"))
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.dispose()


class FakeProvider:
    def __init__(self, configs: dict[str, bytes]) -> None:
        self.configs = configs
        self.export_calls: list[str] = []

    async def export_client_config(self, client_id: str) -> bytes:
        self.export_calls.append(client_id)
        config = self.configs.get(client_id)
        if config is None:
            raise RuntimeError(f"missing config for {client_id}")
        return config


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


def _registry(*, provider_enabled: bool = True) -> ServerRegistry:
    return ServerRegistry(
        {
            "vps-nl": RegisteredServer(
                key="vps-nl",
                title="VPS NL",
                connection=ConnectionConfig(mode=ConnectionMode.LOCAL),
                host_actions=HostActionsConfig(),
                providers=(
                    ProviderConfig(
                        type=ProviderType.WIREGUARD,
                        enabled=provider_enabled,
                    ),
                ),
                icon=None,
                sort_order=0,
                tags=(),
            )
        }
    )


@pytest.mark.asyncio
async def test_list_user_config_files_exports_linked_clients(
    database: DatabaseManager,
) -> None:
    inventory_service = ClientInventoryService(database)
    clients = await inventory_service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[
            VpnClientSyncItem(
                provider_client_id="peer-1",
                display_name="Alice Phone",
            ),
            VpnClientSyncItem(
                provider_client_id="peer-2",
                display_name="Bob Laptop",
            ),
        ],
    )
    await inventory_service.link_client_to_user(
        vpn_client_id=clients[0].id,
        telegram_user_id=1001,
    )
    await inventory_service.link_client_to_user(
        vpn_client_id=clients[1].id,
        telegram_user_id=2002,
    )
    provider = FakeProvider({"peer-1": b"[Interface]\nPrivateKey = xxx\n"})
    executor_factory = FakeExecutorFactory()
    service = ConfigDeliveryService(
        server_registry=_registry(),
        executor_factory=executor_factory,
        provider_factory=FakeProviderFactory(provider),
        client_inventory_service=inventory_service,
    )

    result = await service.list_user_config_files(telegram_user_id=1001)

    assert [item.provider_client_id for item in result.files] == ["peer-1"]
    assert result.files[0].filename == "vps-nl_wireguard_Alice_Phone.conf"
    assert result.files[0].content == b"[Interface]\nPrivateKey = xxx\n"
    assert result.errors == ()
    assert provider.export_calls == ["peer-1"]
    assert executor_factory.calls == ["vps-nl"]


@pytest.mark.asyncio
async def test_list_user_config_files_reports_export_errors(
    database: DatabaseManager,
) -> None:
    inventory_service = ClientInventoryService(database)
    clients = await inventory_service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice")],
    )
    await inventory_service.link_client_to_user(
        vpn_client_id=clients[0].id,
        telegram_user_id=1001,
    )
    service = ConfigDeliveryService(
        server_registry=_registry(provider_enabled=False),
        executor_factory=FakeExecutorFactory(),
        provider_factory=FakeProviderFactory(FakeProvider({})),
        client_inventory_service=inventory_service,
    )

    result = await service.list_user_config_files(telegram_user_id=1001)

    assert result.files == ()
    assert len(result.errors) == 1
    assert result.errors[0].provider_client_id == "peer-1"
    assert "Enabled provider" in result.errors[0].message


@pytest.mark.asyncio
async def test_export_client_config_file_exports_selected_client(
    database: DatabaseManager,
) -> None:
    inventory_service = ClientInventoryService(database)
    clients = await inventory_service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[
            VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice Phone"),
            VpnClientSyncItem(provider_client_id="peer-2", display_name="Bob Laptop"),
        ],
    )
    provider = FakeProvider({"peer-2": b"[Interface]\nPrivateKey = yyy\n"})
    service = ConfigDeliveryService(
        server_registry=_registry(),
        executor_factory=FakeExecutorFactory(),
        provider_factory=FakeProviderFactory(provider),
        client_inventory_service=inventory_service,
    )

    config_file = await service.export_client_config_file(vpn_client_id=clients[1].id)

    assert config_file.provider_client_id == "peer-2"
    assert config_file.filename == "vps-nl_wireguard_Bob_Laptop.conf"
    assert config_file.content == b"[Interface]\nPrivateKey = yyy\n"
    assert provider.export_calls == ["peer-2"]


@pytest.mark.asyncio
async def test_export_client_config_file_reports_missing_client(
    database: DatabaseManager,
) -> None:
    service = ConfigDeliveryService(
        server_registry=_registry(),
        executor_factory=FakeExecutorFactory(),
        provider_factory=FakeProviderFactory(FakeProvider({})),
        client_inventory_service=ClientInventoryService(database),
    )

    with pytest.raises(ValueError, match="VPN client 404 does not exist"):
        await service.export_client_config_file(vpn_client_id=404)
