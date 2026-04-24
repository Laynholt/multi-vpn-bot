"""Repository for traffic samples."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.common import StatPeriodType
from app.infrastructure.db.models import TrafficStatSampleORM


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
