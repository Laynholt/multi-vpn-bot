"""Bidirectional user-admin message bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.types import Message

from app.bot.formatters import render_config_request_admin_text
from app.core.config.models import TelegramConfig
from app.core.permissions import AccessService
from app.infrastructure.db import DatabaseManager
from app.infrastructure.db.repositories import MessageLinkRepository
from app.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from app.services.users import TelegramUserSnapshot


class MessageBridgeService:
    """Forwards user messages to admins and relays admin replies back to users."""

    def __init__(
        self,
        *,
        database: DatabaseManager,
        telegram_config: TelegramConfig,
        access_service: AccessService,
    ) -> None:
        self._database = database
        self._admin_ids = tuple(telegram_config.admin_ids)
        self._access_service = access_service
        self._logger = get_logger(__name__)

    async def forward_user_message(self, *, bot: Bot, message: Message) -> int:
        if message.from_user is None:
            return 0

        forwarded_count = 0
        admin_label = self._format_user_label(message)
        caption_prefix = f"Сообщение от {admin_label}"

        for admin_id in self._admin_ids:
            header = await bot.send_message(admin_id, caption_prefix)
            copied_message = await message.copy_to(chat_id=admin_id)
            async with self._database.session() as session:
                repository = MessageLinkRepository(session)
                await repository.create(
                    telegram_user_id=message.from_user.id,
                    user_chat_id=message.chat.id,
                    user_message_id=message.message_id,
                    admin_chat_id=admin_id,
                    admin_message_id=copied_message.message_id,
                )
                await repository.create(
                    telegram_user_id=message.from_user.id,
                    user_chat_id=message.chat.id,
                    user_message_id=message.message_id,
                    admin_chat_id=admin_id,
                    admin_message_id=header.message_id,
                )
            forwarded_count += 1

        self._logger.info(
            "Forwarded message %s from user %s to %s admins",
            message.message_id,
            message.from_user.id,
            forwarded_count,
        )
        return forwarded_count

    async def forward_config_request(
        self,
        *,
        bot: Bot,
        telegram_user: TelegramUserSnapshot,
        comment: str,
    ) -> int:
        full_name = " ".join(
            part
            for part in (telegram_user.first_name, telegram_user.last_name)
            if part
        )
        text = render_config_request_admin_text(
            telegram_user_id=telegram_user.telegram_user_id,
            username=telegram_user.username,
            full_name=full_name or None,
            comment=comment,
        )

        forwarded_count = 0
        for admin_id in self._admin_ids:
            await bot.send_message(admin_id, text)
            forwarded_count += 1

        self._logger.info(
            "Forwarded config request from user %s to %s admins",
            telegram_user.telegram_user_id,
            forwarded_count,
        )
        return forwarded_count

    async def relay_admin_reply(self, *, bot: Bot, message: Message) -> bool:
        reply_to_message = message.reply_to_message
        if reply_to_message is None:
            return False
        if message.from_user is None:
            return False
        if not self._access_service.is_admin(message.from_user.id):
            return False

        async with self._database.session() as session:
            repository = MessageLinkRepository(session)
            link = await repository.get_by_admin_message(
                admin_chat_id=message.chat.id,
                admin_message_id=reply_to_message.message_id,
            )

        if link is None:
            return False

        await message.copy_to(chat_id=link.user_chat_id)
        self._logger.info(
            "Relayed admin reply %s from admin %s to user %s",
            message.message_id,
            message.from_user.id,
            link.telegram_user_id,
        )
        return True

    def _format_user_label(self, message: Message) -> str:
        assert message.from_user is not None
        parts = [message.from_user.full_name, f"(id={message.from_user.id})"]
        if message.from_user.username:
            parts.append(f"@{message.from_user.username}")
        return " ".join(parts)
