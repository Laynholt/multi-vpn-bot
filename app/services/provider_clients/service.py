"""Service layer for synchronizing provider clients into inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.domain.enums.common import ClientStatus
from app.services.client_inventory import VpnClientSnapshot, VpnClientSyncItem

if TYPE_CHECKING:
    from app.core.config.models import ProviderConfig, ProviderType
    from app.core.executors import BaseExecutor, ExecutorFactory
    from app.core.registry import RegisteredServer, ServerRegistry
    from app.providers import BaseProvider, ProviderFactory
    from app.services.client_inventory import ClientInventoryService


@dataclass(frozen=True, slots=True)
class ProviderClientSyncResult:
    server_key: str
    provider_type: ProviderType
    clients: tuple[VpnClientSnapshot, ...]


@dataclass(frozen=True, slots=True)
class ProviderClientActionResult:
    provider_client: dict[str, Any]
    sync_result: ProviderClientSyncResult


@dataclass(frozen=True, slots=True)
class ProviderClientDeleteResult:
    provider_client_id: str
    sync_result: ProviderClientSyncResult


class ProviderClientSyncService:
    """Coordinates provider reads and inventory writes."""

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

    async def sync_server_clients(self, server_key: str) -> tuple[ProviderClientSyncResult, ...]:
        server = self._server_registry.get(server_key)
        executor = self._executor_factory.for_server(server)
        results: list[ProviderClientSyncResult] = []

        for provider_config in server.providers:
            if not provider_config.enabled:
                continue
            results.append(
                await self._sync_provider_clients(
                    server=server,
                    provider_config=provider_config,
                    executor=executor,
                )
            )

        return tuple(results)

    async def sync_provider_clients(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
    ) -> ProviderClientSyncResult:
        server = self._server_registry.get(server_key)
        provider_config = self._get_enabled_provider_config(server, provider_type)
        executor = self._executor_factory.for_server(server)
        return await self._sync_provider_clients(
            server=server,
            provider_config=provider_config,
            executor=executor,
        )

    async def list_provider_clients(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
    ) -> tuple[VpnClientSnapshot, ...]:
        server = self._server_registry.get(server_key)
        self._get_enabled_provider_config(server, provider_type)
        clients = await self._client_inventory_service.list_clients_for_provider(
            server_key=server.key,
            provider_type=provider_type,
        )
        return tuple(clients)

    async def create_client(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
        payload: dict[str, Any],
    ) -> ProviderClientActionResult:
        server = self._server_registry.get(server_key)
        provider_config = self._get_enabled_provider_config(server, provider_type)
        executor = self._executor_factory.for_server(server)
        provider = self._provider_factory.create(provider_config, executor=executor)

        provider_client = await provider.create_client(payload)
        sync_result = await self._sync_provider_clients(
            server=server,
            provider_config=provider_config,
            executor=executor,
            provider=provider,
        )
        return ProviderClientActionResult(
            provider_client=provider_client,
            sync_result=sync_result,
        )

    async def delete_client(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
        provider_client_id: str,
    ) -> ProviderClientDeleteResult:
        server = self._server_registry.get(server_key)
        provider_config = self._get_enabled_provider_config(server, provider_type)
        executor = self._executor_factory.for_server(server)
        provider = self._provider_factory.create(provider_config, executor=executor)

        await provider.delete_client(provider_client_id)
        sync_result = await self._sync_provider_clients(
            server=server,
            provider_config=provider_config,
            executor=executor,
            provider=provider,
        )
        return ProviderClientDeleteResult(
            provider_client_id=provider_client_id,
            sync_result=sync_result,
        )

    async def _sync_provider_clients(
        self,
        *,
        server: RegisteredServer,
        provider_config: ProviderConfig,
        executor: BaseExecutor,
        provider: BaseProvider | None = None,
    ) -> ProviderClientSyncResult:
        if provider is None:
            provider = self._provider_factory.create(provider_config, executor=executor)

        provider_clients = await provider.list_clients()
        synced_clients = await self._client_inventory_service.sync_provider_clients(
            server_key=server.key,
            provider_type=provider_config.type,
            clients=[
                self._to_sync_item(provider_config.type, client)
                for client in provider_clients
            ],
        )
        return ProviderClientSyncResult(
            server_key=server.key,
            provider_type=provider_config.type,
            clients=tuple(synced_clients),
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

    def _to_sync_item(
        self,
        provider_type: ProviderType,
        payload: dict[str, Any],
    ) -> VpnClientSyncItem:
        provider_client_id = str(payload["provider_client_id"])
        display_name = str(payload.get("display_name") or provider_client_id)
        status = self._parse_status(provider_type, payload.get("status"))
        metadata = payload.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError(
                f"Provider {provider_type.value!r} returned non-object client metadata"
            )
        return VpnClientSyncItem(
            provider_client_id=provider_client_id,
            display_name=display_name,
            status=status,
            metadata=dict(metadata),
        )

    def _parse_status(self, provider_type: ProviderType, value: object) -> ClientStatus:
        if value is None:
            return ClientStatus.ACTIVE
        try:
            return ClientStatus(str(value))
        except ValueError as exc:
            raise ValueError(
                f"Unsupported provider client status {value!r} from {provider_type.value!r}"
            ) from exc
