"""Formatting helpers for server Telegram UI."""

from __future__ import annotations

from html import escape

from app.core.registry import RegisteredServer, ServerRegistry
from app.providers import BaseProvider
from app.services.host_actions import HostActionDefinition, HostActionExecution


def _server_title(server: RegisteredServer) -> str:
    icon = f"{escape(server.icon)} " if server.icon else ""
    return f"{icon}{escape(server.title)}"


def render_server_list_text(registry: ServerRegistry) -> str:
    servers = registry.list_servers()
    if not servers:
        return "Серверы\n\nВ конфиге пока нет enabled-серверов."

    lines = ["Серверы", ""]
    for server in servers:
        active_providers = len([provider for provider in server.providers if provider.enabled])
        lines.append(
            f"{_server_title(server)} · <code>{escape(server.key)}</code> "
            f"· providers: {active_providers}"
        )
    return "\n".join(lines)


def render_server_card_text(server: RegisteredServer) -> str:
    active_providers = len([provider for provider in server.providers if provider.enabled])
    enabled_actions = [
        key
        for key in ("server_status", "speedtest", "vnstat_week", "healthcheck")
        if getattr(server.host_actions, key)
    ]
    lines = [
        _server_title(server),
        "",
        f"Ключ: <code>{escape(server.key)}</code>",
        f"Транспорт: {server.connection.mode.value}",
        f"Провайдеров: {active_providers} active / {len(server.providers)} total",
        f"Host actions: {len(enabled_actions)} enabled",
    ]
    if server.tags:
        lines.append(f"Теги: {escape(', '.join(server.tags))}")
    return "\n".join(lines)


def render_server_system_text(
    *,
    server: RegisteredServer,
    actions: tuple[HostActionDefinition, ...],
) -> str:
    lines = [
        f"Система · {_server_title(server)}",
        "",
    ]
    if not actions:
        lines.append("Для этого сервера не включены системные действия.")
        return "\n".join(lines)

    lines.append("Доступные действия:")
    for action in actions:
        lines.append(f"- {escape(action.title)}")
    return "\n".join(lines)


def render_server_providers_text(
    server: RegisteredServer,
    *,
    providers: tuple[BaseProvider, ...] = (),
) -> str:
    lines = [
        f"Провайдеры · {_server_title(server)}",
        "",
    ]
    if not server.providers:
        lines.append("Для этого сервера провайдеры не настроены.")
        return "\n".join(lines)

    for provider in server.providers:
        status = "enabled" if provider.enabled else "disabled"
        lines.append(f"{provider.type.value} · {status}")
        if provider.settings:
            keys = ", ".join(sorted(provider.settings))
            lines.append(f"settings: {escape(keys)}")

        provider_module = next(
            (
                item
                for item in providers
                if item.provider_type == provider.type and item.config is provider
            ),
            None,
        )
        if provider_module is not None:
            capabilities = ", ".join(provider_module.capabilities.enabled_names())
            lines.append(f"capabilities: {escape(capabilities)}")
    return "\n".join(lines)


def render_server_info_text(server: RegisteredServer) -> str:
    lines = [
        f"Информация · {_server_title(server)}",
        "",
        f"Ключ: <code>{escape(server.key)}</code>",
        f"Название: {escape(server.title)}",
        f"Транспорт: {server.connection.mode.value}",
        f"Sort order: {server.sort_order}",
    ]
    if server.connection.ssh_alias:
        lines.append(f"SSH alias: <code>{escape(server.connection.ssh_alias)}</code>")
    if server.tags:
        lines.append(f"Теги: {escape(', '.join(server.tags))}")
    return "\n".join(lines)


def _clip_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    marker = "\n[truncated]"
    if max_length <= len(marker):
        return marker[-max_length:]
    return text[: max_length - len(marker)] + marker


def render_host_action_result(
    execution: HostActionExecution,
    *,
    max_message_length: int,
) -> str:
    result = execution.result
    lines = [
        f"Host action · {escape(execution.action_key)}",
        "",
        f"server: <code>{escape(execution.server_key)}</code>",
        f"command: <code>{escape(' '.join(result.command))}</code>",
        f"exit code: {result.exit_code}",
        f"duration: {result.duration_ms} ms",
    ]
    if result.stdout:
        lines.extend(["", "stdout:", f"<pre>{escape(result.stdout)}</pre>"])
    if result.stderr:
        lines.extend(["", "stderr:", f"<pre>{escape(result.stderr)}</pre>"])
    return _clip_text("\n".join(lines), max_message_length)


def render_host_action_error(
    *,
    server_key: str,
    action_key: str,
    error: Exception,
) -> str:
    return "\n".join(
        [
            "Не удалось выполнить действие.",
            "",
            f"server: <code>{escape(server_key)}</code>",
            f"action: <code>{escape(action_key)}</code>",
            f"error: {escape(str(error))}",
        ]
    )
