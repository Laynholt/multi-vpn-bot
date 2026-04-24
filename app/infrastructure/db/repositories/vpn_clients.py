"""Repository for normalized VPN clients."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.common import ClientStatus
from app.infrastructure.db.models import VpnClientORM


class VpnClientRepository:
    """CRUD helpers for unified VPN clients."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
