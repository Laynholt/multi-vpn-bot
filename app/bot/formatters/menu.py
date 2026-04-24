"""Formatting helpers for the Telegram inline menu."""

from __future__ import annotations

from html import escape

from app.bot.menu_sections import MenuSection
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry
from app.services.config_delivery import ConfigDeliveryResult
from app.services.traffic_stats import TrafficUserDailySummary


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


def render_user_configs_result(result: ConfigDeliveryResult) -> str:
    if not result.files and not result.errors:
        return "\n".join(
            [
                "Мои конфиги",
                "",
                "Привязанные VPN-клиенты не найдены.",
            ]
        )

    lines = [
        "Мои конфиги",
        "",
        f"Configs ready: {len(result.files)}",
        f"Errors: {len(result.errors)}",
    ]
    if result.files:
        lines.append("")
        for item in result.files:
            lines.append(
                f"- {escape(item.display_name)} "
                f"(<code>{escape(item.server_key)}</code>, "
                f"<code>{escape(item.provider_type.value)}</code>)"
            )
    if result.errors:
        lines.append("")
        lines.append("Не удалось получить:")
        for error in result.errors:
            lines.append(
                f"- {escape(error.display_name)} "
                f"(<code>{escape(error.server_key)}</code>): {escape(error.message)}"
            )
    return "\n".join(lines)


def _format_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def render_user_stats_summary(summary: TrafficUserDailySummary) -> str:
    if not summary.clients:
        return "\n".join(
            [
                "Моя статистика",
                "",
                "Привязанные VPN-клиенты не найдены.",
            ]
        )

    lines = [
        "Моя статистика",
        "",
        f"Traffic total: {_format_bytes(summary.total_bytes)}",
        f"RX: {_format_bytes(summary.rx_bytes)}",
        f"TX: {_format_bytes(summary.tx_bytes)}",
        "",
        "Клиенты:",
    ]
    for client in summary.clients:
        lines.append(
            f"- {escape(client.display_name)} "
            f"(<code>{escape(client.server_key)}</code>): "
            f"{_format_bytes(client.total_bytes)}"
        )
    return "\n".join(lines)
