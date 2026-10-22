"""Unit tests for the audit log service (Issue #6: SRS-F-025, TC-AUD-01)."""

from src.extensions import db
from src.services.audit_service import get_audit_logs, record_audit_log


def test_record_audit_log_creates_entry(app):
    with app.app_context():
        entry = record_audit_log(
            user_id=1,
            action="marks changed",
            entity="marks",
            entity_id="101:5",
            old_value="15",
            new_value="18",
        )
        db.session.commit()

        assert entry.id is not None
        assert entry.action == "marks changed"
        assert entry.old_value == "15"
        assert entry.new_value == "18"
        assert entry.timestamp is not None


def test_get_audit_logs_filters_by_entity_action_and_search(app):
    with app.app_context():
        record_audit_log(1, "marks changed", "marks", "101:1", "12", "16")
        record_audit_log(1, "fee status changed", "fee_status", "1:1", "UNPAID", "PAID")
        record_audit_log(2, "attendance changed", "attendance", "42", "absent", "present")
        db.session.commit()

        all_logs = get_audit_logs()
        assert len(all_logs) == 3

        # Filter by entity
        marks_logs = get_audit_logs(entity="marks")
        assert len(marks_logs) == 1
        assert marks_logs[0].entity == "marks"

        # Filter by user_id
        user2_logs = get_audit_logs(user_id=2)
        assert len(user2_logs) == 1
        assert user2_logs[0].entity == "attendance"

        # Filter by action
        fee_logs = get_audit_logs(action="fee status changed")
        assert len(fee_logs) == 1
        assert fee_logs[0].action == "fee status changed"

        # Search query
        search_logs = get_audit_logs(search="PAID")
        assert len(search_logs) == 1
        assert search_logs[0].entity == "fee_status"
