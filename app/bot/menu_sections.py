"""Pure menu enums shared across Telegram-specific and generic code."""

from enum import StrEnum


class MenuSection(StrEnum):
    HOME = "home"
    SERVERS = "servers"
    PROFILE = "profile"
    TELEGRAM_ID = "telegram_id"
    ADMIN = "admin"
