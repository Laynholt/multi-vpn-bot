"""Inline keyboards for server navigation."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import (
    HostActionCallback,
    MenuActionCallback,
    MenuSection,
    ProviderClientAction,
    ProviderClientActionCallback,
    ProviderClientItemAction,
    ProviderClientItemActionCallback,
    ServerSection,
    ServerSectionCallback,
    ServerSelectCallback,
)
from app.core.config.models import ProviderConfig, ProviderType
from app.core.registry import ServerRegistry
from app.services.client_inventory import VpnClientSnapshot
from app.services.host_actions import HostActionDefinition


def build_server_list_keyboard(registry: ServerRegistry) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for server in registry.list_servers():
        icon = f"{server.icon} " if server.icon else ""
        builder.button(
            text=f"{icon}{server.title}",
            callback_data=ServerSelectCallback(key=server.key).pack(),
        )

    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_server_card_keyboard(*, server_key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Система",
        callback_data=ServerSectionCallback(
            key=server_key,
            section=ServerSection.SYSTEM,
        ).pack(),
    )
    builder.button(
        text="Провайдеры",
        callback_data=ServerSectionCallback(
            key=server_key,
            section=ServerSection.PROVIDERS,
        ).pack(),
    )
    builder.button(
        text="Информация",
        callback_data=ServerSectionCallback(
            key=server_key,
            section=ServerSection.INFO,
        ).pack(),
    )
    builder.button(
        text="Назад",
        callback_data=MenuActionCallback(section=MenuSection.SERVERS).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1, 1, 1, 2)
    return builder.as_markup()


def build_server_system_keyboard(
    *,
    server_key: str,
    actions: tuple[HostActionDefinition, ...],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for action in actions:
        builder.button(
            text=action.title,
            callback_data=HostActionCallback(key=server_key, action=action.key).pack(),
        )

    builder.button(
        text="Назад",
        callback_data=ServerSelectCallback(key=server_key).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1, 2)
    return builder.as_markup()


def build_server_providers_keyboard(
    *,
    server_key: str,
    providers: tuple[ProviderConfig, ...],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for provider in providers:
        if not provider.enabled:
            continue
        builder.button(
            text=f"Клиенты {provider.type.value}",
            callback_data=ProviderClientActionCallback(
                key=server_key,
                provider=provider.type,
                action=ProviderClientAction.LIST,
            ).pack(),
        )
        builder.button(
            text=f"Синхронизировать {provider.type.value}",
            callback_data=ProviderClientActionCallback(
                key=server_key,
                provider=provider.type,
                action=ProviderClientAction.SYNC,
            ).pack(),
        )

    builder.button(
        text="Назад",
        callback_data=ServerSelectCallback(key=server_key).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1, 2)
    return builder.as_markup()


def build_provider_clients_keyboard(
    *,
    server_key: str,
    provider_type: ProviderType,
    clients: tuple[VpnClientSnapshot, ...],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for client in clients[:20]:
        builder.button(
            text=f"Удалить {client.display_name}",
            callback_data=ProviderClientItemActionCallback(
                key=server_key,
                provider=provider_type,
                client_id=client.id,
                action=ProviderClientItemAction.DELETE,
            ).pack(),
        )

    builder.button(
        text="Назад",
        callback_data=ServerSectionCallback(
            key=server_key,
            section=ServerSection.PROVIDERS,
        ).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1, 2)
    return builder.as_markup()


def build_provider_client_delete_confirm_keyboard(
    *,
    server_key: str,
    provider_type: ProviderType,
    client_id: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подтвердить удаление",
        callback_data=ProviderClientItemActionCallback(
            key=server_key,
            provider=provider_type,
            client_id=client_id,
            action=ProviderClientItemAction.CONFIRM_DELETE,
        ).pack(),
    )
    builder.button(
        text="Назад",
        callback_data=ProviderClientActionCallback(
            key=server_key,
            provider=provider_type,
            action=ProviderClientAction.LIST,
        ).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(1, 2)
    return builder.as_markup()


def build_server_back_keyboard(*, server_key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Назад",
        callback_data=ServerSelectCallback(key=server_key).pack(),
    )
    builder.button(
        text="Домой",
        callback_data=MenuActionCallback(section=MenuSection.HOME).pack(),
    )
    builder.adjust(2)
    return builder.as_markup()
