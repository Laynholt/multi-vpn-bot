from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.config.models import AppConfig
from app.core.executors import CommandResult
from app.core.registry import ServerRegistry
from app.services.host_actions import HostActionRegistry, HostActionsService


class FakeExecutor:
    async def run(self, command, *, timeout_seconds=None, cwd=None, env=None):  # noqa: ANN001
        return CommandResult(
            command=tuple(command),
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_ms=1,
            timed_out=False,
        )


@dataclass
class FakeExecutorFactory:
    executor: FakeExecutor

    def for_server(self, server):  # noqa: ANN001
        return self.executor


def test_host_action_registry_contains_expected_actions() -> None:
    registry = HostActionRegistry()

    assert registry.has("server_status") is True
    assert registry.has("healthcheck") is True
    assert registry.has("missing") is False


@pytest.mark.asyncio
async def test_host_actions_service_runs_enabled_action() -> None:
    config = AppConfig.model_validate(
        {
            "config_version": 1,
            "telegram": {
                "token": "dummy",
                "admin_ids": [1],
                "ui_mode": "inline",
            },
            "servers": [
                {
                    "key": "srv-1",
                    "title": "Server 1",
                    "enabled": True,
                    "connection": {"mode": "local"},
                    "host_actions": {"healthcheck": True},
                    "providers": [],
                }
            ],
        }
    )
    server_registry = ServerRegistry.from_config(config)
    service = HostActionsService(
        server_registry=server_registry,
        executor_factory=FakeExecutorFactory(FakeExecutor()),
        host_action_registry=HostActionRegistry(),
        speedtest_timeout_seconds=180,
    )

    execution = await service.run_action(server_key="srv-1", action_key="healthcheck")

    assert execution.server_key == "srv-1"
    assert execution.action_key == "healthcheck"
    assert execution.result.command == ("hostname",)


@pytest.mark.asyncio
async def test_host_actions_service_lists_enabled_actions_in_registry_order() -> None:
    config = AppConfig.model_validate(
        {
            "config_version": 1,
            "telegram": {
                "token": "dummy",
                "admin_ids": [1],
                "ui_mode": "inline",
            },
            "servers": [
                {
                    "key": "srv-1",
                    "title": "Server 1",
                    "enabled": True,
                    "connection": {"mode": "local"},
                    "host_actions": {
                        "server_status": False,
                        "speedtest": True,
                        "vnstat_week": False,
                        "healthcheck": True,
                    },
                    "providers": [],
                }
            ],
        }
    )
    server_registry = ServerRegistry.from_config(config)
    service = HostActionsService(
        server_registry=server_registry,
        executor_factory=FakeExecutorFactory(FakeExecutor()),
        host_action_registry=HostActionRegistry(),
        speedtest_timeout_seconds=180,
    )

    actions = service.list_enabled_actions("srv-1")

    assert tuple(action.key for action in actions) == ("speedtest", "healthcheck")


@pytest.mark.asyncio
async def test_host_actions_service_rejects_disabled_action() -> None:
    config = AppConfig.model_validate(
        {
            "config_version": 1,
            "telegram": {
                "token": "dummy",
                "admin_ids": [1],
                "ui_mode": "inline",
            },
            "servers": [
                {
                    "key": "srv-1",
                    "title": "Server 1",
                    "enabled": True,
                    "connection": {"mode": "local"},
                    "host_actions": {"healthcheck": False},
                    "providers": [],
                }
            ],
        }
    )
    server_registry = ServerRegistry.from_config(config)
    service = HostActionsService(
        server_registry=server_registry,
        executor_factory=FakeExecutorFactory(FakeExecutor()),
        host_action_registry=HostActionRegistry(),
        speedtest_timeout_seconds=180,
    )

    with pytest.raises(ValueError):
        await service.run_action(server_key="srv-1", action_key="healthcheck")
