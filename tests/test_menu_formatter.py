from app.bot.formatters import (
    render_admin_config_delivery_result,
    render_config_request_admin_text,
    render_config_request_prompt,
    render_config_request_submitted,
    render_home_text,
)
from app.core.config import load_config
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.core.registry import ServerRegistry
from app.services.config_delivery import (
    ConfigDeliveryError,
    ConfigDeliveryFile,
    ConfigDeliveryResult,
)


def test_render_home_text_includes_role_and_server_count() -> None:
    config = load_config("configs/config.example.json")
    registry = ServerRegistry.from_config(config)

    text = render_home_text(role=UserRole.ADMIN, registry=registry)

    assert "Роль: admin" in text
    assert "Доступных серверов: 1" in text
    assert "Нидерланды" in text


def test_render_config_request_prompt_explains_next_message() -> None:
    text = render_config_request_prompt()

    assert "Запросить конфиг" in text
    assert "следующее сообщение" in text.lower()


def test_render_config_request_submitted_mentions_admins() -> None:
    text = render_config_request_submitted(admin_count=2)

    assert "Заявка отправлена" in text
    assert "2" in text


def test_render_config_request_admin_text_escapes_user_and_comment() -> None:
    text = render_config_request_admin_text(
        telegram_user_id=1001,
        username="<alice>",
        full_name="Alice & Bob",
        comment="<phone & laptop>",
    )

    assert "Заявка на конфиг" in text
    assert "<code>1001</code>" in text
    assert "&lt;alice&gt;" in text
    assert "Alice &amp; Bob" in text
    assert "&lt;phone &amp; laptop&gt;" in text


def test_render_admin_config_delivery_result_summarizes_files_and_errors() -> None:
    text = render_admin_config_delivery_result(
        target_user_id=1001,
        result=ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="alice.conf",
                    content=b"config",
                    server_key="vps<nl>",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice & Phone",
                ),
            ),
            errors=(
                ConfigDeliveryError(
                    server_key="vps-de",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-2",
                    display_name="Bob <Laptop>",
                    message="provider disabled",
                ),
            ),
        ),
    )

    assert "Выдача конфигов" in text
    assert "<code>1001</code>" in text
    assert "Отправлено: 1" in text
    assert "Ошибок: 1" in text
    assert "Alice &amp; Phone" in text
    assert "vps&lt;nl&gt;" in text
    assert "Bob &lt;Laptop&gt;" in text


def test_render_admin_config_delivery_result_handles_empty_result() -> None:
    text = render_admin_config_delivery_result(
        target_user_id=1001,
        result=ConfigDeliveryResult(files=(), errors=()),
    )

    assert "Привязанные VPN-клиенты не найдены." in text
