from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import load_config
from app.core.exceptions import ConfigurationError


def test_load_example_config(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    source_path = Path(__file__).resolve().parents[1] / "configs" / "config.example.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    config_path.write_text(json.dumps(source), encoding="utf-8")

    config = load_config(config_path)

    assert config.config_version == 1
    assert len(config.servers) == 1
    assert config.servers[0].key == "vps-nl"


def test_duplicate_server_keys_raise_configuration_error(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_data = {
        "config_version": 1,
        "telegram": {"token_env": "TELEGRAM_BOT_TOKEN", "admin_ids": [1], "ui_mode": "inline"},
        "servers": [
            {
                "key": "same",
                "title": "One",
                "enabled": True,
                "connection": {"mode": "local"},
                "providers": [],
            },
            {
                "key": "same",
                "title": "Two",
                "enabled": True,
                "connection": {"mode": "local"},
                "providers": [],
            },
        ],
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_config(config_path)
