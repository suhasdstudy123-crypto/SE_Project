"""Unit tests for ESA eligibility, window and override rules (Issues #17, #19, #20)."""

from datetime import date, timedelta

import pytest

from src.extensions import db
from src.models import (
    Attendance,
    AuditLog,
    Course,
    Department,
    EligibilityOverride,
    Enrollment,
    ExamRegistration,
    ExamWindow,
    FeeStatus,
    Marks,
    Section,
    Student,
)
from src.services import esa_service
from src.services.auth_service import create_user
from src.services.esa_service import EsaError, blocking_reasons
from tests.conftest import TEST_PASSWORD


def add_attendance(student, course, held, attended):
    """Add `held` classes for the student in the course, `attended` of them present."""
    start = date(2026, 8, 1)
    for day in range(held):
        db.session.add(
            Attendance(
                student_id=student.id,
                course_id=course.id,
                date=start + timedelta(days=day),
                present=day < attended,
            )
        )
    db.session.commit()


def set_fees(student, status):
    """Record the student's fee status for their current semester."""
    db.session.add(FeeStatus(student_id=student.id, semester=student.semester, status=status))
    db.session.commit()


@pytest.fixture
def ctx(app):
    """App context with an admin, a course and one enrolled student."""
    with app.app_context():
        admin = create_user("admin@pes.edu", "Admin", TEST_PASSWORD, "admin")
        department = Department(name="CSE-AIML")
        db.session.add(department)
        db.session.flush()
        section = Section(name="H", department_id=department.id)
        db.session.add(section)
        db.session.flush()
        course = Course(code="UE24AM241A", name="SE", credits=4, department_id=department.id)
        student = Student(
            srn="PES1UG24AM001",
            name="Student 01",
            email="s1@pes.edu",
            semester=4,
            department_id=department.id,
            section_id=section.id,
        )
        db.session.add_all([course, student])
        db.session.flush()
        db.session.add(Enrollment(student_id=student.id, course_id=course.id))
        db.session.add(ExamWindow(is_open=True))
        db.session.commit()
        yield {"admin": admin, "course": course, "student": student}


# ---------------------------------------------------------------- BR-1 boundaries


def test_tc_esa_04_fees_unpaid_blocks_even_with_90_percent():
    """TC-ESA-04: fees Unpaid, attendance 90% -> not eligible, reason 'fees unpaid'."""
    assert blocking_reasons(False, 90.0, 20) == [("fees_unpaid", "Fees unpaid")]


def test_tc_esa_05_attendance_70_percent_blocks():
    """TC-ESA-05: fees Paid, attendance 70% -> not eligible, reason 'attendance shortage'."""
    assert blocking_reasons(True, 70.0, 20) == [("attendance_shortage", "Attendance 70% < 75%")]


def test_tc_esa_06_attendance_exactly_75_percent_is_eligible():
    """TC-ESA-06: fees Paid, attendance exactly 75.00% -> eligible (boundary value)."""
    assert not blocking_reasons(True, 75.0, 20)


def test_attendance_74_99_percent_is_blocked():
    """Boundary: 74.99% is a shortage (SRS 6: 74.99% vs 75.00%)."""
    assert blocking_reasons(True, 74.99, 10000) == [
        ("attendance_shortage", "Attendance 74.99% < 75%")
    ]


def test_both_reasons_are_reported():
    """Unpaid fees and a shortage are both shown to the student."""
    codes = [code for code, _ in blocking_reasons(False, 50.0, 4)]
    assert codes == ["fees_unpaid", "attendance_shortage"]


def test_no_classes_held_is_not_a_shortage():
    """No classes yet is not a shortage (same rule as the shortage flag, F-014)."""
    assert not blocking_reasons(True, 0.0, 0)


# ---------------------------------------------------------------- check_eligibility on real rows


def test_check_eligibility_reads_fees_and_attendance(ctx):
    """Paid fees and 15/20 (75%) attendance make the student eligible."""
    set_fees(ctx["student"], "PAID")
    add_attendance(ctx["student"], ctx["course"], held=20, attended=15)
    result = esa_service.check_eligibility(ctx["student"], ctx["course"])
    assert result["eligible"] is True
    assert (result["held"], result["attended"], result["percentage"]) == (20, 15, 75.0)
    assert result["reasons"] == []
    assert result["override"] is None


def test_missing_fee_record_counts_as_unpaid(ctx):
    """No fee status for the student's semester means fees are not paid."""
    add_attendance(ctx["student"], ctx["course"], held=10, attended=10)
    result = esa_service.check_eligibility(ctx["student"], ctx["course"])
    assert result["eligible"] is False
    assert result["reasons"] == ["Fees unpaid"]


def test_fees_for_another_semester_do_not_count(ctx):
    """Only the fee status of the student's current semester matters."""
    db.session.add(FeeStatus(student_id=ctx["student"].id, semester=3, status="PAID"))
    db.session.commit()
    assert esa_service.check_eligibility(ctx["student"], ctx["course"])["fees_paid"] is False


# ---------------------------------------------------------------- window (TC-ESA-01)


