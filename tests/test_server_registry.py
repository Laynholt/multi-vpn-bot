from __future__ import annotations

from app.core.config import load_config
from app.core.registry import ServerRegistry


def test_server_registry_contains_only_enabled_servers() -> None:
    config = load_config("configs/config.example.json")
    registry = ServerRegistry.from_config(config)

    assert len(registry) == 1
    assert registry.get("vps-nl").title == "Нидерланды"
