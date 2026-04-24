"""Callback data for server navigation and host actions."""

from __future__ import annotations

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from app.core.config.models import ProviderType


class ServerSection(StrEnum):
    SYSTEM = "system"
    PROVIDERS = "providers"
    INFO = "info"


class ServerSelectCallback(CallbackData, prefix="srv"):
    key: str


class ServerSectionCallback(CallbackData, prefix="srvsec"):
    key: str
    section: ServerSection


class HostActionCallback(CallbackData, prefix="hact"):
    key: str
    action: str


class ProviderClientAction(StrEnum):
    LIST = "list"
    SYNC = "sync"


class ProviderClientActionCallback(CallbackData, prefix="pcli"):
    key: str
    provider: ProviderType
    action: ProviderClientAction


class ProviderClientItemAction(StrEnum):
    DELETE = "del"
    CONFIRM_DELETE = "cdel"


class ProviderClientItemActionCallback(CallbackData, prefix="pcitem"):
    key: str
    provider: ProviderType
    client_id: int
    action: ProviderClientItemAction
