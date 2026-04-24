from app.core.config.models import TelegramConfig
from app.core.permissions import AccessService, UserRole


def test_access_service_resolves_admin_and_user_roles() -> None:
    telegram_config = TelegramConfig(
        token="dummy-token",
        admin_ids=[100, 200],
    )

    service = AccessService(telegram_config)

    assert service.resolve_role(100) == UserRole.ADMIN
    assert service.resolve_role(999) == UserRole.USER
    assert service.is_admin(200) is True
    assert service.is_admin(300) is False
