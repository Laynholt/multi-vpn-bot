"""Handlers for server navigation and host actions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

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
from app.bot.formatters import (
    render_host_action_error,
    render_host_action_result,
    render_provider_client_create_help,
    render_provider_client_create_result,
    render_provider_client_delete_confirmation,
    render_provider_client_delete_result,
    render_provider_client_sync_result,
    render_provider_clients_list,
    render_server_card_text,
    render_server_info_text,
    render_server_list_text,
    render_server_providers_text,
    render_server_system_text,
)
from app.bot.handlers.common import send_or_edit_text
from app.bot.keyboards import (
    build_provider_client_delete_confirm_keyboard,
    build_provider_clients_keyboard,
    build_server_back_keyboard,
    build_server_card_keyboard,
    build_server_list_keyboard,
    build_server_providers_keyboard,
    build_server_system_keyboard,
)
from app.context import ApplicationContext
from app.core.config.models import ProviderType
from app.core.permissions import UserRole

router = Router(name="servers")


def _parse_wg_create_command(text: str) -> tuple[str, ProviderType, str, str, str | None]:
    parts = text.split()
    if len(parts) < 5:
        raise ValueError(
            "Usage: /wg_create <server_key> <provider> <client_id> <allowed_ips> "
            "[display name]"
        )

    server_key = parts[1]
    provider_type = ProviderType(parts[2])
    if provider_type != ProviderType.WIREGUARD:
        raise ValueError("Only wireguard client creation is supported")

    client_id = parts[3]
    allowed_ips = parts[4]
    display_name = " ".join(parts[5:]) or None
    return server_key, provider_type, client_id, allowed_ips, display_name


async def _ensure_admin(callback: CallbackQuery, user_role: UserRole) -> bool:
    if user_role == UserRole.ADMIN:
        return True
    await callback.answer("Недостаточно прав.", show_alert=True)
    return False


@router.callback_query(MenuActionCallback.filter(F.section == MenuSection.SERVERS))
async def open_servers_section(
    callback: CallbackQuery,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    await send_or_edit_text(
        event=callback,
        text=render_server_list_text(app_context.server_registry),
        reply_markup=build_server_list_keyboard(app_context.server_registry),
    )


@router.callback_query(ServerSelectCallback.filter())
async def open_server_card(
    callback: CallbackQuery,
    callback_data: ServerSelectCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    server = app_context.server_registry.get(callback_data.key)
    await send_or_edit_text(
        event=callback,
        text=render_server_card_text(server),
        reply_markup=build_server_card_keyboard(server_key=server.key),
    )


@router.callback_query(ServerSectionCallback.filter())
async def open_server_section(
    callback: CallbackQuery,
    callback_data: ServerSectionCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return
    server = app_context.server_registry.get(callback_data.key)

    if callback_data.section == ServerSection.SYSTEM:
        actions = app_context.host_actions_service.list_enabled_actions(server.key)
        text = render_server_system_text(server=server, actions=actions)
        reply_markup = build_server_system_keyboard(server_key=server.key, actions=actions)
    elif callback_data.section == ServerSection.PROVIDERS:
        providers = tuple(
            app_context.provider_factory.create(provider_config)
            for provider_config in server.providers
            if provider_config.enabled
        )
        text = render_server_providers_text(server, providers=providers)
        reply_markup = build_server_providers_keyboard(
            server_key=server.key,
            providers=server.providers,
        )
    else:
        text = render_server_info_text(server)
        reply_markup = build_server_back_keyboard(server_key=server.key)

    await send_or_edit_text(event=callback, text=text, reply_markup=reply_markup)


@router.callback_query(HostActionCallback.filter())
async def run_host_action(
    callback: CallbackQuery,
    callback_data: HostActionCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return

    try:
        execution = await app_context.host_actions_service.run_action(
            server_key=callback_data.key,
            action_key=callback_data.action,
        )
        text = render_host_action_result(
            execution,
            max_message_length=app_context.config.telegram.max_message_length,
        )
    except Exception as exc:
        text = render_host_action_error(
            server_key=callback_data.key,
            action_key=callback_data.action,
            error=exc,
        )

    await send_or_edit_text(
        event=callback,
        text=text,
        reply_markup=build_server_back_keyboard(server_key=callback_data.key),
    )


@router.callback_query(ProviderClientActionCallback.filter())
async def handle_provider_client_action(
    callback: CallbackQuery,
    callback_data: ProviderClientActionCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return

    if callback_data.action == ProviderClientAction.CREATE:
        text = render_provider_client_create_help(
            server_key=callback_data.key,
            provider_type=callback_data.provider,
        )
        await send_or_edit_text(
            event=callback,
            text=text,
            reply_markup=build_server_back_keyboard(server_key=callback_data.key),
        )
        return

    if callback_data.action == ProviderClientAction.LIST:
        try:
            clients = await app_context.provider_client_sync_service.list_provider_clients(
                server_key=callback_data.key,
                provider_type=callback_data.provider,
            )
            text = render_provider_clients_list(
                server_key=callback_data.key,
                provider_type=callback_data.provider,
                clients=clients,
            )
            reply_markup = build_provider_clients_keyboard(
                server_key=callback_data.key,
                provider_type=callback_data.provider,
                clients=clients,
            )
        except Exception as exc:
            text = render_host_action_error(
                server_key=callback_data.key,
                action_key=f"{callback_data.provider.value}:{callback_data.action.value}",
                error=exc,
            )
            reply_markup = build_server_back_keyboard(server_key=callback_data.key)
        await send_or_edit_text(event=callback, text=text, reply_markup=reply_markup)
        return

    if callback_data.action != ProviderClientAction.SYNC:
        await callback.answer("Неизвестное действие провайдера.", show_alert=True)
        return

    try:
        result = await app_context.provider_client_sync_service.sync_provider_clients(
            server_key=callback_data.key,
            provider_type=callback_data.provider,
        )
        text = render_provider_client_sync_result(result)
    except Exception as exc:
        text = render_host_action_error(
            server_key=callback_data.key,
            action_key=f"{callback_data.provider.value}:{callback_data.action.value}",
            error=exc,
        )

    await send_or_edit_text(
        event=callback,
        text=text,
        reply_markup=build_server_back_keyboard(server_key=callback_data.key),
    )


@router.message(F.text.startswith("/wg_create"))
async def create_wireguard_client_from_command(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if user_role != UserRole.ADMIN:
        return

    try:
        server_key, provider_type, client_id, allowed_ips, display_name = (
            _parse_wg_create_command(message.text or "")
        )
        result = await app_context.provider_client_sync_service.create_wireguard_client(
            server_key=server_key,
            provider_type=provider_type,
            client_id=client_id,
            allowed_ips=allowed_ips,
            display_name=display_name,
        )
        text = render_provider_client_create_result(result)
        reply_markup = build_server_back_keyboard(server_key=server_key)
    except Exception as exc:
        text = render_host_action_error(
            server_key="-",
            action_key="wg_create",
            error=exc,
        )
        reply_markup = None

    await send_or_edit_text(event=message, text=text, reply_markup=reply_markup)


@router.callback_query(ProviderClientItemActionCallback.filter())
async def handle_provider_client_item_action(
    callback: CallbackQuery,
    callback_data: ProviderClientItemActionCallback,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if not await _ensure_admin(callback, user_role):
        return

    if callback_data.action == ProviderClientItemAction.DELETE:
        try:
            client = await app_context.provider_client_sync_service.get_provider_client(
                server_key=callback_data.key,
                provider_type=callback_data.provider,
                vpn_client_id=callback_data.client_id,
            )
            text = render_provider_client_delete_confirmation(client)
            reply_markup = build_provider_client_delete_confirm_keyboard(
                server_key=callback_data.key,
                provider_type=callback_data.provider,
                client_id=callback_data.client_id,
            )
        except Exception as exc:
            text = render_host_action_error(
                server_key=callback_data.key,
                action_key=f"{callback_data.provider.value}:{callback_data.action.value}",
                error=exc,
            )
            reply_markup = build_server_back_keyboard(server_key=callback_data.key)
        await send_or_edit_text(event=callback, text=text, reply_markup=reply_markup)
        return

    if callback_data.action == ProviderClientItemAction.CONFIRM_DELETE:
        try:
            result = await app_context.provider_client_sync_service.delete_inventory_client(
                server_key=callback_data.key,
                provider_type=callback_data.provider,
                vpn_client_id=callback_data.client_id,
            )
            text = render_provider_client_delete_result(result)
        except Exception as exc:
            text = render_host_action_error(
                server_key=callback_data.key,
                action_key=f"{callback_data.provider.value}:{callback_data.action.value}",
                error=exc,
            )
        await send_or_edit_text(
            event=callback,
            text=text,
            reply_markup=build_server_back_keyboard(server_key=callback_data.key),
        )
        return

    await callback.answer("Неизвестное действие клиента.", show_alert=True)
