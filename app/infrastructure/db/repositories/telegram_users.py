"""Repository for telegram users."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.common import UserStatus
from app.infrastructure.db.models import TelegramUserORM


class TelegramUserRepository:
    """CRUD helpers for telegram users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> TelegramUserORM | None:
        query = select(TelegramUserORM).where(TelegramUserORM.telegram_user_id == telegram_user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_bot: bool,
        is_premium: bool,
        is_admin: bool,
    ) -> TelegramUserORM:
        user = await self.get_by_telegram_id(telegram_user_id)
        now = datetime.now(UTC)

        if user is None:
            user = TelegramUserORM(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_bot=is_bot,
                is_premium=is_premium,
                is_admin=is_admin,
                last_seen_at=now,
                status=UserStatus.ACTIVE.value,
            )
            self._session.add(user)
            await self._session.flush()
            return user

        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        user.is_bot = is_bot
        user.is_premium = is_premium
        user.is_admin = is_admin
        user.last_seen_at = now
        await self._session.flush()
        return user

    async def list_all(self) -> list[TelegramUserORM]:
        query = select(TelegramUserORM).order_by(TelegramUserORM.created_at.desc())
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_page(self, *, offset: int, limit: int) -> list[TelegramUserORM]:
        query = (
            select(TelegramUserORM)
            .order_by(TelegramUserORM.created_at.desc(), TelegramUserORM.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        query = select(func.count()).select_from(TelegramUserORM)
        result = await self._session.execute(query)
        return int(result.scalar_one())

    async def set_status(
        self, *, telegram_user_id: int, status: UserStatus
    ) -> TelegramUserORM | None:
        user = await self.get_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        user.status = status.value
        user.updated_at = datetime.now(UTC)
        await self._session.flush()
        return user
