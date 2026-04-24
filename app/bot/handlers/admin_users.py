"""Admin handlers for Telegram user management."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot.callbacks import (
    AdminTrafficStatsAction,
    AdminTrafficStatsCallback,
    AdminUserManageCallback,
    AdminUsersPageCallback,
    MenuActionCallback,
)
from app.bot.formatters import (
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
from app.core.permissions import UserRole

router = Router(name="admin-users")


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
    summary = await app_context.traffic_stats_service.summarize_daily_stats_for_admin(
        server_key=server_key,
    )
    if callback_data.action == AdminTrafficStatsAction.CSV:
        content = app_context.traffic_stats_service.export_admin_daily_csv(
            summary,
            delimiter=app_context.config.statistics.csv_delimiter,
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
