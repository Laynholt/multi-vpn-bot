"""Admin handlers for Telegram user management."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import date

from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot.callbacks import (
    AdminTrafficStatsAction,
    AdminTrafficStatsCallback,
    AdminUserManageCallback,
    AdminUsersPageCallback,
    MenuActionCallback,
)
from app.bot.formatters import (
    render_admin_config_delivery_result,
    render_admin_traffic_summary,
    render_admin_user_card,
    render_admin_users_page,
)
from app.bot.handlers.common import send_or_edit_text
from app.bot.keyboards import (
    build_admin_section_keyboard,
    build_admin_traffic_keyboard,
    build_admin_user_card_keyboard,
    build_admin_users_page_keyboard,
)
from app.bot.menu_sections import MenuSection
from app.bot.user_admin_actions import AdminUserAction
from app.context import ApplicationContext
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.services.config_delivery import ConfigDeliveryFile, ConfigDeliveryResult
from app.services.traffic_stats import TrafficAdminDailySummary

router = Router(name="admin-users")

MAX_ADMIN_TRAFFIC_CSV_ROWS = 10_000


@dataclass(frozen=True, slots=True)
class AdminConfigDeliveryQuery:
    target_user_id: int
    vpn_client_id: int | None = None


@dataclass(frozen=True, slots=True)
class AdminTrafficStatsQuery:
    server_key: str | None = None
    provider_type: ProviderType | None = None
    telegram_user_id: int | None = None
    vpn_client_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


def _admin_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user is not None else None


async def _ensure_admin(callback: CallbackQuery, user_role: UserRole) -> bool:
    if user_role == UserRole.ADMIN:
        return True
    await callback.answer("Недостаточно прав.", show_alert=True)
    return False


async def _send_traffic_csv(
    *,
    callback: CallbackQuery,
    content: bytes,
    filename: str,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer("Не удалось отправить CSV.", show_alert=True)
        return
    await callback.message.answer_document(
        BufferedInputFile(content, filename=filename),
        caption="CSV export: admin traffic stats",
    )


async def _send_message_traffic_csv(
    *,
    message: Message,
    content: bytes,
    filename: str,
) -> None:
    await message.answer_document(
        BufferedInputFile(content, filename=filename),
        caption="CSV export: admin traffic stats",
    )


async def _send_config_delivery_files(
    *,
    bot: Bot,
    target_user_id: int,
    files: tuple[ConfigDeliveryFile, ...],
) -> None:
    for item in files:
        await bot.send_document(
            chat_id=target_user_id,
            document=BufferedInputFile(item.content, filename=item.filename),
            caption=f"VPN config: {item.display_name}",
        )


def _normalize_optional(value: str) -> str | None:
    return None if value.lower() in {"all", "-", "none"} else value


def _parse_admin_config_delivery_query(text: str) -> AdminConfigDeliveryQuery:
    parts = shlex.split(text)
    values: dict[str, str] = {}
    allowed_keys = {"user", "chat", "client"}
    for part in parts[1:]:
        if "=" not in part:
            raise ValueError("Usage: /send_config user=<telegram_id> [client=<vpn_client_id>]")
        key, value = part.split("=", 1)
        if key not in allowed_keys:
            raise ValueError(f"Unknown argument: {key}")
        values[key] = value

    target_user_value = values.get("user") or values.get("chat")
    if target_user_value is None:
        raise ValueError("Usage: /send_config user=<telegram_id> [client=<vpn_client_id>]")

    client_value = values.get("client")
    return AdminConfigDeliveryQuery(
        target_user_id=int(target_user_value),
        vpn_client_id=int(client_value) if client_value is not None else None,
    )


def _parse_admin_traffic_stats_query(text: str) -> AdminTrafficStatsQuery:
    parts = shlex.split(text)
    values: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            raise ValueError(
                "Usage: /stats server=<key|all> provider=<wireguard|3xui|all> "
                "user=<telegram_id|all> client=<vpn_client_id|all> "
                "from=<YYYY-MM-DD|all> to=<YYYY-MM-DD|all>"
            )
        key, value = part.split("=", 1)
        values[key] = value

    server_key = _normalize_optional(values.get("server", "all"))
    provider_value = _normalize_optional(values.get("provider", "all"))
    user_value = _normalize_optional(values.get("user", "all"))
    client_value = _normalize_optional(values.get("client", "all"))
    from_value = _normalize_optional(values.get("from", "all"))
    to_value = _normalize_optional(values.get("to", "all"))

    return AdminTrafficStatsQuery(
        server_key=server_key,
        provider_type=ProviderType(provider_value) if provider_value is not None else None,
        telegram_user_id=int(user_value) if user_value is not None else None,
        vpn_client_id=int(client_value) if client_value is not None else None,
        date_from=date.fromisoformat(from_value) if from_value is not None else None,
        date_to=date.fromisoformat(to_value) if to_value is not None else None,
    )


async def _load_admin_traffic_summary(
    *,
    app_context: ApplicationContext,
    query: AdminTrafficStatsQuery,
) -> TrafficAdminDailySummary:
    return await app_context.traffic_stats_service.summarize_daily_stats_for_admin(
        server_key=query.server_key,
        provider_type=query.provider_type,
        telegram_user_id=query.telegram_user_id,
        vpn_client_id=query.vpn_client_id,
        date_from=query.date_from,
        date_to=query.date_to,
    )


async def _load_admin_config_delivery_result(
    *,
    app_context: ApplicationContext,
    query: AdminConfigDeliveryQuery,
) -> ConfigDeliveryResult:
    if query.vpn_client_id is None:
        return await app_context.config_delivery_service.list_user_config_files(
            telegram_user_id=query.target_user_id,
        )

    config_file = await app_context.config_delivery_service.export_client_config_file(
        vpn_client_id=query.vpn_client_id,
    )
    return ConfigDeliveryResult(files=(config_file,), errors=())


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.ADMIN))
async def admin_home(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    await send_or_edit_text(
        event=callback,
        text=(
            "Админка\n\n"
            "Доступны базовые административные функции ядра.\n"
            "Выберите раздел для продолжения."
        ),
        reply_markup=build_admin_section_keyboard(),
    )


@router.callback_query(AdminTrafficStatsCallback.filter())
async def open_admin_traffic_stats(
    callback: CallbackQuery,
    callback_data: AdminTrafficStatsCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return

    server_key = None if callback_data.server == "all" else callback_data.server
    summary = await _load_admin_traffic_summary(
        app_context=app_context,
        query=AdminTrafficStatsQuery(server_key=server_key),
    )
    if callback_data.action == AdminTrafficStatsAction.CSV:
        content = app_context.traffic_stats_service.export_admin_daily_csv(
            summary,
            delimiter=app_context.config.statistics.csv_delimiter,
            max_rows=MAX_ADMIN_TRAFFIC_CSV_ROWS,
        )
        await _send_traffic_csv(
            callback=callback,
            content=content,
            filename=f"traffic_stats_{server_key or 'all'}.csv",
        )
        return

    await send_or_edit_text(
        event=callback,
        text=render_admin_traffic_summary(summary),
        reply_markup=build_admin_traffic_keyboard(
            registry=app_context.server_registry,
            server_key=server_key,
        ),
    )


@router.message(F.text.startswith("/stats_csv"))
async def open_admin_traffic_stats_csv_command(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if user_role != UserRole.ADMIN:
        return

    try:
        query = _parse_admin_traffic_stats_query(message.text or "")
        summary = await _load_admin_traffic_summary(app_context=app_context, query=query)
        content = app_context.traffic_stats_service.export_admin_daily_csv(
            summary,
            delimiter=app_context.config.statistics.csv_delimiter,
            max_rows=MAX_ADMIN_TRAFFIC_CSV_ROWS,
        )
    except Exception as exc:
        await send_or_edit_text(event=message, text=f"Не удалось построить CSV: {exc}")
        return

    await _send_message_traffic_csv(
        message=message,
        content=content,
        filename=f"traffic_stats_{query.server_key or 'all'}.csv",
    )


@router.message(F.text.startswith("/stats"))
async def open_admin_traffic_stats_command(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if user_role != UserRole.ADMIN:
        return

    try:
        query = _parse_admin_traffic_stats_query(message.text or "")
        summary = await _load_admin_traffic_summary(app_context=app_context, query=query)
        text = render_admin_traffic_summary(summary)
    except Exception as exc:
        text = f"Не удалось построить статистику: {exc}"

    await send_or_edit_text(event=message, text=text)


@router.message(F.text.startswith("/send_config"))
async def send_config_command(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if user_role != UserRole.ADMIN:
        return

    try:
        query = _parse_admin_config_delivery_query(message.text or "")
        if message.bot is None:
            raise RuntimeError("Telegram bot is unavailable")
        admin_telegram_user_id = _admin_user_id(message)
        if admin_telegram_user_id is None:
            raise RuntimeError("Admin Telegram user is unavailable")
        result = await _load_admin_config_delivery_result(app_context=app_context, query=query)
        await _send_config_delivery_files(
            bot=message.bot,
            target_user_id=query.target_user_id,
            files=result.files,
        )
        await app_context.admin_audit_service.record_config_delivery(
            admin_telegram_user_id=admin_telegram_user_id,
            target_telegram_user_id=query.target_user_id,
            vpn_client_id=query.vpn_client_id,
            result=result,
        )
        text = render_admin_config_delivery_result(
            target_user_id=query.target_user_id,
            result=result,
        )
    except Exception as exc:
        text = f"Не удалось выдать конфиги: {exc}"

    await send_or_edit_text(event=message, text=text)


@router.callback_query(AdminUsersPageCallback.filter())
async def list_users_page(
    callback: CallbackQuery,
    callback_data: AdminUsersPageCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    page_data = await app_context.telegram_user_service.list_users(page=callback_data.page)
    await send_or_edit_text(
        event=callback,
        text=render_admin_users_page(page_data),
        reply_markup=build_admin_users_page_keyboard(page_data),
    )


@router.callback_query(AdminUserManageCallback.filter(F.action == AdminUserAction.OPEN))
async def open_user_card(
    callback: CallbackQuery,
    callback_data: AdminUserManageCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    user = await app_context.telegram_user_service.get_user(telegram_user_id=callback_data.user_id)
    if user is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await send_or_edit_text(
        event=callback,
        text=render_admin_user_card(user),
        reply_markup=build_admin_user_card_keyboard(user=user, page=callback_data.page),
    )


@router.callback_query(
    AdminUserManageCallback.filter(
        F.action.in_([AdminUserAction.BAN, AdminUserAction.UNBAN, AdminUserAction.DELETE])
    ),
)
async def change_user_status(
    callback: CallbackQuery,
    callback_data: AdminUserManageCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    if callback_data.action == AdminUserAction.BAN:
        await app_context.telegram_user_service.ban_user(telegram_user_id=callback_data.user_id)
    elif callback_data.action == AdminUserAction.UNBAN:
        await app_context.telegram_user_service.unban_user(telegram_user_id=callback_data.user_id)
    elif callback_data.action == AdminUserAction.DELETE:
        await app_context.telegram_user_service.soft_delete_user(
            telegram_user_id=callback_data.user_id
        )

    user = await app_context.telegram_user_service.get_user(telegram_user_id=callback_data.user_id)
    if user is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await send_or_edit_text(
        event=callback,
        text=render_admin_user_card(user),
        reply_markup=build_admin_user_card_keyboard(user=user, page=callback_data.page),
    )
