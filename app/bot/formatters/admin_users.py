"""Formatting helpers for admin user management."""

from __future__ import annotations

from datetime import datetime
from html import escape

from app.services.users import TelegramUserPage, TelegramUserSnapshot


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "never"
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _render_display_name(user: TelegramUserSnapshot) -> str:
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
    return escape(full_name or user.username or str(user.telegram_user_id))


def render_admin_users_page(page_data: TelegramUserPage) -> str:
    lines = [
        "Админка · Пользователи",
        "",
        f"Всего пользователей: {page_data.total}",
        f"Страница: {page_data.page + 1}",
        "",
    ]
    if not page_data.items:
        lines.append("Пользователи ещё не зарегистрированы.")
        return "\n".join(lines)

    for user in page_data.items:
        display_name = _render_display_name(user)
        lines.append(f"{display_name} · id={user.telegram_user_id} · status={user.status.value}")
    return "\n".join(lines)


def render_admin_user_card(user: TelegramUserSnapshot) -> str:
    username_line = f"@{escape(user.username)}" if user.username else "not set"
    return "\n".join(
        [
            "Админка · Карточка пользователя",
            "",
            f"Telegram ID: <code>{user.telegram_user_id}</code>",
            f"Username: {username_line}",
            f"Имя: {_render_display_name(user)}",
            f"Статус: {user.status.value}",
            f"Админ: {'yes' if user.is_admin else 'no'}",
            f"Premium: {'yes' if user.is_premium else 'no'}",
            f"Язык: {escape(user.language_code) if user.language_code else 'unknown'}",
            f"Создан: {_format_dt(user.created_at)}",
            f"Обновлён: {_format_dt(user.updated_at)}",
            f"Последняя активность: {_format_dt(user.last_seen_at)}",
        ]
    )
