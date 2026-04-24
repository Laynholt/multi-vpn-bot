"""Formatting helpers for admin user management."""

from __future__ import annotations

from datetime import datetime
from html import escape

from app.services.traffic_stats import TrafficAdminDailySummary
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


def _format_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def render_admin_traffic_summary(summary: TrafficAdminDailySummary) -> str:
    scope = summary.server_key or "all servers"
    period = "all time"
    if summary.date_from is not None or summary.date_to is not None:
        period = f"{summary.date_from or '...'} - {summary.date_to or '...'}"

    lines = [
        "Админская статистика",
        "",
        f"Scope: {escape(scope)}",
        f"Period: {period}",
        f"Traffic total: {_format_bytes(summary.total_bytes)}",
        f"RX: {_format_bytes(summary.rx_bytes)}",
        f"TX: {_format_bytes(summary.tx_bytes)}",
    ]
    if not summary.clients:
        lines.extend(["", "Данных по трафику пока нет."])
        return "\n".join(lines)

    lines.extend(["", "Клиенты:"])
    for client in summary.clients:
        user = client.telegram_user_id if client.telegram_user_id is not None else "none"
        lines.append(
            f"- {escape(client.display_name)} "
            f"(<code>{escape(client.server_key)}</code>, "
            f"<code>{escape(client.provider_type.value)}</code>, "
            f"user: {user}): {_format_bytes(client.total_bytes)}"
        )
    return "\n".join(lines)
