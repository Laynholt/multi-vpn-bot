"""Service layer for normalized traffic statistics."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from app.core.config.models import ProviderType, StatisticsConfig
from app.domain.enums.common import StatPeriodType

if TYPE_CHECKING:
    from app.core.executors import ExecutorFactory
    from app.core.registry import ServerRegistry
    from app.infrastructure.db import DatabaseManager
    from app.infrastructure.db.models import TrafficStatDailyORM, TrafficStatSampleORM
    from app.providers import ProviderFactory


class TrafficCounterMode(StrEnum):
    """How provider traffic counters should be interpreted."""

    CUMULATIVE = "cumulative"
    CURRENT = "current"


@dataclass(frozen=True, slots=True)
class TrafficStatSyncItem:
    """Provider traffic payload normalized before persistence."""

    provider_client_id: str
    captured_at: datetime
    counter_mode: TrafficCounterMode = TrafficCounterMode.CUMULATIVE
    rx_bytes_total: int | None = None
    tx_bytes_total: int | None = None
    rx_bytes_delta: int | None = None
    tx_bytes_delta: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrafficStatSnapshot:
    """Read model for a raw traffic sample."""

    id: int | None
    server_key: str
    provider_type: ProviderType
    provider_client_id: str
    telegram_user_id: int | None
    captured_at: datetime
    rx_bytes_total: int
    tx_bytes_total: int
    rx_bytes_delta: int
    tx_bytes_delta: int
    period_type: StatPeriodType
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TrafficDailySnapshot:
    """Read model for a daily traffic aggregate."""

    id: int
    stat_date: date
    server_key: str
    provider_type: ProviderType
    provider_client_id: str
    telegram_user_id: int | None
    rx_bytes: int
    tx_bytes: int
    total_bytes: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TrafficStatsService:
    """Coordinates raw traffic samples, delta calculation and daily aggregates."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        store_raw_samples: bool = True,
        daily_rollup_timezone: str = "Europe/Moscow",
    ) -> None:
        self._database = database
        self._store_raw_samples = store_raw_samples
        self._daily_rollup_timezone = ZoneInfo(daily_rollup_timezone)

    @classmethod
    def from_config(
        cls,
        database: DatabaseManager,
        statistics_config: StatisticsConfig,
    ) -> TrafficStatsService:
        return cls(
            database,
            store_raw_samples=statistics_config.store_raw_samples,
            daily_rollup_timezone=statistics_config.daily_rollup_timezone,
        )

    async def record_provider_samples(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
        samples: list[TrafficStatSyncItem],
    ) -> list[TrafficStatSnapshot]:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import (
                TrafficStatDailyRepository,
                TrafficStatSampleRepository,
                VpnClientRepository,
            )

            sample_repository = TrafficStatSampleRepository(session)
            daily_repository = TrafficStatDailyRepository(session)
            client_repository = VpnClientRepository(session)

            snapshots: list[TrafficStatSnapshot] = []
            for item in samples:
                previous = await sample_repository.get_latest_sample(
                    server_key=server_key,
                    provider_type=provider_type.value,
                    provider_client_id=item.provider_client_id,
                )
                rx_total, tx_total, rx_delta, tx_delta = self._calculate_traffic(
                    item,
                    previous,
                )
                client = await client_repository.get_by_identity(
                    server_key=server_key,
                    provider_type=provider_type.value,
                    provider_client_id=item.provider_client_id,
                )
                telegram_user_id = None
                if client is not None:
                    linked_user_ids = await client_repository.list_linked_user_ids(client.id)
                    telegram_user_id = linked_user_ids[0] if linked_user_ids else None

                persisted_sample = None
                if self._store_raw_samples:
                    persisted_sample = await sample_repository.add_sample(
                        server_key=server_key,
                        provider_type=provider_type.value,
                        provider_client_id=item.provider_client_id,
                        captured_at=item.captured_at,
                        rx_bytes_total=rx_total,
                        tx_bytes_total=tx_total,
                        rx_bytes_delta=rx_delta,
                        tx_bytes_delta=tx_delta,
                        telegram_user_id=telegram_user_id,
                        metadata=item.metadata,
                    )

                await daily_repository.add_delta(
                    stat_date=self._stat_date(item.captured_at),
                    server_key=server_key,
                    provider_type=provider_type.value,
                    provider_client_id=item.provider_client_id,
                    rx_bytes_delta=rx_delta,
                    tx_bytes_delta=tx_delta,
                    telegram_user_id=telegram_user_id,
                    metadata={"last_captured_at": item.captured_at.isoformat()},
                )
                snapshots.append(
                    self._to_sample_snapshot(
                        sample=persisted_sample,
                        server_key=server_key,
                        provider_type=provider_type,
                        provider_client_id=item.provider_client_id,
                        telegram_user_id=telegram_user_id,
                        captured_at=item.captured_at,
                        rx_bytes_total=rx_total,
                        tx_bytes_total=tx_total,
                        rx_bytes_delta=rx_delta,
                        tx_bytes_delta=tx_delta,
                        metadata=item.metadata,
                    )
                )
            return snapshots

    async def list_raw_samples_for_client(
        self,
        *,
        vpn_client_id: int,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
    ) -> list[TrafficStatSnapshot]:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import (
                TrafficStatSampleRepository,
                VpnClientRepository,
            )

            client_repository = VpnClientRepository(session)
            client = await client_repository.get_by_id(vpn_client_id)
            if client is None:
                raise ValueError(f"VPN client {vpn_client_id} does not exist")

            sample_repository = TrafficStatSampleRepository(session)
            samples = await sample_repository.list_samples(
                server_key=client.server_key,
                provider_type=client.provider_type,
                provider_client_id=client.provider_client_id,
                captured_from=captured_from,
                captured_to=captured_to,
            )
            return [self._to_persisted_sample_snapshot(sample) for sample in samples]

    async def list_daily_stats_for_client(
        self,
        *,
        vpn_client_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TrafficDailySnapshot]:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import (
                TrafficStatDailyRepository,
                VpnClientRepository,
            )

            client_repository = VpnClientRepository(session)
            client = await client_repository.get_by_id(vpn_client_id)
            if client is None:
                raise ValueError(f"VPN client {vpn_client_id} does not exist")

            daily_repository = TrafficStatDailyRepository(session)
            rows = await daily_repository.list_by_identity(
                server_key=client.server_key,
                provider_type=client.provider_type,
                provider_client_id=client.provider_client_id,
                date_from=date_from,
                date_to=date_to,
            )
            return [self._to_daily_snapshot(row) for row in rows]

    async def rebuild_daily_rollup(self, stat_date: date) -> list[TrafficDailySnapshot]:
        """Rebuild a single local-date daily aggregate from stored raw samples."""

        start_local = datetime.combine(
            stat_date,
            time.min,
            tzinfo=self._daily_rollup_timezone,
        )
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(UTC)
        end_utc = end_local.astimezone(UTC)

        async with self._database.session() as session:
            from sqlalchemy import select

            from app.infrastructure.db.models import VpnClientORM
            from app.infrastructure.db.repositories import (
                TrafficStatDailyRepository,
                TrafficStatSampleRepository,
                VpnClientRepository,
            )

            client_repository = VpnClientRepository(session)
            sample_repository = TrafficStatSampleRepository(session)
            daily_repository = TrafficStatDailyRepository(session)
            await daily_repository.delete_for_date(stat_date)

            result = await session.execute(select(VpnClientORM).order_by(VpnClientORM.id))
            snapshots: list[TrafficDailySnapshot] = []
            for client in result.scalars().all():
                samples = await sample_repository.list_samples(
                    server_key=client.server_key,
                    provider_type=client.provider_type,
                    provider_client_id=client.provider_client_id,
                    captured_from=start_utc,
                    captured_to=end_utc,
                )
                if not samples:
                    continue

                linked_user_ids = await client_repository.list_linked_user_ids(client.id)
                telegram_user_id = linked_user_ids[0] if linked_user_ids else None
                rx_bytes = sum(sample.rx_bytes_delta for sample in samples)
                tx_bytes = sum(sample.tx_bytes_delta for sample in samples)
                daily = await daily_repository.replace_totals(
                    stat_date=stat_date,
                    server_key=client.server_key,
                    provider_type=client.provider_type,
                    provider_client_id=client.provider_client_id,
                    rx_bytes=rx_bytes,
                    tx_bytes=tx_bytes,
                    telegram_user_id=telegram_user_id,
                    metadata={"source": "rollup"},
                )
                snapshots.append(self._to_daily_snapshot(daily))
            return snapshots

    def _calculate_traffic(
        self,
        item: TrafficStatSyncItem,
        previous: TrafficStatSampleORM | None,
    ) -> tuple[int, int, int, int]:
        if item.counter_mode == TrafficCounterMode.CURRENT:
            rx_delta = max(item.rx_bytes_delta or 0, 0)
            tx_delta = max(item.tx_bytes_delta or 0, 0)
            rx_total = item.rx_bytes_total if item.rx_bytes_total is not None else rx_delta
            tx_total = item.tx_bytes_total if item.tx_bytes_total is not None else tx_delta
            return rx_total, tx_total, rx_delta, tx_delta

        if item.rx_bytes_total is None or item.tx_bytes_total is None:
            raise ValueError("Cumulative traffic samples require total counters")

        if previous is None:
            return item.rx_bytes_total, item.tx_bytes_total, 0, 0

        rx_delta = max(item.rx_bytes_total - previous.rx_bytes_total, 0)
        tx_delta = max(item.tx_bytes_total - previous.tx_bytes_total, 0)
        return item.rx_bytes_total, item.tx_bytes_total, rx_delta, tx_delta

    def _stat_date(self, captured_at: datetime) -> date:
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        return captured_at.astimezone(self._daily_rollup_timezone).date()

    def _to_sample_snapshot(
        self,
        *,
        sample: TrafficStatSampleORM | None,
        server_key: str,
        provider_type: ProviderType,
        provider_client_id: str,
        telegram_user_id: int | None,
        captured_at: datetime,
        rx_bytes_total: int,
        tx_bytes_total: int,
        rx_bytes_delta: int,
        tx_bytes_delta: int,
        metadata: dict[str, Any],
    ) -> TrafficStatSnapshot:
        return TrafficStatSnapshot(
            id=sample.id if sample is not None else None,
            server_key=server_key,
            provider_type=provider_type,
            provider_client_id=provider_client_id,
            telegram_user_id=telegram_user_id,
            captured_at=captured_at,
            rx_bytes_total=rx_bytes_total,
            tx_bytes_total=tx_bytes_total,
            rx_bytes_delta=rx_bytes_delta,
            tx_bytes_delta=tx_bytes_delta,
            period_type=StatPeriodType.RAW,
            metadata=dict(metadata),
        )

    def _to_persisted_sample_snapshot(
        self,
        sample: TrafficStatSampleORM,
    ) -> TrafficStatSnapshot:
        return TrafficStatSnapshot(
            id=sample.id,
            server_key=sample.server_key,
            provider_type=ProviderType(sample.provider_type),
            provider_client_id=sample.provider_client_id,
            telegram_user_id=sample.telegram_user_id,
            captured_at=sample.captured_at,
            rx_bytes_total=sample.rx_bytes_total,
            tx_bytes_total=sample.tx_bytes_total,
            rx_bytes_delta=sample.rx_bytes_delta,
            tx_bytes_delta=sample.tx_bytes_delta,
            period_type=StatPeriodType(sample.period_type),
            metadata=dict(sample.metadata_json),
        )

    def _to_daily_snapshot(self, daily: TrafficStatDailyORM) -> TrafficDailySnapshot:
        return TrafficDailySnapshot(
            id=daily.id,
            stat_date=daily.stat_date,
            server_key=daily.server_key,
            provider_type=ProviderType(daily.provider_type),
            provider_client_id=daily.provider_client_id,
            telegram_user_id=daily.telegram_user_id,
            rx_bytes=daily.rx_bytes,
            tx_bytes=daily.tx_bytes,
            total_bytes=daily.total_bytes,
            metadata=dict(daily.metadata_json),
            created_at=daily.created_at,
            updated_at=daily.updated_at,
        )


