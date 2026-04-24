from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.bot.callbacks import AdminTrafficStatsAction, AdminTrafficStatsCallback
from app.bot.handlers import admin_users
from app.core.config import load_config
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


@dataclass
class FakeTrafficStatsService:
    calls: list[str | None]

    async def summarize_daily_stats_for_admin(
        self,
        *,
        server_key: str | None = None,
        provider_type: object | None = None,
        date_from: object | None = None,
        date_to: object | None = None,
    ) -> TrafficAdminDailySummary:
        del provider_type, date_from, date_to
        self.calls.append(server_key)
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

    def export_admin_daily_csv(self, summary: TrafficAdminDailySummary, *, delimiter: str) -> bytes:
        del summary, delimiter
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

    assert service.calls == ["vps-nl"]
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

    assert service.calls == [None]
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
