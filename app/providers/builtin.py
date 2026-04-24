"""Built-in provider stubs."""

from __future__ import annotations

from app.core.config.models import ProviderType
from app.providers.base import BaseProvider
from app.providers.capabilities import ProviderCapabilities


class WireGuardProvider(BaseProvider):
    """WireGuard provider placeholder with declared target capabilities."""

    provider_type = ProviderType.WIREGUARD
    capabilities = ProviderCapabilities(
        list_clients=True,
        create_client=True,
        enable_client=False,
        disable_client=False,
        delete_client=True,
        export_client_config=True,
        collect_client_stats=True,
    )


class X3UIProvider(BaseProvider):
    """3xUI provider placeholder with declared target capabilities."""

    provider_type = ProviderType.X3UI
    capabilities = ProviderCapabilities(
        list_clients=True,
        create_client=True,
        enable_client=True,
        disable_client=True,
        delete_client=True,
        export_client_config=False,
        collect_client_stats=True,
    )
