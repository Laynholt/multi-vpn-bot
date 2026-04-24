from __future__ import annotations

from app.bot.formatters import render_admin_traffic_summary
from app.core.config.models import ProviderType
from app.services.traffic_stats import (
    TrafficAdminClientDailySummary,
    TrafficAdminDailySummary,
)


def test_render_admin_traffic_summary_escapes_and_summarizes_clients() -> None:
    summary = TrafficAdminDailySummary(
        date_from=None,
        date_to=None,
        server_key=None,
        provider_type=None,
        clients=(
            TrafficAdminClientDailySummary(
                vpn_client_id=1,
                server_key="srv<html>",
                provider_type=ProviderType.WIREGUARD,
                provider_client_id="peer-1",
                display_name="<Alice>",
                telegram_user_id=1001,
                rx_bytes=1024,
                tx_bytes=2048,
                total_bytes=3072,
            ),
        ),
        rx_bytes=1024,
        tx_bytes=2048,
        total_bytes=3072,
    )

    text = render_admin_traffic_summary(summary)

    assert "Админская статистика" in text
    assert "Traffic total: 3.0 KiB" in text
    assert "srv&lt;html&gt;" in text
    assert "&lt;Alice&gt;" in text
    assert "user: 1001" in text


def test_render_admin_traffic_summary_handles_empty_clients() -> None:
    summary = TrafficAdminDailySummary(
        date_from=None,
        date_to=None,
        server_key=None,
        provider_type=None,
        clients=(),
        rx_bytes=0,
        tx_bytes=0,
        total_bytes=0,
    )

    text = render_admin_traffic_summary(summary)

    assert "Данных по трафику пока нет" in text
