from __future__ import annotations

from datetime import datetime

from app.bot.formatters import (
    render_host_action_result,
    render_provider_client_delete_confirmation,
    render_provider_client_delete_result,
    render_provider_client_sync_result,
    render_provider_clients_list,
    render_server_card_text,
    render_server_list_text,
    render_server_providers_text,
    render_server_system_text,
)
from app.core.config.models import AppConfig, ProviderType
from app.core.executors import CommandResult
from app.core.registry import ServerRegistry
from app.domain.enums.common import ClientStatus
from app.providers import ProviderFactory, ProviderRegistry
from app.services.client_inventory import VpnClientSnapshot
from app.services.host_actions import HostActionExecution, HostActionRegistry
from app.services.provider_clients import ProviderClientDeleteResult, ProviderClientSyncResult


def _registry() -> ServerRegistry:
    config = AppConfig.model_validate(
        {
            "config_version": 1,
            "telegram": {"token": "dummy", "admin_ids": [1], "ui_mode": "inline"},
            "servers": [
                {
                    "key": "srv-html",
                    "title": "<Main & VPN>",
                    "enabled": True,
                    "connection": {"mode": "local"},
                    "host_actions": {"healthcheck": True, "speedtest": False},
                    "providers": [
                        {
                            "type": "wireguard",
                            "enabled": True,
                            "settings": {"wireguard_interface": "wg0"},
                        },
                        {
                            "type": "3xui",
                            "enabled": False,
                            "settings": {},
                        },
                    ],
                    "ui": {"icon": "WG", "sort_order": 1},
                    "tags": ["prod"],
                }
            ],
        }
    )
    return ServerRegistry.from_config(config)


def test_render_server_list_text_escapes_server_titles() -> None:
    text = render_server_list_text(_registry())

    assert "Серверы" in text
    assert "&lt;Main &amp; VPN&gt;" in text
    assert "<Main & VPN>" not in text
    assert "<code>srv-html</code>" in text


def test_render_server_card_text_contains_sections_summary() -> None:
    server = _registry().get("srv-html")

    text = render_server_card_text(server)

    assert "WG &lt;Main &amp; VPN&gt;" in text
    assert "Ключ: <code>srv-html</code>" in text
    assert "Транспорт: local" in text
    assert "Провайдеров: 1 active / 2 total" in text
    assert "Host actions: 1 enabled" in text


def test_render_server_system_text_lists_enabled_actions_only() -> None:
    server = _registry().get("srv-html")
    actions = HostActionRegistry()

    text = render_server_system_text(
        server=server,
        actions=(actions.get("healthcheck"),),
    )

    assert "Система" in text
    assert "Healthcheck" in text
    assert "Speedtest" not in text


def test_render_server_providers_text_lists_enabled_and_disabled_providers() -> None:
    server = _registry().get("srv-html")
    provider_factory = ProviderFactory(ProviderRegistry.with_builtin_providers())
    providers = tuple(
        provider_factory.create(provider_config)
        for provider_config in server.providers
        if provider_config.enabled
    )

    text = render_server_providers_text(server, providers=providers)

    assert "wireguard · enabled" in text
    assert "3xui · disabled" in text
    assert "wireguard_interface" in text
    assert "export_client_config" in text


def test_render_host_action_result_truncates_long_output() -> None:
    execution = HostActionExecution(
        server_key="srv-html",
        action_key="healthcheck",
        result=CommandResult(
            command=("hostname",),
            exit_code=0,
            stdout="x" * 200,
            stderr="",
            duration_ms=42,
        ),
    )

    text = render_host_action_result(execution, max_message_length=180)

    assert "healthcheck" in text
    assert "exit code: 0" in text
    assert "duration: 42 ms" in text
    assert "truncated" in text
    assert len(text) <= 180


def test_render_provider_client_sync_result_summarizes_clients() -> None:
    now = datetime(2026, 1, 1)
    result = ProviderClientSyncResult(
        server_key="srv-html",
        provider_type=ProviderType.WIREGUARD,
        clients=(
            VpnClientSnapshot(
                id=1,
                provider_type=ProviderType.WIREGUARD,
                server_key="srv-html",
                provider_client_id="peer-1",
                display_name="<Alice>",
                status=ClientStatus.ACTIVE,
                metadata={},
                telegram_user_ids=(),
                created_at=now,
                updated_at=now,
            ),
        ),
    )

    text = render_provider_client_sync_result(result)

    assert "Синхронизация клиентов" in text
    assert "<code>srv-html</code>" in text
    assert "wireguard" in text
    assert "1 clients" in text
    assert "&lt;Alice&gt;" in text


def test_render_provider_clients_list_escapes_and_summarizes_clients() -> None:
    now = datetime(2026, 1, 1)
    clients = (
        VpnClientSnapshot(
            id=1,
            provider_type=ProviderType.WIREGUARD,
            server_key="srv-html",
            provider_client_id="peer-1",
            display_name="<Alice>",
            status=ClientStatus.ACTIVE,
            metadata={},
            telegram_user_ids=(1001,),
            created_at=now,
            updated_at=now,
        ),
        VpnClientSnapshot(
            id=2,
            provider_type=ProviderType.WIREGUARD,
            server_key="srv-html",
            provider_client_id="peer-2",
            display_name="Bob",
            status=ClientStatus.DISABLED,
            metadata={},
            telegram_user_ids=(),
            created_at=now,
            updated_at=now,
        ),
    )

    text = render_provider_clients_list(
        server_key="srv-html",
        provider_type=ProviderType.WIREGUARD,
        clients=clients,
    )

    assert "Клиенты провайдера" in text
    assert "<code>srv-html</code>" in text
    assert "wireguard" in text
    assert "&lt;Alice&gt;" in text
    assert "users: 1001" in text
    assert "Bob" in text
    assert "disabled" in text


def test_render_provider_clients_list_handles_empty_clients() -> None:
    text = render_provider_clients_list(
        server_key="srv-html",
        provider_type=ProviderType.WIREGUARD,
        clients=(),
    )

    assert "Клиенты провайдера" in text
    assert "В inventory пока нет клиентов" in text


def test_render_provider_client_delete_confirmation_is_explicit() -> None:
    now = datetime(2026, 1, 1)
    client = VpnClientSnapshot(
        id=1,
        provider_type=ProviderType.WIREGUARD,
        server_key="srv-html",
        provider_client_id="peer-1",
        display_name="<Alice>",
        status=ClientStatus.ACTIVE,
        metadata={},
        telegram_user_ids=(1001,),
        created_at=now,
        updated_at=now,
    )

    text = render_provider_client_delete_confirmation(client)

    assert "Подтвердите удаление клиента" in text
    assert "&lt;Alice&gt;" in text
    assert "<code>peer-1</code>" in text
    assert "users: 1001" in text


def test_render_provider_client_delete_result_summarizes_action() -> None:
    result = ProviderClientDeleteResult(
        provider_client_id="peer-1",
        sync_result=ProviderClientSyncResult(
            server_key="srv-html",
            provider_type=ProviderType.WIREGUARD,
            clients=(),
        ),
    )

    text = render_provider_client_delete_result(result)

    assert "Клиент удалён" in text
    assert "<code>peer-1</code>" in text
    assert "remaining synced: 0" in text
