"""User-admin message bridge handlers."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.context import ApplicationContext
from app.core.permissions import UserRole
from app.infrastructure.logging import get_logger
from app.services.users import TelegramUserSnapshot

router = Router(name="relay")
logger = get_logger(__name__)


def _is_command_message(message: Message) -> bool:
    if message.text is None:
        return False
    entities = message.entities or []
    return any(entity.type == "bot_command" and entity.offset == 0 for entity in entities)


@router.message(F.reply_to_message)
async def relay_admin_reply(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
) -> None:
    if user_role != UserRole.ADMIN:
        return

    bot = message.bot
    if bot is None:
        logger.warning("Admin reply %s has no bot instance", message.message_id)
        return

    relayed = await app_context.message_bridge_service.relay_admin_reply(
        bot=bot,
        message=message,
    )
    if relayed:
        await message.reply("Ответ отправлен пользователю.")


@router.message()
async def forward_user_message(
    message: Message,
    app_context: ApplicationContext,
    user_role: UserRole,
    telegram_user: TelegramUserSnapshot,
) -> None:
    if user_role != UserRole.USER:
        return
    if _is_command_message(message):
        return

    bot = message.bot
    if bot is None:
        logger.warning("User message %s has no bot instance", message.message_id)
        return

    forwarded_count = await app_context.message_bridge_service.forward_user_message(
        bot=bot,
        message=message,
    )
    if forwarded_count == 0:
        logger.warning("No admins configured; message %s was not forwarded", message.message_id)
        await message.reply("Администраторы пока не настроены.")
        return

    await message.reply(
        "Сообщение отправлено администраторам."
        f"\nВаш Telegram ID: <code>{telegram_user.telegram_user_id}</code>"
    )
