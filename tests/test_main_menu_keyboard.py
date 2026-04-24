from __future__ import annotations

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.keyboards import build_main_menu_keyboard
from app.core.permissions import UserRole


def _button_payloads(markup) -> list[tuple[str, str]]:  # noqa: ANN001
    return [
        (button.text, button.callback_data or "")
        for row in markup.inline_keyboard
        for button in row
    ]


def test_main_menu_contains_config_request_button_for_users() -> None:
    markup = build_main_menu_keyboard(role=UserRole.USER, has_servers=True)

    payloads = _button_payloads(markup)

    assert (
        "Запросить конфиг",
        MenuActionCallback(section=MenuSection.REQUEST_CONFIG).pack(),
    ) in payloads
