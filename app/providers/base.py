"""Base provider contract."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from app.core.config.models import ProviderConfig, ProviderType
from app.providers.capabilities import ProviderCapabilities

if TYPE_CHECKING:
    from app.core.executors.base import BaseExecutor


class BaseProvider(ABC):
    """Unified contract implemented by provider modules."""

    provider_type: ProviderType
    capabilities: ProviderCapabilities = ProviderCapabilities()

    def __init__(self, config: ProviderConfig, executor: BaseExecutor | None = None) -> None:
        self.config = config
        self.executor = executor

    async def healthcheck(self) -> bool:
        raise NotImplementedError

    async def list_clients(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def get_client(self, client_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def create_client(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def enable_client(self, client_id: str) -> None:
        raise NotImplementedError

    async def disable_client(self, client_id: str) -> None:
        raise NotImplementedError

    async def delete_client(self, client_id: str) -> None:
        raise NotImplementedError

    async def export_client_config(self, client_id: str) -> bytes:
        raise NotImplementedError

    async def collect_client_stats(self) -> list[dict[str, Any]]:
        raise NotImplementedError
