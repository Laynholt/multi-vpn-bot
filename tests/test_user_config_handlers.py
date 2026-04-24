from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.handlers import navigation
from app.core.config.models import ProviderType
from app.core.permissions import UserRole
from app.services.config_delivery import ConfigDeliveryFile, ConfigDeliveryResult


class FakeCallback:
    pass


@dataclass
class FakeTelegramUser:
    telegram_user_id: int


class FakeConfigDeliveryService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def list_user_config_files(self, *, telegram_user_id: int) -> ConfigDeliveryResult:
        self.calls.append(telegram_user_id)
        return ConfigDeliveryResult(
            files=(
                ConfigDeliveryFile(
                    filename="vps-nl_wireguard_Alice.conf",
                    content=b"[Interface]\nPrivateKey = xxx\n",
                    server_key="vps-nl",
                    provider_type=ProviderType.WIREGUARD,
                    provider_client_id="peer-1",
                    display_name="Alice",
                ),
            ),
            errors=(),
        )


@pytest.mark.asyncio
async def test_open_my_configs_sends_summary_and_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []
    files: list[ConfigDeliveryFile] = []

    async def fake_send_or_edit_text(**kwargs) -> None:  # noqa: ANN003
        sent.append(kwargs)

    async def fake_send_config_files(*, callback, config_files) -> None:  # noqa: ANN001
        assert isinstance(callback, FakeCallback)
        files.extend(config_files)

    monkeypatch.setattr(navigation, "send_or_edit_text", fake_send_or_edit_text)
    monkeypatch.setattr(navigation, "_send_config_files", fake_send_config_files)

    service = FakeConfigDeliveryService()

    await navigation.open_my_configs_section(
        FakeCallback(),
        SimpleNamespace(config_delivery_service=service),
        UserRole.USER,
        FakeTelegramUser(telegram_user_id=1001),
    )

    assert service.calls == [1001]
    assert "Configs ready: 1" in sent[0]["text"]
    assert [item.filename for item in files] == ["vps-nl_wireguard_Alice.conf"]


def test_my_configs_callback_is_short() -> None:
    packed = MenuActionCallback(section=MenuSection.MY_CONFIGS).pack()

    assert packed == "menu:my_configs"
    assert len(packed) < 64
