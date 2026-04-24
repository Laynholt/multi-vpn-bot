"""Middleware that injects application context and resolved role."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.context import ApplicationContext
from app.core.permissions import AccessService


class ContextMiddleware(BaseMiddleware):
    """Injects shared runtime dependencies into handler data."""

    def __init__(
        self,
        *,
        app_context: ApplicationContext,
        access_service: AccessService,
    ) -> None:
        self._app_context = app_context
        self._access_service = access_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["app_context"] = self._app_context
        data["access_service"] = self._access_service

        from_user = None
        if isinstance(event, Message | CallbackQuery):
            from_user = event.from_user

        if from_user is not None:
            data["user_role"] = self._access_service.resolve_role(from_user.id)

        return await handler(event, data)
