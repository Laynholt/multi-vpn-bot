"""Telegram bot package."""

from __future__ import annotations

from app.context import ApplicationContext


async def run_bot(app_context: ApplicationContext) -> None:
    from app.bot.runtime import run_bot as _run_bot

    await _run_bot(app_context)


__all__ = ["run_bot"]
