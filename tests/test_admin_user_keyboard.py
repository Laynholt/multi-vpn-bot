from __future__ import annotations

from datetime import UTC, datetime

from app.bot.callbacks import AdminUserManageCallback
from app.bot.keyboards import build_admin_user_card_keyboard
from app.bot.user_admin_actions import AdminUserAction
from app.domain.enums.common import UserStatus
from app.services.users import TelegramUserSnapshot


def _button_payloads(markup) -> list[tuple[str, str]]:  # noqa: ANN001
    return [
        (button.text, button.callback_data or "")
        for row in markup.inline_keyboard
        for button in row
    ]


def _make_user(telegram_user_id: int, *, status: UserStatus) -> TelegramUserSnapshot:
    now = datetime.now(UTC)
    return TelegramUserSnapshot(
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        first_name="Test",
        last_name="User",
        language_code="ru",
        is_bot=False,
        is_premium=False,
        is_admin=False,
        status=status,
        created_at=now,
        updated_at=now,
        last_seen_at=now,
    )


def test_admin_user_card_keyboard_contains_config_delivery_action() -> None:
    user = _make_user(telegram_user_id=1001, status=UserStatus.ACTIVE)

    markup = build_admin_user_card_keyboard(user=user, page=3)

    payloads = _button_payloads(markup)
    callbacks = {callback for _text, callback in payloads}

    assert ("Выдать конфиги", AdminUserManageCallback(
        action=AdminUserAction.SEND_CONFIGS,
        user_id=1001,
        page=3,
    ).pack()) in payloads
    assert (
        AdminUserManageCallback(
            action=AdminUserAction.SEND_CONFIGS,
            user_id=1001,
            page=3,
        ).pack()
        in callbacks
    )
