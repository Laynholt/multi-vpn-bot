"""Callback data for admin user management."""

from __future__ import annotations

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from app.bot.user_admin_actions import AdminUserAction


class AdminTrafficStatsAction(StrEnum):
    REPORT = "r"
    CSV = "csv"


class AdminUsersPageCallback(CallbackData, prefix="admin_users"):
    page: int


class AdminUserManageCallback(CallbackData, prefix="admin_user"):
    action: AdminUserAction
    user_id: int
    page: int = 0


class AdminTrafficStatsCallback(CallbackData, prefix="adm_stats"):
    action: AdminTrafficStatsAction
    server: str = "all"
