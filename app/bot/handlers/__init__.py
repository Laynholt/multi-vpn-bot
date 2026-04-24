"""Telegram routers."""

from aiogram import Router

from app.bot.handlers.admin_users import router as admin_users_router
from app.bot.handlers.navigation import router as navigation_router
from app.bot.handlers.relay import router as relay_router
from app.bot.handlers.servers import router as servers_router
from app.bot.handlers.start import router as start_router


def create_root_router() -> Router:
    router = Router(name="root")
    router.include_router(start_router)
    router.include_router(admin_users_router)
    router.include_router(servers_router)
    router.include_router(navigation_router)
    router.include_router(relay_router)
    return router
