"""Role-based filters for handlers."""

from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from app.core.permissions import AccessService


class AdminFilter(Filter):
    """Allows access only to admins from the configured admin id list."""

    async def __call__(
        self,
        event: Message | CallbackQuery,
        access_service: AccessService,
    ) -> bool:
        from_user = event.from_user
        if from_user is None:
            return False
        return access_service.is_admin(from_user.id)
