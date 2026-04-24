"""Provider class registry."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config.models import ProviderType
from app.providers.base import BaseProvider
from app.providers.builtin import WireGuardProvider, X3UIProvider


class UnsupportedProviderError(ValueError):
    """Raised when a provider type is not registered."""


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    provider_type: ProviderType
    provider_class: type[BaseProvider]
    title: str


class ProviderRegistry:
    """Read-only registry of provider modules available at runtime."""

    def __init__(
        self,
        definitions: tuple[ProviderDefinition, ...] = (),
    ) -> None:
        self._definitions = {definition.provider_type: definition for definition in definitions}

    @classmethod
    def with_builtin_providers(cls) -> ProviderRegistry:
        return cls(
            (
                ProviderDefinition(
                    provider_type=ProviderType.WIREGUARD,
                    provider_class=WireGuardProvider,
                    title="WireGuard",
                ),
                ProviderDefinition(
                    provider_type=ProviderType.X3UI,
                    provider_class=X3UIProvider,
                    title="3xUI",
                ),
            )
        )

    def has(self, provider_type: ProviderType) -> bool:
        return provider_type in self._definitions

    def get(self, provider_type: ProviderType) -> ProviderDefinition:
        try:
            return self._definitions[provider_type]
        except KeyError as exc:
            raise UnsupportedProviderError(
                f"Unsupported provider type: {provider_type.value}"
            ) from exc

    def list_definitions(self) -> tuple[ProviderDefinition, ...]:
        return tuple(self._definitions.values())
