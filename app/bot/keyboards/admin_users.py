"""Inline keyboards for admin user management."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import AdminUserManageCallback, AdminUsersPageCallback, MenuActionCallback
from app.bot.menu_sections import MenuSection
from app.bot.user_admin_actions import AdminUserAction
from app.services.users import TelegramUserPage, TelegramUserSnapshot


def build_admin_section_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Пользователи",
        callback_data=AdminUsersPageCallback(page=0).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_admin_users_page_keyboard(page_data: TelegramUserPage) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in page_data.items:
        label = user.username or user.first_name or str(user.telegram_user_id)
        builder.button(
            text=f"{label} · {user.status.value}",
            callback_data=AdminUserManageCallback(
                action=AdminUserAction.OPEN,
                user_id=user.telegram_user_id,
                page=page_data.page,
            ).pack(),
        )

    if page_data.page > 0:
        builder.button(
            text="← Пред",
            callback_data=AdminUsersPageCallback(page=page_data.page - 1).pack(),
        )
    if page_data.has_next:
        builder.button(
            text="След →",
            callback_data=AdminUsersPageCallback(page=page_data.page + 1).pack(),
        )

    builder.button(
        text="Назад",
        callback_data=MenuActionCallback(section=MenuSection.ADMIN).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1, 2, 2)
    return builder.as_markup()


def build_admin_user_card_keyboard(
    *,
    user: TelegramUserSnapshot,
    page: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if user.status.value == "banned":
        builder.button(
            text="Разбанить",
            callback_data=AdminUserManageCallback(
                action=AdminUserAction.UNBAN,
                user_id=user.telegram_user_id,
                page=page,
            ).pack(),
        )
    else:
        builder.button(
            text="Забанить",
            callback_data=AdminUserManageCallback(
                action=AdminUserAction.BAN,
                user_id=user.telegram_user_id,
                page=page,
            ).pack(),
        )

    if user.status.value != "deleted":
        builder.button(
            text="Мягко удалить",
            callback_data=AdminUserManageCallback(
                action=AdminUserAction.DELETE,
                user_id=user.telegram_user_id,
                page=page,
            ).pack(),
        )

    builder.button(
        text="К списку",
        callback_data=AdminUsersPageCallback(page=page).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(2, 2)
    return builder.as_markup()
