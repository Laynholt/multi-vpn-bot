from __future__ import annotations

from app.bot.callbacks import AdminTrafficStatsAction, AdminTrafficStatsCallback
from app.bot.keyboards import build_admin_traffic_keyboard
from app.core.config import load_config
from app.core.registry import ServerRegistry


def _button_payloads(markup) -> list[tuple[str, str]]:  # noqa: ANN001
    return [
        (button.text, button.callback_data or "")
        for row in markup.inline_keyboard
        for button in row
    ]


def test_admin_traffic_keyboard_contains_csv_and_server_filters() -> None:
    registry = ServerRegistry.from_config(load_config("configs/config.example.json"))

    markup = build_admin_traffic_keyboard(registry=registry, server_key=None)

    payloads = _button_payloads(markup)
    callbacks = {callback for _text, callback in payloads}

    assert (
        AdminTrafficStatsCallback(
            action=AdminTrafficStatsAction.CSV,
            server="all",
        ).pack()
        in callbacks
    )
    assert (
        AdminTrafficStatsCallback(
            action=AdminTrafficStatsAction.REPORT,
            server="vps-nl",
        ).pack()
        in callbacks
    )
