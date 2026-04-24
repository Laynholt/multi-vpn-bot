"""Registry of supported host/system actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HostActionDefinition:
    """Metadata for a built-in host action."""

    key: str
    title: str
    command: tuple[str, ...]


class HostActionRegistry:
    """Read-only registry of built-in host actions."""

    def __init__(self) -> None:
        self._actions = {
            "server_status": HostActionDefinition(
                key="server_status",
                title="Server Status",
                command=("uname", "-a"),
            ),
            "speedtest": HostActionDefinition(
                key="speedtest",
                title="Speedtest",
                command=("speedtest", "--accept-license", "--accept-gdpr"),
            ),
            "vnstat_week": HostActionDefinition(
                key="vnstat_week",
                title="VNStat Week",
                command=("vnstat", "-w"),
            ),
            "healthcheck": HostActionDefinition(
                key="healthcheck",
                title="Healthcheck",
                command=("hostname",),
            ),
        }

    def get(self, key: str) -> HostActionDefinition:
        return self._actions[key]

    def has(self, key: str) -> bool:
        return key in self._actions

    def list_keys(self) -> tuple[str, ...]:
        return tuple(self._actions)
