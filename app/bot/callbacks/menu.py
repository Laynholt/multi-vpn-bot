"""Callback data for basic menu navigation."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

from app.bot.menu_sections import MenuSection


class MenuActionCallback(CallbackData, prefix="menu"):
    section: MenuSection
