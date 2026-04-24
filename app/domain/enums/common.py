"""Common domain enumerations."""

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    BANNED = "banned"
    DELETED = "deleted"


class ClientStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class StatPeriodType(StrEnum):
    RAW = "raw"
    DAILY = "daily"
