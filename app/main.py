"""Bootstrap entrypoint for the application."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.core.config import load_config
from app.core.exceptions import ConfigurationError
from app.core.executors import ExecutorFactory
from app.core.registry import ServerRegistry
from app.infrastructure.logging import configure_logging, get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the multi VPN bot")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/config.json"),
        help="Path to the application config file",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Only validate the config and exit",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Initialize config, registry and database, then exit without Telegram polling",
    )
    return parser


async def bootstrap(
    config_path: Path,
    *,
    validate_only: bool,
    bootstrap_only: bool,
) -> int:
    config = load_config(config_path)
    configure_logging(config.logging)

    logger = get_logger(__name__)
    logger.info("Configuration loaded from %s", config_path)

    registry = ServerRegistry.from_config(config)
    logger.info("Enabled servers in registry: %s", len(registry))

    executor_factory = ExecutorFactory(config.transports)
    logger.info("ExecutorFactory initialized")

    if validate_only:
        logger.info("Configuration validation completed successfully")
        return 0

    from app.infrastructure.db import DatabaseManager

    database = DatabaseManager(config.database)
    await database.initialize()
    logger.info("Database initialized at %s", config.database.sqlite_path)

    if bootstrap_only:
        logger.info("Bootstrap-only mode completed successfully")
        await database.dispose()
        return 0

    try:
        from app.bot import run_bot
        from app.context import ApplicationContext
        from app.core.permissions import AccessService
        from app.providers import ProviderFactory, ProviderRegistry
        from app.services.admin_audit import AdminAuditService
        from app.services.client_inventory import ClientInventoryService
        from app.services.config_delivery import ConfigDeliveryService
        from app.services.host_actions import HostActionRegistry, HostActionsService
        from app.services.messages import MessageBridgeService
        from app.services.provider_clients import ProviderClientSyncService
        from app.services.traffic_stats import TrafficStatsService
        from app.services.users import TelegramUserService

        access_service = AccessService(config.telegram)
        admin_audit_service = AdminAuditService(database)
        provider_factory = ProviderFactory(ProviderRegistry.with_builtin_providers())
        host_action_registry = HostActionRegistry()
        host_actions_service = HostActionsService(
            server_registry=registry,
            executor_factory=executor_factory,
            host_action_registry=host_action_registry,
            speedtest_timeout_seconds=config.defaults.speedtest_timeout_seconds,
        )
        client_inventory_service = ClientInventoryService(database)
        provider_client_sync_service = ProviderClientSyncService(
            server_registry=registry,
            executor_factory=executor_factory,
            provider_factory=provider_factory,
            client_inventory_service=client_inventory_service,
        )
        config_delivery_service = ConfigDeliveryService(
            server_registry=registry,
            executor_factory=executor_factory,
            provider_factory=provider_factory,
            client_inventory_service=client_inventory_service,
        )
        traffic_stats_service = TrafficStatsService.from_config(
            database,
            config.statistics,
        )
        telegram_user_service = TelegramUserService(database)
        message_bridge_service = MessageBridgeService(
            database=database,
            telegram_config=config.telegram,
            access_service=access_service,
        )
        app_context = ApplicationContext(
            config=config,
            database=database,
            server_registry=registry,
            executor_factory=executor_factory,
            provider_factory=provider_factory,
            admin_audit_service=admin_audit_service,
            host_actions_service=host_actions_service,
            provider_client_sync_service=provider_client_sync_service,
            config_delivery_service=config_delivery_service,
            traffic_stats_service=traffic_stats_service,
            access_service=access_service,
            telegram_user_service=telegram_user_service,
            message_bridge_service=message_bridge_service,
        )
        await run_bot(app_context)
    finally:
        await database.dispose()

    return 0


def main() -> int:
    args = build_parser().parse_args()
    try:
        return asyncio.run(
            bootstrap(
                args.config,
                validate_only=args.validate_config,
                bootstrap_only=args.bootstrap_only,
            )
        )
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependency. Install project dependencies from pyproject.toml "
            f"before starting the application: {exc}"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
