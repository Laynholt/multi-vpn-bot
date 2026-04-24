"""Async database manager."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.models import DatabaseConfig
from app.infrastructure.db import models as _models  # noqa: F401
from app.infrastructure.db.base import Base


class DatabaseManager:
    """Creates the async SQLite engine and manages sessions."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database engine is not initialized")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Database session factory is not initialized")
        return self._session_factory

    async def initialize(self) -> None:
        sqlite_path = self._config.sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        database_url = f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
