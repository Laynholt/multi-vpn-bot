"""Provider capability model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Declares provider operations available to higher layers."""

    list_clients: bool = True
    create_client: bool = False
    enable_client: bool = False
    disable_client: bool = False
    delete_client: bool = False
    export_client_config: bool = False
    collect_client_stats: bool = False

    def enabled_names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in (
                "list_clients",
                "create_client",
                "enable_client",
                "disable_client",
                "delete_client",
                "export_client_config",
                "collect_client_stats",
            )
            if bool(getattr(self, name))
        )
