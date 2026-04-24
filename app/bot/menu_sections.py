"""Pure menu enums shared across Telegram-specific and generic code."""

from enum import StrEnum


class MenuSection(StrEnum):
    HOME = "home"
    SERVERS = "servers"
    PROFILE = "profile"
    MY_CONFIGS = "my_configs"
    TELEGRAM_ID = "telegram_id"
    ADMIN = "admin"
