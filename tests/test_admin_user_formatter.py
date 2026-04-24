from __future__ import annotations

from datetime import UTC, datetime

from app.bot.formatters import render_admin_user_card, render_admin_users_page
from app.domain.enums.common import UserStatus
from app.services.users import TelegramUserPage, TelegramUserSnapshot


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


def test_render_admin_users_page_contains_users() -> None:
    page = TelegramUserPage(
        items=[
            _make_user(100, status=UserStatus.ACTIVE),
            _make_user(200, status=UserStatus.BANNED),
        ],
        total=2,
        page=0,
        page_size=8,
    )

    text = render_admin_users_page(page)

    assert "Всего пользователей: 2" in text
    assert "Test User" in text
    assert "banned" in text


def test_render_admin_user_card_contains_status_and_id() -> None:
    user = _make_user(777, status=UserStatus.DELETED)

    text = render_admin_user_card(user)

    assert "Telegram ID: <code>777</code>" in text
    assert "Статус: deleted" in text
