from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.core.config.models import DatabaseConfig, ProviderType
from app.infrastructure.db import DatabaseManager
from app.services.admin_audit import AdminAuditService
from app.services.config_delivery import (
    ConfigDeliveryError,
    ConfigDeliveryFile,
    ConfigDeliveryResult,
)


@pytest.fixture
async def database(tmp_path) -> AsyncIterator[DatabaseManager]:  # noqa: ANN001
    manager = DatabaseManager(DatabaseConfig(sqlite_path=tmp_path / "test.db"))
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.dispose()


@pytest.mark.asyncio
async def test_record_config_delivery_writes_admin_action_log(
    database: DatabaseManager,
) -> None:
    service = AdminAuditService(database)

    entry = await service.record_config_delivery(
        admin_telegram_user_id=500,
        target_telegram_user_id=1001,
        vpn_client_id=42,
        result=ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="alice.conf",
                    content=b"private config must not be persisted",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice Phone",
                ),
            ),
            errors=(
                ConfigDeliveryError(
                    server_key="vps-de",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-2",
                    display_name="Bob Laptop",
                    message="provider disabled",
                ),
            ),
        ),
    )

    assert entry.admin_telegram_user_id == 500
    assert entry.action == "config_delivery.send"
    assert entry.target_type == "telegram_user"
    assert entry.target_id == "1001"
    assert entry.payload["target_telegram_user_id"] == 1001
    assert entry.payload["vpn_client_id"] == 42
    assert entry.payload["file_count"] == 1
    assert entry.payload["error_count"] == 1
    assert entry.payload["files"] == [
        {
            "filename": "alice.conf",
            "server_key": "vps-nl",
            "provider_type": "wireguard",
            "provider_client_id": "peer-1",
            "display_name": "Alice Phone",
        }
    ]
    assert "content" not in entry.payload["files"][0]

    recent = await service.list_recent(limit=10)

    assert [item.id for item in recent] == [entry.id]
    assert recent[0].payload == entry.payload
