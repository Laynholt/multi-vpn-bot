from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.bot.callbacks import MenuActionCallback, MenuSection
from app.bot.handlers import navigation
from app.bot.states import ConfigRequestStates
from app.core.permissions import UserRole


class FakeCallback:
    pass


class FakeState:
    def __init__(self) -> None:
        self.state: object | None = None
        self.clear_count = 0

    async def set_state(self, state: object) -> None:
        self.state = state

    async def clear(self) -> None:
        self.clear_count += 1
        self.state = None


class FakeMessage:
    def __init__(self, *, text: str | None = None, bot: object | None = object()) -> None:
        self.text = text
        self.caption: str | None = None
        self.bot = bot
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs: object) -> None:
        self.answers.append(text)


@dataclass(frozen=True)
class FakeTelegramUser:
    telegram_user_id: int
    username: str | None = None
    first_name: str | None = "Alice"
    last_name: str | None = None


class FakeMessageBridgeService:
    def __init__(self, *, forwarded_count: int = 1) -> None:
        self.forwarded_count = forwarded_count
        self.calls: list[dict[str, object]] = []

    async def forward_config_request(
        self,
        *,
        bot: object,
        telegram_user: FakeTelegramUser,
        comment: str,
    ) -> int:
        self.calls.append(
            {
                "bot": bot,
                "telegram_user": telegram_user,
                "comment": comment,
            }
        )
        return self.forwarded_count


@pytest.mark.asyncio
async def test_open_config_request_sets_fsm_and_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def fake_send_or_edit_text(**kwargs: object) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(navigation, "send_or_edit_text", fake_send_or_edit_text)

    state = FakeState()
    await navigation.open_config_request_section(FakeCallback(), state)

    assert state.state == ConfigRequestStates.waiting_for_comment
    assert "Запросить конфиг" in str(sent[0]["text"])
    assert "следующее сообщение" in str(sent[0]["text"]).lower()


@pytest.mark.asyncio
async def test_submit_config_request_forwards_comment_and_clears_state() -> None:
    bridge = FakeMessageBridgeService()
    state = FakeState()
    message = FakeMessage(text="Нужен конфиг для телефона")
    telegram_user = FakeTelegramUser(telegram_user_id=1001)

    await navigation.submit_config_request_comment(
        message,
        state,
        SimpleNamespace(message_bridge_service=bridge),
        UserRole.USER,
        telegram_user,
    )

    assert bridge.calls == [
        {
            "bot": message.bot,
            "telegram_user": telegram_user,
            "comment": "Нужен конфиг для телефона",
        }
    ]
    assert state.clear_count == 1
    assert "Заявка отправлена" in message.answers[0]


@pytest.mark.asyncio
async def test_submit_config_request_reports_missing_admins() -> None:
    bridge = FakeMessageBridgeService(forwarded_count=0)
    state = FakeState()
    message = FakeMessage(text="Нужен конфиг")

    await navigation.submit_config_request_comment(
        message,
        state,
        SimpleNamespace(message_bridge_service=bridge),
        UserRole.USER,
        FakeTelegramUser(telegram_user_id=1001),
    )

    assert state.clear_count == 1
    assert "Администраторы пока не настроены" in message.answers[0]


def test_request_config_callback_is_short() -> None:
    packed = MenuActionCallback(section=MenuSection.REQUEST_CONFIG).pack()

    assert packed == "menu:request_config"
    assert len(packed) < 64
