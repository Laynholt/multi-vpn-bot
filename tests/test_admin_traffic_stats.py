from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest

from app.core.config.models import DatabaseConfig, ProviderType
from app.infrastructure.db import DatabaseManager
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


@pytest.mark.asyncio
async def test_admin_daily_summary_filters_by_server_and_aggregates_clients(
    database: DatabaseManager,
) -> None:
    inventory = ClientInventoryService(database)
    first = await inventory.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice")],
    )
    second = await inventory.sync_provider_clients(
        server_key="vps-de",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-2", display_name="Bob")],
    )
    await inventory.link_client_to_user(vpn_client_id=first[0].id, telegram_user_id=1001)
    await inventory.link_client_to_user(vpn_client_id=second[0].id, telegram_user_id=1002)

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

    summary = await service.summarize_daily_stats_for_admin(
        server_key="vps-nl",
        date_from=date(2026, 4, 24),
        date_to=date(2026, 4, 24),
    )

    assert summary.server_key == "vps-nl"
    assert summary.rx_bytes == 100
    assert summary.tx_bytes == 200
    assert summary.total_bytes == 300
    assert [(client.display_name, client.telegram_user_id) for client in summary.clients] == [
        ("Alice", 1001)
    ]


@pytest.mark.asyncio
async def test_admin_daily_csv_export_contains_header_and_rows(
    database: DatabaseManager,
) -> None:
    inventory = ClientInventoryService(database)
    clients = await inventory.sync_provider_clients(
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        clients=[VpnClientSyncItem(provider_client_id="peer-1", display_name="Alice")],
    )
    await inventory.link_client_to_user(vpn_client_id=clients[0].id, telegram_user_id=1001)
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

    summary = await service.summarize_daily_stats_for_admin()
    csv_bytes = service.export_admin_daily_csv(summary, delimiter=",")
    csv_text = csv_bytes.decode("utf-8")

    assert "server_key,provider_type,provider_client_id,display_name" in csv_text
    assert "vps-nl,wireguard,peer-1,Alice,1001,100,200,300" in csv_text
