from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.bot.callbacks import (
    HostActionCallback,
    ProviderClientAction,
    ProviderClientActionCallback,
    ServerSelectCallback,
)
from app.bot.handlers import servers as server_handlers
from app.core.config import load_config
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry
from app.services.host_actions import HostActionRegistry


class FakeCallback:
    def __init__(self) -> None:
        self.answers: list[tuple[str | None, bool | None]] = []

    async def answer(
        self,
        text: str | None = None,
        *,
        show_alert: bool | None = None,
    ) -> None:
        self.answers.append((text, show_alert))


class FakeHostActionsService:
    def __init__(self) -> None:
        self.actions = (HostActionRegistry().get("healthcheck"),)
        self.run_calls: list[tuple[str, str]] = []

    def list_enabled_actions(self, server_key: str):  # noqa: ANN001
        assert server_key == "vps-nl"
        return self.actions

    async def run_action(self, *, server_key: str, action_key: str):  # noqa: ANN001
        self.run_calls.append((server_key, action_key))
        raise ValueError("boom")


class FakeProviderClientSyncService:
    def __init__(self) -> None:
        self.sync_calls: list[tuple[str, ProviderType]] = []
        self.list_calls: list[tuple[str, ProviderType]] = []

    async def sync_provider_clients(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
    ) -> object:
        self.sync_calls.append((server_key, provider_type))
        return SimpleNamespace(
            server_key=server_key,
            provider_type=provider_type,
            clients=(),
        )

    async def list_provider_clients(
        self,
        *,
        server_key: str,
        provider_type: ProviderType,
    ) -> tuple[object, ...]:
        self.list_calls.append((server_key, provider_type))
        return ()


@dataclass
class FakeContext:
    server_registry: ServerRegistry
    host_actions_service: FakeHostActionsService
    provider_client_sync_service: FakeProviderClientSyncService
    config: SimpleNamespace


@pytest.mark.asyncio
async def test_open_server_card_rejects_regular_user(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs) -> None:  # noqa: ANN003
        sent.append(kwargs)

    monkeypatch.setattr(server_handlers, "send_or_edit_text", fake_send_or_edit_text)

    callback = FakeCallback()
    context = FakeContext(
        server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
        host_actions_service=FakeHostActionsService(),
        provider_client_sync_service=FakeProviderClientSyncService(),
        config=SimpleNamespace(telegram=SimpleNamespace(max_message_length=4000)),
    )

    await server_handlers.open_server_card(
        callback,
        ServerSelectCallback(key="vps-nl"),
        context,
        UserRole.USER,
    )

    assert sent == []
    assert callback.answers == [("Недостаточно прав.", True)]


@pytest.mark.asyncio
async def test_run_host_action_renders_service_error(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs) -> None:  # noqa: ANN003
        sent.append(kwargs)

    monkeypatch.setattr(server_handlers, "send_or_edit_text", fake_send_or_edit_text)

    callback = FakeCallback()
    host_actions_service = FakeHostActionsService()
    context = FakeContext(
        server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
        host_actions_service=host_actions_service,
        provider_client_sync_service=FakeProviderClientSyncService(),
        config=SimpleNamespace(telegram=SimpleNamespace(max_message_length=4000)),
    )

    await server_handlers.run_host_action(
        callback,
        HostActionCallback(key="vps-nl", action="healthcheck"),
        context,
        UserRole.ADMIN,
    )

    assert host_actions_service.run_calls == [("vps-nl", "healthcheck")]
    assert "Не удалось выполнить действие" in sent[0]["text"]
    assert "boom" in sent[0]["text"]


@pytest.mark.asyncio
async def test_sync_provider_clients_renders_sync_result(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs) -> None:  # noqa: ANN003
        sent.append(kwargs)

    monkeypatch.setattr(server_handlers, "send_or_edit_text", fake_send_or_edit_text)

    callback = FakeCallback()
    provider_client_sync_service = FakeProviderClientSyncService()
    context = FakeContext(
        server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
        host_actions_service=FakeHostActionsService(),
        provider_client_sync_service=provider_client_sync_service,
        config=SimpleNamespace(telegram=SimpleNamespace(max_message_length=4000)),
    )

    await server_handlers.handle_provider_client_action(
        callback,
        ProviderClientActionCallback(
            key="vps-nl",
            provider=ProviderType.WIREGUARD,
            action=ProviderClientAction.SYNC,
        ),
        context,
        UserRole.ADMIN,
    )

    assert provider_client_sync_service.sync_calls == [
        ("vps-nl", ProviderType.WIREGUARD)
    ]
    assert "Синхронизация клиентов" in sent[0]["text"]


@pytest.mark.asyncio
async def test_list_provider_clients_renders_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs) -> None:  # noqa: ANN003
        sent.append(kwargs)

    monkeypatch.setattr(server_handlers, "send_or_edit_text", fake_send_or_edit_text)

    callback = FakeCallback()
    provider_client_sync_service = FakeProviderClientSyncService()
    context = FakeContext(
        server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
        host_actions_service=FakeHostActionsService(),
        provider_client_sync_service=provider_client_sync_service,
        config=SimpleNamespace(telegram=SimpleNamespace(max_message_length=4000)),
    )

    await server_handlers.handle_provider_client_action(
        callback,
        ProviderClientActionCallback(
            key="vps-nl",
            provider=ProviderType.WIREGUARD,
            action=ProviderClientAction.LIST,
        ),
        context,
        UserRole.ADMIN,
    )

    assert provider_client_sync_service.list_calls == [
        ("vps-nl", ProviderType.WIREGUARD)
    ]
    assert "Клиенты провайдера" in sent[0]["text"]
