"""aiogram runtime bootstrap."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.bot.handlers import create_root_router
from app.bot.middlewares import ContextMiddleware, UserSyncMiddleware
from app.context import ApplicationContext
from app.infrastructure.logging import get_logger


def build_dispatcher(*, app_context: ApplicationContext) -> Dispatcher:
    dispatcher = Dispatcher()
    middleware = ContextMiddleware(
        app_context=app_context,
        access_service=app_context.access_service,
    )
    user_sync_middleware = UserSyncMiddleware(
        user_service=app_context.telegram_user_service,
        access_service=app_context.access_service,
    )

    dispatcher.message.middleware(middleware)
    dispatcher.callback_query.middleware(middleware)
    dispatcher.message.middleware(user_sync_middleware)
    dispatcher.callback_query.middleware(user_sync_middleware)
    dispatcher.include_router(create_root_router())
    return dispatcher


async def run_bot(app_context: ApplicationContext) -> None:
    """Start Telegram long polling."""

    logger = get_logger(__name__)
    token = app_context.config.telegram.resolve_token()

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = build_dispatcher(app_context=app_context)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
        ]
    )

    logger.info("Starting Telegram polling")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
