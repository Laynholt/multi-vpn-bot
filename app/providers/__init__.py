"""Provider base layer and built-in provider registry."""

from app.providers.base import BaseProvider
from app.providers.builtin import X3UIProvider
from app.providers.capabilities import ProviderCapabilities
from app.providers.factory import ProviderFactory
from app.providers.registry import ProviderDefinition, ProviderRegistry, UnsupportedProviderError
from app.providers.wireguard import WireGuardProvider, WireGuardProviderSettings

__all__ = [
    "BaseProvider",
    "ProviderCapabilities",
    "ProviderDefinition",
    "ProviderFactory",
    "ProviderRegistry",
    "UnsupportedProviderError",
    "WireGuardProvider",
    "WireGuardProviderSettings",
    "X3UIProvider",
]
