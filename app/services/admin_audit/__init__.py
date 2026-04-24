"""Service for explicit admin action audit records."""

from app.services.admin_audit.service import AdminActionLogSnapshot, AdminAuditService

__all__ = ["AdminActionLogSnapshot", "AdminAuditService"]
