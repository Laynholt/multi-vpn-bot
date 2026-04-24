"""Role resolution and access helpers."""

from __future__ import annotations

from enum import StrEnum

from app.core.config.models import TelegramConfig


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class AccessService:
    """Resolves user roles from the application config."""

    def __init__(self, telegram_config: TelegramConfig) -> None:
        self._admin_ids = frozenset(telegram_config.admin_ids)

    def resolve_role(self, telegram_user_id: int) -> UserRole:
        if telegram_user_id in self._admin_ids:
            return UserRole.ADMIN
        return UserRole.USER

    def is_admin(self, telegram_user_id: int) -> bool:
        return self.resolve_role(telegram_user_id) == UserRole.ADMIN
