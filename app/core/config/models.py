"""Strong application configuration models."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.exceptions import ConfigurationError


class StrictModel(BaseModel):
    """Base Pydantic model with strict schema handling."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ConnectionMode(StrEnum):
    LOCAL = "local"
    SSH = "ssh"


class ProviderType(StrEnum):
    WIREGUARD = "wireguard"
    X3UI = "3xui"


class UiMode(StrEnum):
    INLINE = "inline"


class LoggingConfig(StrictModel):
    logs_dir: Path = Path("stuff/logs")
    base_log_filename: str = "telegram_bot"
    max_log_length: int = Field(default=5000, gt=0)
    level: str = "INFO"

    @model_validator(mode="after")
    def validate_level(self) -> Self:
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if self.level.upper() not in allowed_levels:
            msg = f"Unsupported logging level: {self.level}"
            raise ValueError(msg)
        return self


class TelegramSystemMonitorConfig(StrictModel):
    enabled: bool = False
    interval_seconds: int = Field(default=60, gt=0)
    cpu_threshold_percent: float = Field(default=90.0, ge=0.0, le=100.0)
    cpu_duration_minutes: int = Field(default=3, gt=0)
    ram_threshold_percent: float = Field(default=90.0, ge=0.0, le=100.0)
    ram_duration_minutes: int = Field(default=3, gt=0)


class TelegramConfig(StrictModel):
    token: str | None = None
    token_env: str | None = None
    admin_ids: list[int] = Field(default_factory=list)
    max_concurrent_messages: int = Field(default=5, gt=0)
    max_message_length: int = Field(default=4000, gt=0)
    ui_mode: UiMode = UiMode.INLINE
    system_monitor: TelegramSystemMonitorConfig = Field(default_factory=TelegramSystemMonitorConfig)

    @model_validator(mode="after")
    def validate_token_source(self) -> Self:
        if self.token is None and self.token_env is None:
            raise ValueError("telegram.token or telegram.token_env must be provided")
        if any(admin_id <= 0 for admin_id in self.admin_ids):
            raise ValueError("telegram.admin_ids must contain only positive integers")
        if len(set(self.admin_ids)) != len(self.admin_ids):
            raise ValueError("telegram.admin_ids must be unique")
        return self

    def resolve_token(self) -> str:
        if self.token is not None:
            return self.token
        assert self.token_env is not None
        token = os.getenv(self.token_env)
        if not token:
            raise ConfigurationError(
                f"Environment variable {self.token_env!r} is not set for telegram token"
            )
        return token


class DatabaseConfig(StrictModel):
    sqlite_path: Path = Path("stuff/multivpn.db")


class LocalTransportConfig(StrictModel):
    enabled: bool = True


class SshTransportConfig(StrictModel):
    enabled: bool = True
    use_system_ssh_config: bool = True
    connect_timeout_seconds: int = Field(default=10, gt=0)
    command_timeout_seconds: int = Field(default=30, gt=0)


class TransportsConfig(StrictModel):
    local: LocalTransportConfig = Field(default_factory=LocalTransportConfig)
    ssh: SshTransportConfig = Field(default_factory=SshTransportConfig)


class StatisticsConfig(StrictModel):
    enabled: bool = True
    collect_interval_minutes: int = Field(default=15, gt=0)
    store_raw_samples: bool = True
    daily_rollup_timezone: str = "Europe/Moscow"
    csv_delimiter: str = ","

    @model_validator(mode="after")
    def validate_csv_delimiter(self) -> Self:
        if not self.csv_delimiter:
            raise ValueError("statistics.csv_delimiter must not be empty")
        return self


class ConnectionConfig(StrictModel):
    mode: ConnectionMode
    ssh_alias: str | None = None

    @model_validator(mode="after")
    def validate_connection(self) -> Self:
        if self.mode == ConnectionMode.SSH and not self.ssh_alias:
            raise ValueError("connection.ssh_alias is required when connection.mode is 'ssh'")
        return self


class HostActionsConfig(StrictModel):
    server_status: bool = False
    speedtest: bool = False
    vnstat_week: bool = False
    healthcheck: bool = False


class ProviderConfig(StrictModel):
    type: ProviderType
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


class ServerUiConfig(StrictModel):
    icon: str | None = None
    sort_order: int = 0


class ServerConfig(StrictModel):
    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    enabled: bool = True
    connection: ConnectionConfig
    host_actions: HostActionsConfig = Field(default_factory=HostActionsConfig)
    providers: list[ProviderConfig] = Field(default_factory=list)
    ui: ServerUiConfig = Field(default_factory=ServerUiConfig)
    tags: list[str] = Field(default_factory=list)


class FeaturesConfig(StrictModel):
    broadcasts_enabled: bool = True
    csv_export_enabled: bool = True
    user_config_request_enabled: bool = True


class DefaultsConfig(StrictModel):
    speedtest_timeout_seconds: int = Field(default=180, gt=0)


class AppConfig(StrictModel):
    config_version: int = 1
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    telegram: TelegramConfig
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    transports: TransportsConfig = Field(default_factory=TransportsConfig)
    statistics: StatisticsConfig = Field(default_factory=StatisticsConfig)
    servers: list[ServerConfig] = Field(default_factory=list)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if self.config_version != 1:
            raise ValueError(f"Unsupported config_version: {self.config_version}")

        server_keys = [server.key for server in self.servers]
        if len(set(server_keys)) != len(server_keys):
            raise ValueError("server.key values must be unique")

        disabled_transports: set[ConnectionMode] = set()
        if not self.transports.local.enabled:
            disabled_transports.add(ConnectionMode.LOCAL)
        if not self.transports.ssh.enabled:
            disabled_transports.add(ConnectionMode.SSH)

        for server in self.servers:
            if not server.enabled:
                continue
            if server.connection.mode in disabled_transports:
                msg = (
                    f"Server {server.key!r} uses disabled transport "
                    f"{server.connection.mode.value!r}"
                )
                raise ValueError(msg)

        return self
