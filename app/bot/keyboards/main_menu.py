"""Inline keyboards for main navigation."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.core.permissions import UserRole


def build_main_menu_keyboard(*, role: UserRole, has_servers: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if role == UserRole.ADMIN and has_servers:
        builder.button(
            text="Серверы",
            callback_data=MenuActionCallback(section=MenuSection.SERVERS).pack(),
        )

    builder.button(
        text="Мой профиль",
        callback_data=MenuActionCallback(section=MenuSection.PROFILE).pack(),
    )
    builder.button(
        text="Мои конфиги",
        callback_data=MenuActionCallback(section=MenuSection.MY_CONFIGS).pack(),
    )
    builder.button(
        text="Мой Telegram ID",
        callback_data=MenuActionCallback(section=MenuSection.TELEGRAM_ID).pack(),
    )

    if role == UserRole.ADMIN:
        builder.button(
            text="Админка",
            callback_data=MenuActionCallback(section=MenuSection.ADMIN).pack(),
        )

    builder.adjust(1)
    return builder.as_markup()


def build_back_home_keyboard(*, allow_back: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if allow_back:
        builder.button(
            text="Назад",
            callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
        )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(2 if allow_back else 1)
    return builder.as_markup()