class TrafficStatsCollector:
    """Periodic provider polling coordinator for traffic statistics."""

    def __init__(
        self,
        *,
        statistics_config: StatisticsConfig,
        server_registry: ServerRegistry,
        provider_factory: ProviderFactory,
        traffic_stats_service: TrafficStatsService,
        executor_factory: ExecutorFactory | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._statistics_config = statistics_config
        self._server_registry = server_registry
        self._provider_factory = provider_factory
        self._traffic_stats_service = traffic_stats_service
        self._executor_factory = executor_factory
        self._sleep = sleep

    @property
    def interval_seconds(self) -> int:
        return self._statistics_config.collect_interval_minutes * 60

    async def collect_once(self) -> list[TrafficStatSnapshot]:
        if not self._statistics_config.enabled:
            return []

        snapshots: list[TrafficStatSnapshot] = []
        for server in self._server_registry.list_servers():
            for provider_config in server.providers:
                if not provider_config.enabled:
                    continue
                executor = (
                    self._executor_factory.for_server(server)
                    if self._executor_factory is not None
                    else None
                )
                provider = self._provider_factory.create(provider_config, executor=executor)
                if not provider.capabilities.collect_client_stats:
                    continue
                payloads = await provider.collect_client_stats()
                items = [self._sync_item_from_provider_payload(payload) for payload in payloads]
                snapshots.extend(
                    await self._traffic_stats_service.record_provider_samples(
                        server_key=server.key,
                        provider_type=provider_config.type,
                        samples=items,
                    )
                )
        return snapshots

    async def run_forever(self) -> None:
        while True:
            await self.collect_once()
            await self._sleep(self.interval_seconds)

    def _sync_item_from_provider_payload(self, payload: dict[str, Any]) -> TrafficStatSyncItem:
        provider_client_id = str(
            payload.get("provider_client_id") or payload.get("client_id") or payload["id"]
        )
        counter_mode = TrafficCounterMode(
            payload.get("counter_mode", TrafficCounterMode.CUMULATIVE)
        )
        captured_at = payload.get("captured_at")
        if not isinstance(captured_at, datetime):
            captured_at = datetime.now(UTC)

        return TrafficStatSyncItem(
            provider_client_id=provider_client_id,
            captured_at=captured_at,
            counter_mode=counter_mode,
            rx_bytes_total=payload.get("rx_bytes_total"),
            tx_bytes_total=payload.get("tx_bytes_total"),
            rx_bytes_delta=payload.get("rx_bytes_delta"),
            tx_bytes_delta=payload.get("tx_bytes_delta"),
            metadata=dict(payload.get("metadata") or {}),
        )
