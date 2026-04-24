"""Shared SQLAlchemy base and helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for the project ORM."""
