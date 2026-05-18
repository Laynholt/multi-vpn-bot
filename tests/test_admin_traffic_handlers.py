from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import SimpleNamespace

import pytest

from app.bot.callbacks import AdminTrafficStatsAction, AdminTrafficStatsCallback
from app.bot.handlers import admin_users
from app.core.config import load_config
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry
from app.services.config_delivery import (
    ConfigDeliveryArchive,
    ConfigDeliveryFile,
    ConfigDeliveryResult,
)
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


class FakeConfigCallback(FakeCallback):
    def __init__(self, bot: FakeBot) -> None:
        super().__init__()
        self.bot = bot
        self.from_user = SimpleNamespace(id=500)


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


class FakeBot:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    async def send_document(
        self,
        *,
        chat_id: int,
        document: object,
        caption: str,
    ) -> None:
        self.documents.append(
            {
                "chat_id": chat_id,
                "filename": getattr(document, "filename", None),
                "caption": caption,
            }
        )


class FakeAdminMessage:
    def __init__(self, text: str, bot: FakeBot | None = None) -> None:
        self.text = text
        self.bot = bot
        self.from_user = SimpleNamespace(id=500)


@dataclass
class FakeConfigDeliveryService:
    user_calls: list[int]
    client_calls: list[int]
    result: ConfigDeliveryResult
    client_file: ConfigDeliveryFile | None = None
    error: Exception | None = None
    archive_calls: list[dict[str, object]] = field(default_factory=list)

    async def list_user_config_files(self, *, telegram_user_id: int) -> ConfigDeliveryResult:
        self.user_calls.append(telegram_user_id)
        if self.error is not None:
            raise self.error
        return self.result

    async def export_client_config_file(self, *, vpn_client_id: int) -> ConfigDeliveryFile:
        self.client_calls.append(vpn_client_id)
        if self.error is not None:
            raise self.error
        if self.client_file is None:
            raise RuntimeError("missing fake client file")
        return self.client_file

    def build_config_archive(
        self,
        *,
        target_user_id: int,
        files: tuple[ConfigDeliveryFile, ...],
    ) -> ConfigDeliveryArchive:
        self.archive_calls.append(
            {
                "target_user_id": target_user_id,
                "file_count": len(files),
            }
        )
        return ConfigDeliveryArchive(
            filename=f"vpn_configs_{target_user_id}.zip",
            content=b"zip-content",
            file_count=len(files),
        )


@dataclass
class FakeAdminAuditService:
    calls: list[dict[str, object]]

    async def record_config_delivery(
        self,
        *,
        admin_telegram_user_id: int,
        target_telegram_user_id: int,
        vpn_client_id: int | None,
        result: ConfigDeliveryResult,
    ) -> None:
        self.calls.append(
            {
                "admin_telegram_user_id": admin_telegram_user_id,
                "target_telegram_user_id": target_telegram_user_id,
                "vpn_client_id": vpn_client_id,
                "file_count": len(result.files),
                "error_count": len(result.errors),
            }
        )


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


@pytest.mark.asyncio
async def test_send_config_command_sends_user_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="alice.conf",
                    content=b"config",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice Phone",
                ),
            ),
            errors=(),
        ),
    )

    await admin_users.send_config_command(
        FakeAdminMessage("/send_config user=1001", bot),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.ADMIN,
    )

    assert service.user_calls == [1001]
    assert service.client_calls == []
    assert bot.documents == [
        {
            "chat_id": 1001,
            "filename": "alice.conf",
            "caption": "VPN config: Alice Phone",
        }
    ]
    assert audit_service.calls == [
        {
            "admin_telegram_user_id": 500,
            "target_telegram_user_id": 1001,
            "vpn_client_id": None,
            "file_count": 1,
            "error_count": 0,
        }
    ]
    assert "Отправлено: 1" in sent[0]["text"]


@pytest.mark.asyncio
async def test_send_config_command_sends_selected_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    config_file = ConfigDeliveryFile(
        filename="bob.conf",
        content=b"config",
        server_key="vps-nl",
        provider_type=ProviderType.WIREGUARD,
        provider_client_id="peer-2",
        display_name="Bob Laptop",
    )
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(files=(), errors=()),
        client_file=config_file,
    )

    await admin_users.send_config_command(
        FakeAdminMessage("/send_config user=1001 client=42", bot),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.ADMIN,
    )

    assert service.user_calls == []
    assert service.client_calls == [42]
    assert bot.documents[0]["chat_id"] == 1001
    assert bot.documents[0]["filename"] == "bob.conf"
    assert audit_service.calls[0]["vpn_client_id"] == 42
    assert "Отправлено: 1" in sent[0]["text"]


