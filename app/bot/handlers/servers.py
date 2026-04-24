"""Handlers for server navigation and host actions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.callbacks import (
    HostActionCallback,
    MenuActionCallback,
    MenuSection,
    ProviderClientAction,
    ProviderClientActionCallback,
    ServerSection,
    ServerSectionCallback,
    ServerSelectCallback,
)
from app.bot.formatters import (
    render_host_action_error,
    render_host_action_result,
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
    build_server_back_keyboard,
    build_server_card_keyboard,
    build_server_list_keyboard,
    build_server_providers_keyboard,
    build_server_system_keyboard,
)
from app.context import ApplicationContext
from app.core.permissions import UserRole

router = Router(name="servers")


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
