from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest

from app.core.config.models import DatabaseConfig, ProviderType
from app.infrastructure.db import DatabaseManager
from app.infrastructure.db.repositories import TelegramUserRepository
from app.services.client_inventory import ClientInventoryService, VpnClientSyncItem
from app.services.traffic_stats import (
    TrafficCounterMode,
    TrafficStatsService,
    TrafficStatSyncItem,
)


@pytest.fixture
async def database(tmp_path) -> AsyncIterator[DatabaseManager]:  # noqa: ANN001
    manager = DatabaseManager(DatabaseConfig(sqlite_path=tmp_path / "test.db"))
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.dispose()


async def _create_linked_client(database: DatabaseManager) -> int:
    async with database.session() as session:
        repository = TelegramUserRepository(session)
        await repository.create_or_update(
            telegram_user_id=1001,
            username="vpn_user",
            first_name="VPN",
            last_name="User",
            language_code="ru",
            is_bot=False,
            is_premium=False,
            is_admin=False,
        )

    inventory = ClientInventoryService(database)
    clients = await inventory.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice")],
    )
    linked = await inventory.link_client_to_user(
        vpn_client_id=clients[0].id,
        telegram_user_id=1001,
    )
    return linked.id


@pytest.mark.asyncio
async def test_cumulative_samples_store_raw_deltas_and_daily_rollup(
    database: DatabaseManager,
) -> None:
    vpn_client_id = await _create_linked_client(database)
    service = TrafficStatsService(database, daily_rollup_timezone="Europe/Moscow")
    captured_at = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)

    first = await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                rx_bytes_total=1_000,
                tx_bytes_total=2_000,
                captured_at=captured_at,
            )
        ],
    )
    second = await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                rx_bytes_total=1_250,
                tx_bytes_total=2_500,
                captured_at=datetime(2026, 4, 24, 12, 15, tzinfo=UTC),
                metadata={"source": "wg"},
            )
        ],
    )

    daily = await service.list_daily_stats_for_client(
        vpn_client_id=vpn_client_id,
        date_from=date(2026, 4, 24),
        date_to=date(2026, 4, 24),
    )
    raw = await service.list_raw_samples_for_client(vpn_client_id=vpn_client_id)

    assert first[0].rx_bytes_delta == 0
    assert first[0].tx_bytes_delta == 0
    assert second[0].rx_bytes_delta == 250
    assert second[0].tx_bytes_delta == 500
    assert second[0].telegram_user_id == 1001
    assert second[0].metadata == {"source": "wg"}
    assert len(raw) == 2
    assert daily[0].rx_bytes == 250
    assert daily[0].tx_bytes == 500
    assert daily[0].total_bytes == 750


@pytest.mark.asyncio
async def test_current_period_samples_use_reported_delta(
    database: DatabaseManager,
) -> None:
    vpn_client_id = await _create_linked_client(database)
    service = TrafficStatsService(database, daily_rollup_timezone="Europe/Moscow")

    samples = await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                counter_mode=TrafficCounterMode.CURRENT,
                rx_bytes_delta=80,
                tx_bytes_delta=20,
                captured_at=datetime(2026, 4, 24, 10, 0, tzinfo=UTC),
            )
        ],
    )

    daily = await service.list_daily_stats_for_client(
        vpn_client_id=vpn_client_id,
        date_from=date(2026, 4, 24),
        date_to=date(2026, 4, 24),
    )

    assert samples[0].rx_bytes_total == 80
    assert samples[0].tx_bytes_total == 20
    assert samples[0].rx_bytes_delta == 80
    assert samples[0].tx_bytes_delta == 20
    assert daily[0].rx_bytes == 80
    assert daily[0].tx_bytes == 20


@pytest.mark.asyncio
async def test_counter_reset_clamps_negative_delta_to_zero(
    database: DatabaseManager,
) -> None:
    vpn_client_id = await _create_linked_client(database)
    service = TrafficStatsService(database, daily_rollup_timezone="Europe/Moscow")

    await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                rx_bytes_total=1_000,
                tx_bytes_total=2_000,
                captured_at=datetime(2026, 4, 24, 10, 0, tzinfo=UTC),
            )
        ],
    )
    reset_samples = await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                rx_bytes_total=50,
                tx_bytes_total=70,
                captured_at=datetime(2026, 4, 24, 10, 15, tzinfo=UTC),
            )
        ],
    )

    daily = await service.list_daily_stats_for_client(
        vpn_client_id=vpn_client_id,
        date_from=date(2026, 4, 24),
        date_to=date(2026, 4, 24),
    )

    assert reset_samples[0].rx_bytes_delta == 0
    assert reset_samples[0].tx_bytes_delta == 0
    assert daily[0].rx_bytes == 0
    assert daily[0].tx_bytes == 0


@pytest.mark.asyncio
async def test_disabled_raw_storage_still_updates_daily_rollup(
    database: DatabaseManager,
) -> None:
    vpn_client_id = await _create_linked_client(database)
    service = TrafficStatsService(
        database,
        store_raw_samples=False,
        daily_rollup_timezone="Europe/Moscow",
    )

    recorded = await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                counter_mode=TrafficCounterMode.CURRENT,
                rx_bytes_delta=10,
                tx_bytes_delta=30,
                captured_at=datetime(2026, 4, 24, 10, 0, tzinfo=UTC),
            )
        ],
    )

    raw = await service.list_raw_samples_for_client(vpn_client_id=vpn_client_id)
    daily = await service.list_daily_stats_for_client(
        vpn_client_id=vpn_client_id,
        date_from=date(2026, 4, 24),
        date_to=date(2026, 4, 24),
    )

    assert recorded[0].id is None
    assert raw == []
    assert daily[0].rx_bytes == 10
    assert daily[0].tx_bytes == 30


@pytest.mark.asyncio
async def test_summarize_daily_stats_for_user_aggregates_linked_clients(
    database: DatabaseManager,
) -> None:
    first_client_id = await _create_linked_client(database)
    inventory = ClientInventoryService(database)
    other_clients = await inventory.sync_provider_clients(
        server_key="vps-de",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-2", display_name="Bob")],
    )
    await inventory.link_client_to_user(
        vpn_client_id=other_clients[0].id,
        telegram_user_id=1001,
    )
    service = TrafficStatsService(database, daily_rollup_timezone="Europe/Moscow")

    await service.record_provider_samples(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-1",
                counter_mode=TrafficCounterMode.CURRENT,
                rx_bytes_delta=100,
                tx_bytes_delta=200,
                captured_at=datetime(2026, 4, 24, 10, 0, tzinfo=UTC),
            )
        ],
    )
    await service.record_provider_samples(
        server_key="vps-de",
        provider_type=ProviderType.WIREGUARD,
        samples=[
            TrafficStatSyncItem(
                provider_client_id="peer-2",
                counter_mode=TrafficCounterMode.CURRENT,
                rx_bytes_delta=50,
                tx_bytes_delta=75,
                captured_at=datetime(2026, 4, 24, 11, 0, tzinfo=UTC),
            )
        ],
    )

    summary = await service.summarize_daily_stats_for_user(
        telegram_user_id=1001,
        date_from=date(2026, 4, 24),
        date_to=date(2026, 4, 24),
    )

    assert summary.telegram_user_id == 1001
    assert summary.rx_bytes == 150
    assert summary.tx_bytes == 275
    assert summary.total_bytes == 425
    assert [(client.display_name, client.total_bytes) for client in summary.clients] == [
        ("Alice", 300),
        ("Bob", 125),
    ]
    assert {client.vpn_client_id for client in summary.clients} == {
        first_client_id,
        other_clients[0].id,
    }
