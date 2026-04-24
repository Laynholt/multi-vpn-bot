"""Repository for normalized VPN clients."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.common import ClientStatus
from app.infrastructure.db.models import VpnClientORM, VpnClientUserLinkORM


class VpnClientRepository:
    """CRUD helpers for unified VPN clients."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, vpn_client_id: int) -> VpnClientORM | None:
        return await self._session.get(VpnClientORM, vpn_client_id)

    async def get_by_identity(
        self,
        *,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
    ) -> VpnClientORM | None:
        query = select(VpnClientORM).where(
            VpnClientORM.server_key == server_key,
            VpnClientORM.provider_type == provider_type,
            VpnClientORM.provider_client_id == provider_client_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        *,
        server_key: str,
        provider_type: str,
        provider_client_id: str,
        display_name: str,
        status: str = ClientStatus.ACTIVE.value,
        metadata: dict[str, Any] | None = None,
    ) -> VpnClientORM:
        client = await self.get_by_identity(
            server_key=server_key,
            provider_type=provider_type,
            provider_client_id=provider_client_id,
        )

        if client is None:
            client = VpnClientORM(
                server_key=server_key,
                provider_type=provider_type,
                provider_client_id=provider_client_id,
                display_name=display_name,
                status=status,
                metadata_json=metadata or {},
            )
            self._session.add(client)
            await self._session.flush()
            return client

        client.display_name = display_name
        client.status = status
        client.metadata_json = metadata or {}
        await self._session.flush()
        return client

    async def link_to_telegram_user(
        self,
        *,
        vpn_client_id: int,
        telegram_user_id: int,
    ) -> VpnClientUserLinkORM:
        query = select(VpnClientUserLinkORM).where(
            VpnClientUserLinkORM.vpn_client_id == vpn_client_id,
            VpnClientUserLinkORM.telegram_user_id == telegram_user_id,
        )
        result = await self._session.execute(query)
        link = result.scalar_one_or_none()
        if link is not None:
            return link

        link = VpnClientUserLinkORM(
            vpn_client_id=vpn_client_id,
            telegram_user_id=telegram_user_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def list_linked_user_ids(self, vpn_client_id: int) -> tuple[int, ...]:
        query = (
            select(VpnClientUserLinkORM.telegram_user_id)
            .where(VpnClientUserLinkORM.vpn_client_id == vpn_client_id)
            .order_by(VpnClientUserLinkORM.telegram_user_id)
        )
        result = await self._session.execute(query)
        return tuple(result.scalars().all())

    async def list_by_telegram_user(
        self,
        *,
        telegram_user_id: int,
        include_deleted: bool = False,
    ) -> list[VpnClientORM]:
        query = (
            select(VpnClientORM)
            .join(
                VpnClientUserLinkORM,
                VpnClientUserLinkORM.vpn_client_id == VpnClientORM.id,
            )
            .where(VpnClientUserLinkORM.telegram_user_id == telegram_user_id)
            .order_by(VpnClientORM.server_key, VpnClientORM.display_name)
        )
        if not include_deleted:
            query = query.where(VpnClientORM.status != ClientStatus.DELETED.value)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_by_provider(
        self,
        *,
        server_key: str,
        provider_type: str,
        include_deleted: bool = False,
    ) -> list[VpnClientORM]:
        query = (
            select(VpnClientORM)
            .where(
                VpnClientORM.server_key == server_key,
                VpnClientORM.provider_type == provider_type,
            )
            .order_by(VpnClientORM.display_name, VpnClientORM.provider_client_id)
        )
        if not include_deleted:
            query = query.where(VpnClientORM.status != ClientStatus.DELETED.value)

        result = await self._session.execute(query)
        return list(result.scalars().all())
