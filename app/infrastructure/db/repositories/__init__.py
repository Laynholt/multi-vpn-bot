"""Repository layer for initial entities."""

from app.infrastructure.db.repositories.message_links import MessageLinkRepository
from app.infrastructure.db.repositories.telegram_users import TelegramUserRepository
from app.infrastructure.db.repositories.traffic_stats import (
    TrafficStatDailyRepository,
    TrafficStatSampleRepository,
)
from app.infrastructure.db.repositories.vpn_clients import VpnClientRepository

__all__ = [
    "MessageLinkRepository",
    "TelegramUserRepository",
    "TrafficStatDailyRepository",
    "TrafficStatSampleRepository",
    "VpnClientRepository",
]
