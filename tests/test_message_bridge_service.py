from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.config.models import TelegramConfig
from app.core.permissions import AccessService
from app.services.messages import MessageBridgeService


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


@dataclass(frozen=True)
class FakeTelegramUser:
    telegram_user_id: int = 1001
    username: str | None = "<alice>"
    first_name: str | None = "Alice"
    last_name: str | None = "& Bob"


@pytest.mark.asyncio
async def test_forward_config_request_sends_escaped_request_to_admins() -> None:
    telegram_config = TelegramConfig(token="dummy", admin_ids=[10, 20])
    service = MessageBridgeService(
        database=None,  # type: ignore[arg-type]
        telegram_config=telegram_config,
        access_service=AccessService(telegram_config),
    )
    bot = FakeBot()

    count = await service.forward_config_request(
        bot=bot,  # type: ignore[arg-type]
        telegram_user=FakeTelegramUser(),  # type: ignore[arg-type]
        comment="<phone & laptop>",
    )

    assert count == 2
    assert [chat_id for chat_id, _text in bot.messages] == [10, 20]
    assert "&lt;phone &amp; laptop&gt;" in bot.messages[0][1]
    assert "&lt;alice&gt;" in bot.messages[0][1]
