"""Start handler and home-screen renderer."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.formatters import render_home_text
from app.bot.handlers.common import send_or_edit_text
from app.bot.keyboards import build_main_menu_keyboard
from app.context import ApplicationContext
from app.core.permissions import UserRole

router = Router(name="start")


async def _show_home(
    event: Message | CallbackQuery,
    *,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    await send_or_edit_text(
        event=event,
        text=render_home_text(role=user_role, registry=app_context.server_registry),
        reply_markup=build_main_menu_keyboard(
            role=user_role,
            has_servers=len(app_context.server_registry) > 0,
        ),
    )


@router.message(CommandStart())
async def start_command(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    await _show_home(message, app_context=app_context, user_role=user_role)


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.HOME))
async def home_callback_entrypoint(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    await _show_home(callback, app_context=app_context, user_role=user_role)
