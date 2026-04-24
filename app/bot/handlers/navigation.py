"""Basic inline navigation handlers."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.formatters import (
    render_section_text,
    render_user_configs_result,
    render_user_stats_summary,
)
from app.bot.handlers.common import send_or_edit_text
from app.bot.keyboards import build_back_home_keyboard
from app.context import ApplicationContext
from app.core.permissions import UserRole
from app.services.config_delivery import ConfigDeliveryFile
from app.services.users import TelegramUserSnapshot

router = Router(name="navigation")


async def _send_config_files(
    *,
    callback: CallbackQuery,
    config_files: tuple[ConfigDeliveryFile, ...],
) -> None:
    if not isinstance(callback.message, Message):
        return
    for config_file in config_files:
        await callback.message.answer_document(
            BufferedInputFile(
                config_file.content,
                filename=config_file.filename,
            ),
            caption=config_file.display_name,
        )


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


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.MY_CONFIGS))
async def open_my_configs_section(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
    telegram_user: TelegramUserSnapshot,
) -> None:
    result = await app_context.config_delivery_service.list_user_config_files(
        telegram_user_id=telegram_user.telegram_user_id,
    )
    await send_or_edit_text(
        event=callback,
        text=render_user_configs_result(result),
        reply_markup=build_back_home_keyboard(),
    )
    await _send_config_files(callback=callback, config_files=result.files)


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.MY_STATS))
async def open_my_stats_section(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
    telegram_user: TelegramUserSnapshot,
) -> None:
    summary = await app_context.traffic_stats_service.summarize_daily_stats_for_user(
        telegram_user_id=telegram_user.telegram_user_id,
    )
    await send_or_edit_text(
        event=callback,
        text=render_user_stats_summary(summary),
        reply_markup=build_back_home_keyboard(),
    )
