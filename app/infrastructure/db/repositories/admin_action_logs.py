"""Repository for admin action audit logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import AdminActionLogORM


class AdminActionLogRepository:
    """Persistence helpers for auditable admin actions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        admin_telegram_user_id: int,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AdminActionLogORM:
        entry = AdminActionLogORM(
            admin_telegram_user_id=admin_telegram_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload_json=payload or {},
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_recent(self, *, limit: int) -> list[AdminActionLogORM]:
        query = (
            select(AdminActionLogORM)
            .order_by(desc(AdminActionLogORM.created_at), desc(AdminActionLogORM.id))
            .limit(limit)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())
