from __future__ import annotations

from app.bot.callbacks import (
    HostActionCallback,
    ProviderClientAction,
    ProviderClientActionCallback,
    ServerSection,
    ServerSectionCallback,
)
from app.bot.keyboards import (
    build_server_card_keyboard,
    build_server_list_keyboard,
    build_server_providers_keyboard,
    build_server_system_keyboard,
)
from app.core.config import load_config
from app.core.config.models import ProviderConfig, ProviderType
from app.core.registry import ServerRegistry
from app.services.host_actions import HostActionRegistry


def _button_payloads(markup) -> list[tuple[str, str]]:  # noqa: ANN001
    return [
        (button.text, button.callback_data or "")
        for row in markup.inline_keyboard
        for button in row
    ]


def test_build_server_list_keyboard_contains_server_callbacks() -> None:
    registry = ServerRegistry.from_config(load_config("configs/config.example.json"))

    markup = build_server_list_keyboard(registry)

    payloads = _button_payloads(markup)
    assert any(text == "🛡 Нидерланды" for text, _callback in payloads)
    assert any(callback == "srv:vps-nl" for _text, callback in payloads)


def test_build_server_card_keyboard_contains_expected_sections() -> None:
    markup = build_server_card_keyboard(server_key="vps-nl")

    callbacks = {callback for _text, callback in _button_payloads(markup)}

    assert (
        ServerSectionCallback(
            key="vps-nl",
            section=ServerSection.SYSTEM,
        ).pack()
        in callbacks
    )
    assert (
        ServerSectionCallback(
            key="vps-nl",
            section=ServerSection.PROVIDERS,
        ).pack()
        in callbacks
    )
    assert (
        ServerSectionCallback(
            key="vps-nl",
            section=ServerSection.INFO,
        ).pack()
        in callbacks
    )


def test_build_server_system_keyboard_contains_host_action_callbacks() -> None:
    actions = (HostActionRegistry().get("healthcheck"),)

    markup = build_server_system_keyboard(server_key="vps-nl", actions=actions)

    callbacks = {callback for _text, callback in _button_payloads(markup)}
    assert HostActionCallback(key="vps-nl", action="healthcheck").pack() in callbacks


def test_build_server_providers_keyboard_contains_provider_sync_callbacks() -> None:
    markup = build_server_providers_keyboard(
        server_key="vps-nl",
        providers=(
            ProviderConfig(type=ProviderType.WIREGUARD),
            ProviderConfig(type=ProviderType.X3UI, enabled=False),
        ),
    )

    payloads = _button_payloads(markup)
    callbacks = {callback for _text, callback in payloads}
    assert (
        ProviderClientActionCallback(
            key="vps-nl",
            provider=ProviderType.WIREGUARD,
            action=ProviderClientAction.SYNC,
        ).pack()
        in callbacks
    )
    assert all("3xui" not in callback for _text, callback in payloads)
