"""Audit log service for recording and retrieving audit trails (SRS-F-025, TC-AUD-01).

Records changes to marks, attendance, fee statuses, and eligibility overrides.
Provides filtering and query access for the Admin audit dashboard.
"""

from src.extensions import db
from src.models.audit import AuditLog


def record_audit_log(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    user_id, action, entity, entity_id, old_value=None, new_value=None
):
    """Record an immutable audit trail entry."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
    )
    db.session.add(entry)
    return entry


def get_audit_logs(limit=100, entity=None, user_id=None, action=None, search=None):
    """Retrieve audit log entries, latest first, with optional filters."""
    query = AuditLog.query

    if entity:
        query = query.filter(AuditLog.entity == entity)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            db.or_(
                AuditLog.action.ilike(search_term),
                AuditLog.entity.ilike(search_term),
                AuditLog.entity_id.ilike(search_term),
                AuditLog.old_value.ilike(search_term),
                AuditLog.new_value.ilike(search_term),
            )
        )

    return query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit).all()
