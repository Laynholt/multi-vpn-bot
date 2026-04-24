"""Provider factory."""

from __future__ import annotations

from app.core.config.models import ProviderConfig
from app.core.executors.base import BaseExecutor
from app.providers.base import BaseProvider
from app.providers.registry import ProviderRegistry


class ProviderFactory:
    """Creates provider modules from provider config entries."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def create(
        self,
        config: ProviderConfig,
        *,
        executor: BaseExecutor | None = None,
    ) -> BaseProvider:
        definition = self._registry.get(config.type)
        return definition.provider_class(config, executor=executor)
