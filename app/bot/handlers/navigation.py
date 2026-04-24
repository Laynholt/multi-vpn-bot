"""Basic inline navigation handlers."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.formatters import render_section_text
from app.bot.handlers.common import send_or_edit_text
from app.bot.keyboards import build_back_home_keyboard
from app.context import ApplicationContext
from app.core.permissions import UserRole
from app.services.users import TelegramUserSnapshot

router = Router(name="navigation")


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.PROFILE))
async def open_profile_section(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
    telegram_user: TelegramUserSnapshot,
) -> None:
    await send_or_edit_text(
        event=callback,
        text=render_section_text(
            section=MenuSection.PROFILE,
            role=user_role,
            registry=app_context.server_registry,
            telegram_user_id=telegram_user.telegram_user_id,
        ),
        reply_markup=build_back_home_keyboard(),
    )


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.TELEGRAM_ID))
async def open_telegram_id_section(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
    telegram_user: TelegramUserSnapshot,
) -> None:
    await send_or_edit_text(
        event=callback,
        text=render_section_text(
            section=MenuSection.TELEGRAM_ID,
            role=user_role,
            registry=app_context.server_registry,
            telegram_user_id=telegram_user.telegram_user_id,
        ),
        reply_markup=build_back_home_keyboard(),
    )
