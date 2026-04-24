"""Repositories for traffic statistics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.common import StatPeriodType
from app.infrastructure.db.models import TrafficStatDailyORM, TrafficStatSampleORM


class TrafficStatSampleRepository:
    """Persistence helpers for raw traffic samples."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_sample(
        self,
        *,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
        captured_at: datetime,
        rx_bytes_total: int,
        tx_bytes_total: int,
        rx_bytes_delta: int = 0,
        tx_bytes_delta: int = 0,
        telegram_user_id: int | None = None,
        period_type: str = StatPeriodType.RAW.value,
        metadata: dict[str, Any] | None = None,
    ) -> TrafficStatSampleORM:
        sample = TrafficStatSampleORM(
            server_key=server_key,
            provider_type=provider_type,
            provider_client_id=provider_client_id,
            telegram_user_id=telegram_user_id,
            captured_at=captured_at,
            rx_bytes_total=rx_bytes_total,
            tx_bytes_total=tx_bytes_total,
            rx_bytes_delta=rx_bytes_delta,
            tx_bytes_delta=tx_bytes_delta,
            period_type=period_type,
            metadata_json=metadata or {},
        )
        self._session.add(sample)
        await self._session.flush()
        return sample

    async def get_latest_sample(
        self,
        *,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
    ) -> TrafficStatSampleORM | None:
        query = (
            select(TrafficStatSampleORM)
            .where(
                TrafficStatSampleORM.server_key == server_key,
                TrafficStatSampleORM.provider_type == provider_type,
                TrafficStatSampleORM.provider_client_id == provider_client_id,
            )
            .order_by(desc(TrafficStatSampleORM.captured_at))
            .limit(1)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_samples(
        self,
        *,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
    ) -> list[TrafficStatSampleORM]:
        query = (
            select(TrafficStatSampleORM)
            .where(
                TrafficStatSampleORM.server_key == server_key,
                TrafficStatSampleORM.provider_type == provider_type,
                TrafficStatSampleORM.provider_client_id == provider_client_id,
            )
            .order_by(TrafficStatSampleORM.captured_at, TrafficStatSampleORM.id)
        )
        if captured_from is not None:
            query = query.where(TrafficStatSampleORM.captured_at >= captured_from)
        if captured_to is not None:
            query = query.where(TrafficStatSampleORM.captured_at < captured_to)

        result = await self._session.execute(query)
        return list(result.scalars().all())


class TrafficStatDailyRepository:
    """Persistence helpers for daily traffic aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_identity(
        self,
        *,
        stat_date: date,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
    ) -> TrafficStatDailyORM | None:
        query = select(TrafficStatDailyORM).where(
            TrafficStatDailyORM.stat_date == stat_date,
            TrafficStatDailyORM.server_key == server_key,
            TrafficStatDailyORM.provider_type == provider_type,
            TrafficStatDailyORM.provider_client_id == provider_client_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def add_delta(
        self,
        *,
        stat_date: date,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
        rx_bytes_delta: int,
        tx_bytes_delta: int,
        telegram_user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrafficStatDailyORM:
        daily = await self.get_by_identity(
            stat_date=stat_date,
            server_key=server_key,
            provider_type=provider_type,
            provider_client_id=provider_client_id,
        )
        if daily is None:
            daily = TrafficStatDailyORM(
                stat_date=stat_date,
                server_key=server_key,
                provider_type=provider_type,
                provider_client_id=provider_client_id,
                telegram_user_id=telegram_user_id,
                rx_bytes=rx_bytes_delta,
                tx_bytes=tx_bytes_delta,
                total_bytes=rx_bytes_delta + tx_bytes_delta,
                metadata_json=metadata or {},
            )
            self._session.add(daily)
            await self._session.flush()
            return daily

        daily.telegram_user_id = telegram_user_id
        daily.rx_bytes += rx_bytes_delta
        daily.tx_bytes += tx_bytes_delta
        daily.total_bytes = daily.rx_bytes + daily.tx_bytes
        daily.metadata_json = metadata or daily.metadata_json
        await self._session.flush()
        return daily

    async def replace_totals(
        self,
        *,
        stat_date: date,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
        rx_bytes: int,
        tx_bytes: int,
        telegram_user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrafficStatDailyORM:
        daily = await self.get_by_identity(
            stat_date=stat_date,
            server_key=server_key,
            provider_type=provider_type,
            provider_client_id=provider_client_id,
        )
        if daily is None:
            daily = TrafficStatDailyORM(
                stat_date=stat_date,
                server_key=server_key,
                provider_type=provider_type,
                provider_client_id=provider_client_id,
                telegram_user_id=telegram_user_id,
            )
            self._session.add(daily)

        daily.rx_bytes = rx_bytes
        daily.tx_bytes = tx_bytes
        daily.total_bytes = rx_bytes + tx_bytes
        daily.telegram_user_id = telegram_user_id
        daily.metadata_json = metadata or {}
        await self._session.flush()
        return daily

    async def list_by_identity(
        self,
        *,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TrafficStatDailyORM]:
        query = (
            select(TrafficStatDailyORM)
            .where(
                TrafficStatDailyORM.server_key == server_key,
                TrafficStatDailyORM.provider_type == provider_type,
                TrafficStatDailyORM.provider_client_id == provider_client_id,
            )
            .order_by(TrafficStatDailyORM.stat_date)
        )
        if date_from is not None:
            query = query.where(TrafficStatDailyORM.stat_date >= date_from)
        if date_to is not None:
            query = query.where(TrafficStatDailyORM.stat_date <= date_to)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def delete_for_date(self, stat_date: date) -> None:
        await self._session.execute(
            delete(TrafficStatDailyORM).where(TrafficStatDailyORM.stat_date == stat_date)
        )
        await self._session.flush()
