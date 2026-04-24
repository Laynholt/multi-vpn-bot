"""Repository for message link mapping between users and admins."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import MessageLinkORM


class MessageLinkRepository:
    """CRUD helpers for forwarded message relationships."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        telegram_user_id: int,
        user_chat_id: int,
        user_message_id: int,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> MessageLinkORM:
        link = MessageLinkORM(
            telegram_user_id=telegram_user_id,
            user_chat_id=user_chat_id,
            user_message_id=user_message_id,
            admin_chat_id=admin_chat_id,
            admin_message_id=admin_message_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def get_by_admin_message(
        self,
        *,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> MessageLinkORM | None:
        query = select(MessageLinkORM).where(
            MessageLinkORM.admin_chat_id == admin_chat_id,
            MessageLinkORM.admin_message_id == admin_message_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()
