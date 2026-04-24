from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from app.bot.callbacks import AdminTrafficStatsAction, AdminTrafficStatsCallback
from app.bot.handlers import admin_users
from app.core.config import load_config
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry
from app.services.traffic_stats import TrafficAdminDailySummary


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


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text


@dataclass
class FakeTrafficStatsService:
    calls: list[dict[str, object]]

    async def summarize_daily_stats_for_admin(
        self,
        *,
        server_key: str | None = None,
        provider_type: object | None = None,
        telegram_user_id: int | None = None,
        vpn_client_id: int | None = None,
        date_from: object | None = None,
        date_to: object | None = None,
    ) -> TrafficAdminDailySummary:
        self.calls.append(
            {
                "server_key": server_key,
                "provider_type": provider_type,
                "telegram_user_id": telegram_user_id,
                "vpn_client_id": vpn_client_id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        return TrafficAdminDailySummary(
            date_from=None,
            date_to=None,
            server_key=server_key,
            provider_type=None,
            clients=(),
            rx_bytes=0,
            tx_bytes=0,
            total_bytes=0,
        )

    def export_admin_daily_csv(
        self,
        summary: TrafficAdminDailySummary,
        *,
        delimiter: str,
        max_rows: int | None = None,
    ) -> bytes:
        del summary, delimiter, max_rows
        return b"server_key,total_bytes\r\n"


@pytest.mark.asyncio
async def test_open_admin_traffic_report_renders_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    service = FakeTrafficStatsService(calls=[])

    await admin_users.open_admin_traffic_stats(
        FakeCallback(),
        AdminTrafficStatsCallback(action=AdminTrafficStatsAction.REPORT, server="vps-nl"),
        SimpleNamespace(
            traffic_stats_service=service,
            server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
            config=SimpleNamespace(statistics=SimpleNamespace(csv_delimiter=",")),
        ),
        UserRole.ADMIN,
    )

    assert service.calls == [
        {
            "server_key": "vps-nl",
            "provider_type": None,
            "telegram_user_id": None,
            "vpn_client_id": None,
            "date_from": None,
            "date_to": None,
        }
    ]
    assert "Админская статистика" in sent[0]["text"]


@pytest.mark.asyncio
async def test_open_admin_traffic_csv_sends_file(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_files: list[dict[str, object]] = []

    async def fake_send_traffic_csv(**kwargs: object) -> None:
        sent_files.append(kwargs)

    monkeypatch.setattr(admin_users, "_send_traffic_csv", fake_send_traffic_csv)
    service = FakeTrafficStatsService(calls=[])

    await admin_users.open_admin_traffic_stats(
        FakeCallback(),
        AdminTrafficStatsCallback(action=AdminTrafficStatsAction.CSV, server="all"),
        SimpleNamespace(
            traffic_stats_service=service,
            server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
            config=SimpleNamespace(statistics=SimpleNamespace(csv_delimiter=",")),
        ),
        UserRole.ADMIN,
    )

    assert service.calls == [
        {
            "server_key": None,
            "provider_type": None,
            "telegram_user_id": None,
            "vpn_client_id": None,
            "date_from": None,
            "date_to": None,
        }
    ]
    assert sent_files[0]["filename"] == "traffic_stats_all.csv"
    assert sent_files[0]["content"] == b"server_key,total_bytes\r\n"


@pytest.mark.asyncio
async def test_open_admin_traffic_rejects_regular_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    callback = FakeCallback()

    await admin_users.open_admin_traffic_stats(
        callback,
        AdminTrafficStatsCallback(action=AdminTrafficStatsAction.REPORT, server="all"),
        SimpleNamespace(
            traffic_stats_service=FakeTrafficStatsService(calls=[]),
            server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
            config=SimpleNamespace(statistics=SimpleNamespace(csv_delimiter=",")),
        ),
        UserRole.USER,
    )

    assert sent == []
    assert callback.answers == [("Недостаточно прав.", True)]


@pytest.mark.asyncio
async def test_stats_command_parses_extended_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    service = FakeTrafficStatsService(calls=[])

    await admin_users.open_admin_traffic_stats_command(
        FakeMessage(
            "/stats server=vps-nl provider=wireguard user=1001 "
            "client=12 from=2026-04-01 to=2026-04-30"
        ),
        SimpleNamespace(
            traffic_stats_service=service,
            server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
            config=SimpleNamespace(statistics=SimpleNamespace(csv_delimiter=",")),
        ),
        UserRole.ADMIN,
    )

    assert service.calls == [
        {
            "server_key": "vps-nl",
            "provider_type": ProviderType.WIREGUARD,
            "telegram_user_id": 1001,
            "vpn_client_id": 12,
            "date_from": date(2026, 4, 1),
            "date_to": date(2026, 4, 30),
        }
    ]
    assert "Админская статистика" in sent[0]["text"]


@pytest.mark.asyncio
async def test_stats_csv_command_sends_filtered_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_files: list[dict[str, object]] = []

    async def fake_send_message_traffic_csv(**kwargs: object) -> None:
        sent_files.append(kwargs)

    monkeypatch.setattr(admin_users, "_send_message_traffic_csv", fake_send_message_traffic_csv)
    service = FakeTrafficStatsService(calls=[])

    await admin_users.open_admin_traffic_stats_csv_command(
        FakeMessage("/stats_csv server=vps-nl provider=wireguard user=1001 client=12"),
        SimpleNamespace(
            traffic_stats_service=service,
            server_registry=ServerRegistry.from_config(load_config("configs/config.example.json")),
            config=SimpleNamespace(statistics=SimpleNamespace(csv_delimiter=",")),
        ),
        UserRole.ADMIN,
    )

    assert service.calls[0]["server_key"] == "vps-nl"
    assert service.calls[0]["provider_type"] == ProviderType.WIREGUARD
    assert service.calls[0]["telegram_user_id"] == 1001
    assert service.calls[0]["vpn_client_id"] == 12
    assert sent_files[0]["filename"] == "traffic_stats_vps-nl.csv"