@pytest.mark.asyncio
async def test_send_config_command_archives_multiple_user_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="alice.conf",
                    content=b"alice",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice Phone",
                ),
                ConfigDeliveryFile(
                    filename="bob.conf",
                    content=b"bob",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-2",
                    display_name="Bob Laptop",
                ),
            ),
            errors=(),
        ),
    )

    await admin_users.send_config_command(
        FakeAdminMessage("/send_config user=1001", bot),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.ADMIN,
    )

    assert service.archive_calls == [{"target_user_id": 1001, "file_count": 2}]
    assert bot.documents == [
        {
            "chat_id": 1001,
            "filename": "vpn_configs_1001.zip",
            "caption": "VPN configs archive: 2 files",
        }
    ]
    assert audit_service.calls[0]["file_count"] == 2
    assert "Отправлено: 2" in sent[0]["text"]


@pytest.mark.asyncio
async def test_send_config_command_can_disable_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="alice.conf",
                    content=b"alice",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice Phone",
                ),
                ConfigDeliveryFile(
                    filename="bob.conf",
                    content=b"bob",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-2",
                    display_name="Bob Laptop",
                ),
            ),
            errors=(),
        ),
    )

    await admin_users.send_config_command(
        FakeAdminMessage("/send_config user=1001 archive=false", bot),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.ADMIN,
    )

    assert service.archive_calls == []
    assert [item["filename"] for item in bot.documents] == ["alice.conf", "bob.conf"]
    assert "Отправлено: 2" in sent[0]["text"]


@pytest.mark.asyncio
async def test_send_config_command_reports_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(files=(), errors=()),
        error=RuntimeError("provider failed"),
    )

    await admin_users.send_config_command(
        FakeAdminMessage("/send_config user=1001", bot),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.ADMIN,
    )

    assert bot.documents == []
    assert audit_service.calls == []
    assert "Не удалось выдать конфиги" in sent[0]["text"]
    assert "provider failed" in sent[0]["text"]


@pytest.mark.asyncio
async def test_send_config_command_ignores_regular_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(files=(), errors=()),
    )

    await admin_users.send_config_command(
        FakeAdminMessage("/send_config user=1001", bot),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.USER,
    )

    assert service.user_calls == []
    assert bot.documents == []
    assert audit_service.calls == []
    assert sent == []


@pytest.mark.asyncio
async def test_send_config_callback_sends_user_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(admin_users, "send_or_edit_text", fake_send_or_edit_text)
    bot = FakeBot()
    audit_service = FakeAdminAuditService(calls=[])
    service = FakeConfigDeliveryService(
        user_calls=[],
        client_calls=[],
        result=ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="alice.conf",
                    content=b"config",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice Phone",
                ),
            ),
            errors=(),
        ),
    )

    await admin_users.send_config_from_user_card(
        FakeConfigCallback(bot),
        SimpleNamespace(action="cfg", user_id=1001, page=0),
        SimpleNamespace(config_delivery_service=service, admin_audit_service=audit_service),
        UserRole.ADMIN,
    )

    assert service.user_calls == [1001]
    assert bot.documents == [
        {
            "chat_id": 1001,
            "filename": "alice.conf",
            "caption": "VPN config: Alice Phone",
        }
    ]
    assert audit_service.calls[0]["target_telegram_user_id"] == 1001
    assert "Отправлено: 1" in sent[0]["text"]


@pytest.mark.asyncio
async def test_send_config_callback_rejects_regular_user() -> None:
    callback = FakeConfigCallback(FakeBot())

    await admin_users.send_config_from_user_card(
        callback,
        SimpleNamespace(action="cfg", user_id=1001, page=0),
        SimpleNamespace(
            config_delivery_service=FakeConfigDeliveryService(
                user_calls=[],
                client_calls=[],
                result=ConfigDeliveryResult(files=(), errors=()),
            ),
            admin_audit_service=FakeAdminAuditService(calls=[]),
        ),
        UserRole.USER,
    )

    assert callback.answers == [("Недостаточно прав.", True)]
    assert callback.bot.documents == []
