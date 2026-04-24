from __future__ import annotations

import pytest

from app.core.config.models import ProviderConfig, ProviderType
from app.providers import (
    BaseProvider,
    ProviderCapabilities,
    ProviderFactory,
    ProviderRegistry,
    UnsupportedProviderError,
)


def test_provider_registry_contains_builtin_provider_types() -> None:
    registry = ProviderRegistry.with_builtin_providers()

    assert registry.has(ProviderType.WIREGUARD) is True
    assert registry.has(ProviderType.X3UI) is True
    assert tuple(definition.provider_type for definition in registry.list_definitions()) == (
        ProviderType.WIREGUARD,
        ProviderType.X3UI,
    )


def test_provider_factory_creates_provider_by_config_type() -> None:
    registry = ProviderRegistry.with_builtin_providers()
    factory = ProviderFactory(registry)
    provider_config = ProviderConfig(
        type=ProviderType.WIREGUARD,
        enabled=True,
        settings={"wireguard_interface": "wg0"},
    )

    provider = factory.create(provider_config)

    assert isinstance(provider, BaseProvider)
    assert provider.provider_type == ProviderType.WIREGUARD
    assert provider.config is provider_config
    assert provider.capabilities.export_client_config is True


def test_provider_factory_rejects_unknown_registered_type() -> None:
    registry = ProviderRegistry()
    factory = ProviderFactory(registry)

    with pytest.raises(UnsupportedProviderError):
        factory.create(ProviderConfig(type=ProviderType.WIREGUARD))


@pytest.mark.asyncio
async def test_base_provider_contract_methods_are_explicitly_unimplemented() -> None:
    provider = ProviderFactory(ProviderRegistry.with_builtin_providers()).create(
        ProviderConfig(type=ProviderType.X3UI)
    )

    with pytest.raises(NotImplementedError):
        await provider.list_clients()
    with pytest.raises(NotImplementedError):
        await provider.create_client({"name": "client"})
    with pytest.raises(NotImplementedError):
        await provider.collect_client_stats()


def test_provider_capabilities_can_be_rendered_as_enabled_names() -> None:
    capabilities = ProviderCapabilities(
        list_clients=True,
        create_client=True,
        enable_client=False,
        disable_client=False,
        delete_client=True,
        export_client_config=True,
        collect_client_stats=False,
    )

    assert capabilities.enabled_names() == (
        "list_clients",
        "create_client",
        "delete_client",
        "export_client_config",
    )
