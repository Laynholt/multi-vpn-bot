"""Pure menu enums shared across Telegram-specific and generic code."""

from enum import StrEnum


class MenuSection(StrEnum):
    HOME = "home"
    SERVERS = "servers"
    PROFILE = "profile"
    MY_CONFIGS = "my_configs"
    MY_STATS = "my_stats"
    REQUEST_CONFIG = "request_config"
    TELEGRAM_ID = "telegram_id"
    ADMIN = "admin"
