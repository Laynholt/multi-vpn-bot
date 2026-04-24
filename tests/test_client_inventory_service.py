from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.core.config.models import DatabaseConfig, ProviderType
from app.domain.enums.common import ClientStatus
from app.infrastructure.db import DatabaseManager
from app.infrastructure.db.repositories import TelegramUserRepository
from app.services.client_inventory import ClientInventoryService, VpnClientSyncItem


@pytest.fixture
async def database(tmp_path) -> AsyncIterator[DatabaseManager]:  # noqa: ANN001
    manager = DatabaseManager(DatabaseConfig(sqlite_path=tmp_path / "test.db"))
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.dispose()


async def _create_telegram_user(database: DatabaseManager, telegram_user_id: int) -> None:
    async with database.session() as session:
        repository = TelegramUserRepository(session)
        await repository.create_or_update(
            telegram_user_id=telegram_user_id,
            username="vpn_user",
            first_name="VPN",
            last_name="User",
            language_code="ru",
            is_bot=False,
            is_premium=False,
            is_admin=False,
        )


@pytest.mark.asyncio
async def test_sync_provider_clients_creates_normalized_clients(
    database: DatabaseManager,
) -> None:
    service = ClientInventoryService(database)

    clients = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[
            VpnClientSyncItem(
                provider_client_id="peer-1",
                display_name="Alice Phone",
                status=ClientStatus.ACTIVE,
                metadata={"public_key": "abc"},
            )
        ],
    )

    assert len(clients) == 1
    assert clients[0].server_key == "vps-nl"
    assert clients[0].provider_type == ProviderType.WIREGUARD
    assert clients[0].provider_client_id == "peer-1"
    assert clients[0].display_name == "Alice Phone"
    assert clients[0].status == ClientStatus.ACTIVE
    assert clients[0].metadata == {"public_key": "abc"}
    assert clients[0].telegram_user_ids == ()


@pytest.mark.asyncio
async def test_sync_provider_clients_updates_existing_identity_on_rename(
    database: DatabaseManager,
) -> None:
    service = ClientInventoryService(database)
    first = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Old")],
    )

    second = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[
            VpnClientSyncItem(
                provider_client_id="peer-1",
                display_name="New",
                status=ClientStatus.DISABLED,
            )
        ],
    )

    assert second[0].id == first[0].id
    assert second[0].display_name == "New"
    assert second[0].status == ClientStatus.DISABLED


@pytest.mark.asyncio
async def test_link_client_to_user_is_idempotent_and_listable(
    database: DatabaseManager,
) -> None:
    await _create_telegram_user(database, telegram_user_id=1001)
    service = ClientInventoryService(database)
    clients = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice")],
    )

    linked = await service.link_client_to_user(
        vpn_client_id=clients[0].id,
        telegram_user_id=1001,
    )
    linked_again = await service.link_client_to_user(
        vpn_client_id=clients[0].id,
        telegram_user_id=1001,
    )
    user_clients = await service.list_clients_for_user(telegram_user_id=1001)

    assert linked.telegram_user_ids == (1001,)
    assert linked_again.telegram_user_ids == (1001,)
    assert [client.id for client in user_clients] == [clients[0].id]


@pytest.mark.asyncio
async def test_soft_deleted_clients_are_not_returned_for_user_by_default(
    database: DatabaseManager,
) -> None:
    await _create_telegram_user(database, telegram_user_id=1001)
    service = ClientInventoryService(database)
    clients = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[
            VpnClientSyncItem(
                provider_client_id="peer-1",
                display_name="Alice",
                status=ClientStatus.DELETED,
            )
        ],
    )
    await service.link_client_to_user(vpn_client_id=clients[0].id, telegram_user_id=1001)

    assert await service.list_clients_for_user(telegram_user_id=1001) == []
    assert (
        len(await service.list_clients_for_user(telegram_user_id=1001, include_deleted=True)) == 1
    )


@pytest.mark.asyncio
async def test_list_clients_for_provider_filters_identity_and_deleted(
    database: DatabaseManager,
) -> None:
    service = ClientInventoryService(database)
    await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[
            VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice"),
            VpnClientSyncItem(
                provider_client_id="peer-deleted",
                display_name="Deleted",
                status=ClientStatus.DELETED,
            ),
        ],
    )
    await service.sync_provider_clients(
        server_key="vps-de",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-2", display_name="Bob")],
    )
    await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.X3UI,
        clients=[VpnClientSyncItem(provider_client_id="x3ui-1", display_name="Carol")],
    )

    active_clients = await service.list_clients_for_provider(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
    )
    all_clients = await service.list_clients_for_provider(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        include_deleted=True,
    )

    assert [client.provider_client_id for client in active_clients] == ["peer-1"]
    assert [client.provider_client_id for client in all_clients] == [
        "peer-1",
        "peer-deleted",
    ]


@pytest.mark.asyncio
async def test_get_and_mark_provider_client_deleted(
    database: DatabaseManager,
) -> None:
    service = ClientInventoryService(database)
    clients = await service.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice")],
    )

    fetched = await service.get_client(clients[0].id)
    deleted = await service.mark_provider_client_deleted(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        provider_client_id="peer-1",
    )
    active_clients = await service.list_clients_for_provider(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
    )

    assert fetched is not None
    assert fetched.provider_client_id == "peer-1"
    assert deleted is not None
    assert deleted.status == ClientStatus.DELETED
    assert active_clients == []
