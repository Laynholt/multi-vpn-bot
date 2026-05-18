"""Pure enums for admin user management actions."""

from enum import StrEnum


class AdminUserAction(StrEnum):
    OPEN = "open"
    SEND_CONFIGS = "cfg"
    BAN = "ban"
    UNBAN = "unban"
    DELETE = "delete"
