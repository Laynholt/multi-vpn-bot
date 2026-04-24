"""Service layer for Telegram users."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.enums.common import UserStatus

if TYPE_CHECKING:
    from aiogram.types import User

    from app.infrastructure.db import DatabaseManager
    from app.infrastructure.db.models import TelegramUserORM


@dataclass(frozen=True, slots=True)
class TelegramUserSnapshot:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    is_bot: bool
    is_premium: bool
    is_admin: bool
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


@dataclass(frozen=True, slots=True)
class TelegramUserPage:
    items: list[TelegramUserSnapshot]
    total: int
    page: int
    page_size: int

    @property
    def has_next(self) -> bool:
        return (self.page + 1) * self.page_size < self.total


class TelegramUserService:
    """Coordinates Telegram user persistence and status checks."""

    DEFAULT_PAGE_SIZE = 8

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def sync_user(self, *, telegram_user: User, is_admin: bool) -> TelegramUserSnapshot:
        from app.infrastructure.db.repositories import TelegramUserRepository

        async with self._database.session() as session:
            repository = TelegramUserRepository(session)
            user = await repository.create_or_update(
                telegram_user_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code,
                is_bot=telegram_user.is_bot,
                is_premium=bool(telegram_user.is_premium),
                is_admin=is_admin,
            )
            return TelegramUserSnapshot(
                telegram_user_id=user.telegram_user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
                is_bot=user.is_bot,
                is_premium=user.is_premium,
                is_admin=user.is_admin,
                status=UserStatus(user.status),
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_seen_at=user.last_seen_at,
            )

    async def get_user(self, *, telegram_user_id: int) -> TelegramUserSnapshot | None:
        from app.infrastructure.db.repositories import TelegramUserRepository

        async with self._database.session() as session:
            repository = TelegramUserRepository(session)
            user = await repository.get_by_telegram_id(telegram_user_id)
            if user is None:
                return None
            return TelegramUserSnapshot(
                telegram_user_id=user.telegram_user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
                is_bot=user.is_bot,
                is_premium=user.is_premium,
                is_admin=user.is_admin,
                status=UserStatus(user.status),
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_seen_at=user.last_seen_at,
            )

    async def list_users(
        self,
        *,
        page: int,
        page_size: int | None = None,
    ) -> TelegramUserPage:
        normalized_page = max(0, page)
        size = page_size or self.DEFAULT_PAGE_SIZE
        offset = normalized_page * size

        async with self._database.session() as session:
            from app.infrastructure.db.repositories import TelegramUserRepository

            repository = TelegramUserRepository(session)
            users = await repository.list_page(offset=offset, limit=size)
            total = await repository.count()

        return TelegramUserPage(
            items=[self._to_snapshot(user) for user in users],
            total=total,
            page=normalized_page,
            page_size=size,
        )

    async def is_banned(self, *, telegram_user_id: int) -> bool:
        user = await self.get_user(telegram_user_id=telegram_user_id)
        return user is not None and user.status == UserStatus.BANNED

    async def ban_user(self, *, telegram_user_id: int) -> None:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import TelegramUserRepository

            repository = TelegramUserRepository(session)
            await repository.set_status(
                telegram_user_id=telegram_user_id,
                status=UserStatus.BANNED,
            )

    async def unban_user(self, *, telegram_user_id: int) -> None:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import TelegramUserRepository

            repository = TelegramUserRepository(session)
            await repository.set_status(
                telegram_user_id=telegram_user_id,
                status=UserStatus.ACTIVE,
            )

    async def soft_delete_user(self, *, telegram_user_id: int) -> None:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import TelegramUserRepository

            repository = TelegramUserRepository(session)
            await repository.set_status(
                telegram_user_id=telegram_user_id,
                status=UserStatus.DELETED,
            )

    def _to_snapshot(self, user: TelegramUserORM) -> TelegramUserSnapshot:
        return TelegramUserSnapshot(
            telegram_user_id=user.telegram_user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
            is_bot=user.is_bot,
            is_premium=user.is_premium,
            is_admin=user.is_admin,
            status=UserStatus(user.status),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_seen_at=user.last_seen_at,
        )
