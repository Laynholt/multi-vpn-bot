"""Formatting helpers for the Telegram inline menu."""

from __future__ import annotations

from html import escape

from app.bot.menu_sections import MenuSection
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry


def render_home_text(*, role: UserRole, registry: ServerRegistry) -> str:
    lines = [
        "Multi VPN Bot",
        "",
        f"Роль: {role.value}",
        f"Доступных серверов: {len(registry)}",
    ]
    if len(registry) == 0:
        lines.extend(
            [
                "",
                "Серверы пока не подключены. Бот остаётся работоспособным и без provider-модулей.",
            ]
        )
    else:
        titles = ", ".join(server.title for server in registry.list_servers())
        lines.extend(["", f"Серверы: {titles}"])

    if role == UserRole.ADMIN:
        lines.extend(["", "Админский раздел уже доступен в базовом виде."])

    return "\n".join(lines)


def render_section_text(
    *,
    section: MenuSection,
    role: UserRole,
    registry: ServerRegistry,
    telegram_user_id: int | None = None,
) -> str:
    if section == MenuSection.SERVERS:
        servers = registry.list_servers()
        if not servers:
            return "Серверы\n\nВ конфиге пока нет enabled-серверов."

        lines = ["Серверы", ""]
        for server in servers:
            icon = f"{server.icon} " if server.icon else ""
            provider_count = len([provider for provider in server.providers if provider.enabled])
            server_name = f"{icon}{escape(server.title)}"
            server_key = escape(server.key)
            lines.append(f"{server_name} (<code>{server_key}</code>) · providers: {provider_count}")
        return "\n".join(lines)

    if section == MenuSection.PROFILE:
        telegram_id_line = (
            f"Мой Telegram ID: <code>{telegram_user_id}</code>"
            if telegram_user_id is not None
            else "Мой Telegram ID пока недоступен."
        )
        return "\n".join(
            [
                "Мой профиль",
                "",
                f"Текущая роль: {role.value}",
                telegram_id_line,
                "Выдача статистики, конфигов и Telegram ID будет добавлена на следующих этапах.",
            ]
        )

    if section == MenuSection.TELEGRAM_ID:
        return "\n".join(
            [
                "Мой Telegram ID",
                "",
                (
                    f"Ваш Telegram ID: <code>{telegram_user_id}</code>"
                    if telegram_user_id is not None
                    else "Telegram ID пока недоступен."
                ),
            ]
        )

    if section == MenuSection.ADMIN:
        return "\n".join(
            [
                "Админка",
                "",
                "Доступны базовые административные функции ядра.",
                "Управление пользователями уже доступно из этого раздела.",
                "Рассылки и статистические отчёты будут добавлены дальше.",
            ]
        )

    return render_home_text(role=role, registry=registry)
