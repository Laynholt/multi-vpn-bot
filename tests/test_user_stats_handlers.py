from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.handlers import navigation
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.services.traffic_stats import TrafficUserClientDailySummary, TrafficUserDailySummary


class FakeCallback:
    pass


@dataclass
class FakeTelegramUser:
    telegram_user_id: int


class FakeTrafficStatsService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def summarize_daily_stats_for_user(
        self,
        *,
        telegram_user_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> TrafficUserDailySummary:
        self.calls.append(telegram_user_id)
        return TrafficUserDailySummary(
            telegram_user_id=telegram_user_id,
            date_from=date_from,
            date_to=date_to,
            clients=(
                TrafficUserClientDailySummary(
                    vpn_client_id=1,
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice",
                    rx_bytes=1024,
                    tx_bytes=2048,
                    total_bytes=3072,
                ),
            ),
            rx_bytes=1024,
            tx_bytes=2048,
            total_bytes=3072,
        )


@pytest.mark.asyncio
async def test_open_my_stats_sends_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs) -> None:  # noqa: ANN003
        sent.append(kwargs)

    monkeypatch.setattr(navigation, "send_or_edit_text", fake_send_or_edit_text)
    service = FakeTrafficStatsService()

    await navigation.open_my_stats_section(
        FakeCallback(),
        SimpleNamespace(traffic_stats_service=service),
        UserRole.USER,
        FakeTelegramUser(telegram_user_id=1001),
    )

    assert service.calls == [1001]
    assert "Traffic total: 3.0 KiB" in sent[0]["text"]


def test_my_stats_callback_is_short() -> None:
    packed = MenuActionCallback(section=MenuSection.MY_STATS).pack()

    assert packed == "menu:my_stats"
    assert len(packed) < 64
