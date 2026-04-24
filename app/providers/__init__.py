"""Provider base layer and built-in provider registry."""

from app.providers.base import BaseProvider
from app.providers.builtin import WireGuardProvider, X3UIProvider
from app.providers.capabilities import ProviderCapabilities
from app.providers.factory import ProviderFactory
from app.providers.registry import ProviderDefinition, ProviderRegistry, UnsupportedProviderError

__all__ = [
    "BaseProvider",
    "ProviderCapabilities",
    "ProviderDefinition",
    "ProviderFactory",
    "ProviderRegistry",
    "UnsupportedProviderError",
    "WireGuardProvider",
    "X3UIProvider",
]
