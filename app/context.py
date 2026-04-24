"""Shared application context passed into the Telegram layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config.models import AppConfig
from app.core.executors import ExecutorFactory
from app.core.permissions import AccessService
from app.core.registry import ServerRegistry
from app.providers import ProviderFactory

if TYPE_CHECKING:
    from app.infrastructure.db import DatabaseManager
    from app.services.config_delivery import ConfigDeliveryService
    from app.services.host_actions import HostActionsService
    from app.services.messages import MessageBridgeService
    from app.services.provider_clients import ProviderClientSyncService
    from app.services.traffic_stats import TrafficStatsService
    from app.services.users import TelegramUserService


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    """Runtime dependencies shared across handlers and services."""

    config: AppConfig
    database: DatabaseManager
    server_registry: ServerRegistry
    executor_factory: ExecutorFactory
    provider_factory: ProviderFactory
    host_actions_service: HostActionsService
    provider_client_sync_service: ProviderClientSyncService
    config_delivery_service: ConfigDeliveryService
    traffic_stats_service: TrafficStatsService
    access_service: AccessService
    telegram_user_service: TelegramUserService
    message_bridge_service: MessageBridgeService
