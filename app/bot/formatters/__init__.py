"""Text formatters for Telegram responses."""

from app.bot.formatters.admin_users import render_admin_user_card, render_admin_users_page
from app.bot.formatters.menu import render_home_text, render_section_text
from app.bot.formatters.servers import (
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

__all__ = [
    "render_admin_user_card",
    "render_admin_users_page",
    "render_host_action_error",
    "render_host_action_result",
    "render_home_text",
    "render_provider_client_create_help",
    "render_provider_client_create_result",
    "render_provider_client_delete_confirmation",
    "render_provider_client_delete_result",
    "render_provider_clients_list",
    "render_provider_client_sync_result",
    "render_server_card_text",
    "render_server_info_text",
    "render_server_list_text",
    "render_server_providers_text",
    "render_server_system_text",
    "render_section_text",
]
