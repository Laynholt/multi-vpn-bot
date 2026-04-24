"""Service layer for normalized VPN client inventory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.core.config.models import ProviderType
from app.domain.enums.common import ClientStatus

if TYPE_CHECKING:
    from app.infrastructure.db import DatabaseManager
    from app.infrastructure.db.models import VpnClientORM


@dataclass(frozen=True, slots=True)
class VpnClientSyncItem:
    """Provider client payload normalized before persistence."""

    provider_client_id: str
    display_name: str
    status: ClientStatus = ClientStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VpnClientSnapshot:
    """Read model for the unified VPN client inventory."""

    id: int
    provider_type: ProviderType
    server_key: str
    provider_client_id: str
    display_name: str
    status: ClientStatus
    metadata: dict[str, Any]
    telegram_user_ids: tuple[int, ...]
    created_at: datetime
    updated_at: datetime


class ClientInventoryService:
    """Coordinates provider client normalization and Telegram user links."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def sync_provider_clients(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
        clients: list[VpnClientSyncItem],
    ) -> list[VpnClientSnapshot]:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import VpnClientRepository

            repository = VpnClientRepository(session)
            snapshots: list[VpnClientSnapshot] = []
            for client in clients:
                orm_client = await repository.create_or_update(
                    server_key=server_key,
                    provider_type=provider_type.value,
                    provider_client_id=client.provider_client_id,
                    display_name=client.display_name,
                    status=client.status.value,
                    metadata=client.metadata,
                )
                telegram_user_ids = await repository.list_linked_user_ids(orm_client.id)
                snapshots.append(self._to_snapshot(orm_client, telegram_user_ids))
            return snapshots

    async def link_client_to_user(
        self,
        *,
        vpn_client_id: int,
        telegram_user_id: int,
    ) -> VpnClientSnapshot:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import VpnClientRepository

            repository = VpnClientRepository(session)
            client = await repository.get_by_id(vpn_client_id)
            if client is None:
                raise ValueError(f"VPN client {vpn_client_id} does not exist")
            await repository.link_to_telegram_user(
                vpn_client_id=vpn_client_id,
                telegram_user_id=telegram_user_id,
            )
            telegram_user_ids = await repository.list_linked_user_ids(vpn_client_id)
            return self._to_snapshot(client, telegram_user_ids)

    async def list_clients_for_user(
        self,
        *,
        telegram_user_id: int,
        include_deleted: bool = False,
    ) -> list[VpnClientSnapshot]:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import VpnClientRepository

            repository = VpnClientRepository(session)
            clients = await repository.list_by_telegram_user(
                telegram_user_id=telegram_user_id,
                include_deleted=include_deleted,
            )
            snapshots: list[VpnClientSnapshot] = []
            for client in clients:
                telegram_user_ids = await repository.list_linked_user_ids(client.id)
                snapshots.append(self._to_snapshot(client, telegram_user_ids))
            return snapshots

    def _to_snapshot(
        self,
        client: VpnClientORM,
        telegram_user_ids: tuple[int, ...],
    ) -> VpnClientSnapshot:
        return VpnClientSnapshot(
            id=client.id,
            provider_type=ProviderType(client.provider_type),
            server_key=client.server_key,
            provider_client_id=client.provider_client_id,
            display_name=client.display_name,
            status=ClientStatus(client.status),
            metadata=dict(client.metadata_json),
            telegram_user_ids=telegram_user_ids,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )
