"""Admin audit log query API (SRS-F-025, TC-AUD-01)."""

from flask import Blueprint, jsonify, request

from src.rbac import admin_required
from src.services.audit_service import get_audit_logs

audit_bp = Blueprint("audit", __name__, url_prefix="/api/admin/audit-log")


@audit_bp.get("")
@admin_required
def list_audit_logs():
    """Retrieve audit log entries (SRS-F-025)."""
    entity = request.args.get("entity")
    action = request.args.get("action")
    search = request.args.get("search") or request.args.get("q")
    user_id = request.args.get("user_id", type=int)
    limit = request.args.get("limit", default=100, type=int)

    if limit < 1 or limit > 500:
        limit = 100

    logs = get_audit_logs(
        limit=limit,
        entity=entity,
        user_id=user_id,
        action=action,
        search=search,
    )
    return jsonify({"audit_log": [log.to_dict() for log in logs]})
