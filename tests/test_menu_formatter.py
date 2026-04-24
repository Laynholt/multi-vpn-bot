from app.bot.formatters import render_home_text
from app.core.config import load_config
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry


def test_render_home_text_includes_role_and_server_count() -> None:
    config = load_config("configs/config.example.json")
    registry = ServerRegistry.from_config(config)

    text = render_home_text(role=UserRole.ADMIN, registry=registry)

    assert "Роль: admin" in text
    assert "Доступных серверов: 1" in text
    assert "Нидерланды" in text
