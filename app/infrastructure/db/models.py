"""ORM models for the first database iteration."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums.common import ClientStatus, StatPeriodType, UserStatus
from app.infrastructure.db.base import Base, utcnow


class TelegramUserORM(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=UserStatus.ACTIVE.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VpnClientORM(Base):
    __tablename__ = "vpn_clients"
    __table_args__ = (
        UniqueConstraint(
            "server_key",
            "provider_type",
            "provider_client_id",
            name="uq_vpn_client_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    server_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ClientStatus.ACTIVE.value, nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class VpnClientUserLinkORM(Base):
    __tablename__ = "vpn_client_user_links"
    __table_args__ = (
        UniqueConstraint("vpn_client_id", "telegram_user_id", name="uq_vpn_client_user_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vpn_client_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_clients.id"), nullable=False, index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.telegram_user_id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class TrafficStatSampleORM(Base):
    __tablename__ = "traffic_stat_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    rx_bytes_total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes_total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rx_bytes_delta: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes_delta: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(32), default=StatPeriodType.RAW.value, nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )


class TrafficStatDailyORM(Base):
    __tablename__ = "traffic_stat_daily"
    __table_args__ = (
        UniqueConstraint(
            "stat_date",
            "server_key",
            "provider_type",
            "provider_client_id",
            name="uq_traffic_stat_daily_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    server_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class BanRecordORM(Base):
    __tablename__ = "ban_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.telegram_user_id"), nullable=False, index=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BroadcastORM(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by_telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class BroadcastDeliveryORM(Base):
    __tablename__ = "broadcast_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("broadcasts.id"), nullable=False, index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminActionLogORM(Base):
    __tablename__ = "admin_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        "payload", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class MessageLinkORM(Base):
    __tablename__ = "message_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    admin_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