def test_window_open_close_and_timestamps(ctx):  # pylint: disable=unused-argument
    """Closing sets closed_at; reopening sets opened_at; a bad value is rejected."""
    closed = esa_service.set_window(False)
    assert closed["is_open"] is False and closed["closed_at"] is not None
    assert esa_service.window_is_open() is False

    opened = esa_service.set_window(True)
    assert opened["is_open"] is True and opened["opened_at"] is not None

    with pytest.raises(EsaError):
        esa_service.set_window("yes")


def test_window_is_created_when_missing(app):
    """With no window row the window counts as closed; opening it creates the row."""
    with app.app_context():
        assert esa_service.window_state()["is_open"] is False
        esa_service.set_window(True)
        assert ExamWindow.query.count() == 1
        assert esa_service.window_is_open() is True


def test_tc_esa_01_register_rejected_while_window_closed(ctx):
    """TC-ESA-01 (unit): an eligible student cannot register while the window is closed."""
    set_fees(ctx["student"], "PAID")
    esa_service.set_window(False)
    with pytest.raises(EsaError) as error:
        esa_service.register(ctx["student"], ctx["course"].id)
    assert (error.value.status_code, error.value.reason) == (403, "window_closed")

    esa_service.set_window(True)
    esa_service.register(ctx["student"], ctx["course"].id)
    assert ExamRegistration.query.count() == 1


# ---------------------------------------------------------------- register / drop


def test_register_blocked_with_reason_code(ctx):
    """An ineligible student gets HTTP 403 with the exact reason."""
    set_fees(ctx["student"], "PAID")
    add_attendance(ctx["student"], ctx["course"], held=10, attended=7)
    with pytest.raises(EsaError) as error:
        esa_service.register(ctx["student"], ctx["course"].id)
    assert error.value.status_code == 403
    assert error.value.reason == "attendance_shortage"
    assert "Attendance 70% < 75%" in error.value.message
    assert ExamRegistration.query.count() == 0


def test_cannot_drop_after_esa_marks_are_entered(ctx):
    """Dropping is refused once ESA marks exist for the course."""
    set_fees(ctx["student"], "PAID")
    esa_service.register(ctx["student"], ctx["course"].id)
    db.session.add(Marks(student_id=ctx["student"].id, course_id=ctx["course"].id, esa=40))
    db.session.commit()
    with pytest.raises(EsaError) as error:
        esa_service.drop(ctx["student"], ctx["course"].id)
    assert error.value.status_code == 409
    assert ExamRegistration.query.count() == 1


@pytest.mark.parametrize("course_id", [None, "1", True])
def test_invalid_course_id_is_rejected(ctx, course_id):
    """course_id must be an integer."""
    with pytest.raises(EsaError) as error:
        esa_service.register(ctx["student"], course_id)
    assert error.value.status_code == 400


# ---------------------------------------------------------------- override (TC-ESA-07)


def test_tc_esa_07_override_makes_student_eligible_and_is_audited(ctx):
    """TC-ESA-07 (unit): with a reason, the 70% student becomes eligible; an audit row is added."""
    set_fees(ctx["student"], "PAID")
    add_attendance(ctx["student"], ctx["course"], held=10, attended=7)
    data = {
        "student_id": ctx["student"].id,
        "course_id": ctx["course"].id,
        "reason": "  Medical certificate  ",
    }
    override = esa_service.create_override(ctx["admin"], data)
    assert override.reason == "Medical certificate"

    result = esa_service.check_eligibility(ctx["student"], ctx["course"])
    assert result["eligible"] is True
    assert result["reasons"] == ["Attendance 70% < 75%"]
    assert result["override"]["reason"] == "Medical certificate"

    audit = AuditLog.query.filter_by(entity="eligibility_override").one()
    assert audit.user_id == ctx["admin"].id
    assert audit.entity_id == str(override.id)
    assert "Medical certificate" in audit.new_value


@pytest.mark.parametrize("reason", [None, "", "   ", 5, "x" * 256])
def test_override_needs_a_valid_reason(ctx, reason):
    """Override without a (valid) reason is rejected and nothing is saved."""
    data = {"student_id": ctx["student"].id, "course_id": ctx["course"].id, "reason": reason}
    with pytest.raises(EsaError) as error:
        esa_service.create_override(ctx["admin"], data)
    assert error.value.status_code == 400
    assert EligibilityOverride.query.count() == 0
    assert AuditLog.query.count() == 0


def test_override_rejects_duplicates_and_unknown_students(ctx):
    """A second override is a 409; unknown or non-enrolled students are 404s."""
    data = {"student_id": ctx["student"].id, "course_id": ctx["course"].id, "reason": "Medical"}
    esa_service.create_override(ctx["admin"], data)
    with pytest.raises(EsaError) as error:
        esa_service.create_override(ctx["admin"], data)
    assert error.value.status_code == 409

    with pytest.raises(EsaError) as error:
        esa_service.create_override(ctx["admin"], {**data, "student_id": 9999})
    assert error.value.status_code == 404

    with pytest.raises(EsaError) as error:
        esa_service.create_override(ctx["admin"], {**data, "student_id": "1"})
    assert error.value.status_code == 400

    with pytest.raises(EsaError):
        esa_service.create_override(ctx["admin"], ["not", "a", "dict"])
