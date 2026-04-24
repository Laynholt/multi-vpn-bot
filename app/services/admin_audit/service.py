"""Service-level API for admin action audit records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.infrastructure.db import DatabaseManager
    from app.infrastructure.db.models import AdminActionLogORM
    from app.services.config_delivery import ConfigDeliveryResult


@dataclass(frozen=True, slots=True)
class AdminActionLogSnapshot:
    id: int
    admin_telegram_user_id: int
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class AdminAuditService:
    """Writes auditable admin actions without persisting sensitive payloads."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def record_config_delivery(
        self,
        *,
        admin_telegram_user_id: int,
        target_telegram_user_id: int,
        vpn_client_id: int | None,
        result: ConfigDeliveryResult,
    ) -> AdminActionLogSnapshot:
        payload = self._build_config_delivery_payload(
            target_telegram_user_id=target_telegram_user_id,
            vpn_client_id=vpn_client_id,
            result=result,
        )
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import AdminActionLogRepository

            repository = AdminActionLogRepository(session)
            entry = await repository.create(
                admin_telegram_user_id=admin_telegram_user_id,
                action="config_delivery.send",
                target_type="telegram_user",
                target_id=str(target_telegram_user_id),
                payload=payload,
            )
            return self._to_snapshot(entry)

    async def list_recent(self, *, limit: int = 20) -> tuple[AdminActionLogSnapshot, ...]:
        async with self._database.session() as session:
            from app.infrastructure.db.repositories import AdminActionLogRepository

            repository = AdminActionLogRepository(session)
            entries = await repository.list_recent(limit=limit)
            return tuple(self._to_snapshot(entry) for entry in entries)

    def _build_config_delivery_payload(
        self,
        *,
        target_telegram_user_id: int,
        vpn_client_id: int | None,
        result: ConfigDeliveryResult,
    ) -> dict[str, Any]:
        return {
            "target_telegram_user_id": target_telegram_user_id,
            "vpn_client_id": vpn_client_id,
            "file_count": len(result.files),
            "error_count": len(result.errors),
            "files": [
                {
                    "filename": item.filename,
                    "server_key": item.server_key,
                    "provider_type": item.provider_type.value,
                    "provider_client_id": item.provider_client_id,
                    "display_name": item.display_name,
                }
                for item in result.files
            ],
            "errors": [
                {
                    "server_key": error.server_key,
                    "provider_type": error.provider_type.value,
                    "provider_client_id": error.provider_client_id,
                    "display_name": error.display_name,
                    "message": error.message,
                }
                for error in result.errors
            ],
        }

    def _to_snapshot(self, entry: AdminActionLogORM) -> AdminActionLogSnapshot:
        return AdminActionLogSnapshot(
            id=entry.id,
            admin_telegram_user_id=entry.admin_telegram_user_id,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            payload=dict(entry.payload_json),
            created_at=entry.created_at,
        )
