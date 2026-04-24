"""Shared helper functions for handlers."""

from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def send_or_edit_text(
    *,
    event: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit existing callback message when possible, otherwise send a new one."""

    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
            try:
                await event.message.edit_text(text=text, reply_markup=reply_markup)
            except TelegramBadRequest as exc:
                if "message is not modified" not in str(exc).lower():
                    raise
            return

    if isinstance(event, Message):
        await event.answer(text=text, reply_markup=reply_markup)
