"""Configuration loading helpers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.core.config.models import AppConfig
from app.core.exceptions import ConfigurationError


def load_config(path: str | Path) -> AppConfig:
    """Load and validate an application config from JSON."""

    config_path = Path(path)

    try:
        raw_data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Config file {config_path} contains invalid JSON: {exc}") from exc

    try:
        return AppConfig.model_validate(raw_data)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid application config: {exc}") from exc
