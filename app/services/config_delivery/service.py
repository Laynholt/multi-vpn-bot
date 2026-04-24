"""Unified service for exporting user VPN configs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config.models import ProviderType

if TYPE_CHECKING:
    from app.core.config.models import ProviderConfig
    from app.core.executors import ExecutorFactory
    from app.core.registry import RegisteredServer, ServerRegistry
    from app.providers import ProviderFactory
    from app.services.client_inventory import ClientInventoryService, VpnClientSnapshot


@dataclass(frozen=True, slots=True)
class ConfigDeliveryFile:
    filename: str
    content: bytes
    server_key: str
    provider_type: ProviderType
    provider_client_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ConfigDeliveryError:
    server_key: str
    provider_type: ProviderType
    provider_client_id: str
    display_name: str
    message: str


@dataclass(frozen=True, slots=True)
class ConfigDeliveryResult:
    files: tuple[ConfigDeliveryFile, ...]
    errors: tuple[ConfigDeliveryError, ...]


class ConfigDeliveryService:
    """Exports provider configs for clients linked to a Telegram user."""

    def __init__(
        self,
        *,
        server_registry: ServerRegistry,
        executor_factory: ExecutorFactory,
        provider_factory: ProviderFactory,
        client_inventory_service: ClientInventoryService,
    ) -> None:
        self._server_registry = server_registry
        self._executor_factory = executor_factory
        self._provider_factory = provider_factory
        self._client_inventory_service = client_inventory_service

    async def list_user_config_files(self, *, telegram_user_id: int) -> ConfigDeliveryResult:
        clients = await self._client_inventory_service.list_clients_for_user(
            telegram_user_id=telegram_user_id,
        )
        files: list[ConfigDeliveryFile] = []
        errors: list[ConfigDeliveryError] = []

        for client in clients:
            try:
                files.append(await self._export_client_config(client))
            except Exception as exc:
                errors.append(
                    ConfigDeliveryError(
                        server_key=client.server_key,
                        provider_type=client.provider_type,
                        provider_client_id=client.provider_client_id,
                        display_name=client.display_name,
                        message=str(exc),
                    )
                )

        return ConfigDeliveryResult(files=tuple(files), errors=tuple(errors))

    async def _export_client_config(
        self,
        client: VpnClientSnapshot,
    ) -> ConfigDeliveryFile:
        server = self._server_registry.get(client.server_key)
        provider_config = self._get_enabled_provider_config(server, client.provider_type)
        executor = self._executor_factory.for_server(server)
        provider = self._provider_factory.create(provider_config, executor=executor)
        content = await provider.export_client_config(client.provider_client_id)
        return ConfigDeliveryFile(
            filename=self._build_filename(client),
            content=content,
            server_key=client.server_key,
            provider_type=client.provider_type,
            provider_client_id=client.provider_client_id,
            display_name=client.display_name,
        )

    def _get_enabled_provider_config(
        self,
        server: RegisteredServer,
        provider_type: ProviderType,
    ) -> ProviderConfig:
        for provider_config in server.providers:
            if provider_config.enabled and provider_config.type == provider_type:
                return provider_config
        raise ValueError(
            f"Enabled provider {provider_type.value!r} is not configured "
            f"for server {server.key!r}"
        )

    def _build_filename(self, client: VpnClientSnapshot) -> str:
        raw_name = "_".join(
            (
                client.server_key,
                client.provider_type.value,
                client.display_name or client.provider_client_id,
            )
        )
        safe_name = re.sub(r"[^A-Za-z0-9_.@-]+", "_", raw_name).strip("._")
        return f"{safe_name or 'vpn_config'}.conf"
