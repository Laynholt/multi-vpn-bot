"""Middleware that synchronizes Telegram users into the local database."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.permissions import AccessService
from app.services.users import TelegramUserService


class UserSyncMiddleware(BaseMiddleware):
    """Persists Telegram users and blocks banned non-admin users."""

    def __init__(
        self,
        *,
        user_service: TelegramUserService,
        access_service: AccessService,
    ) -> None:
        self._user_service = user_service
        self._access_service = access_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = None
        if isinstance(event, Message | CallbackQuery):
            from_user = event.from_user

        if from_user is None:
            return await handler(event, data)

        snapshot = await self._user_service.sync_user(
            telegram_user=from_user,
            is_admin=self._access_service.is_admin(from_user.id),
        )
        data["telegram_user"] = snapshot

        if snapshot.status.value == "banned" and not snapshot.is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer("Ваш доступ ограничен администратором.", show_alert=True)
                return None
            if isinstance(event, Message):
                await event.answer("Ваш доступ ограничен администратором.")
                return None

        return await handler(event, data)
