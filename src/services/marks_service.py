"""Marks entry and validation service (SRS-F-019, SRS-F-025, SRS-NF-005).

Handles component marks validation, assigned faculty authorization,
student enrollment checks, ESA registration prerequisites, and atomic audit logging.
"""

from src.extensions import db
from src.models import AuditLog, Enrollment, ExamRegistration, Marks
from src.services.course_service import course_roster
from src.services.seed_service import atomic_transaction
from src.validators import MARK_COMPONENTS, ValidationError, validate_marks_dict


class MarksError(Exception):
    """Marks service error with HTTP status code."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def check_assigned_faculty(course, user):
    """Verify that user is the assigned faculty for the course."""
    if course.faculty_id != user.id:
        raise MarksError("Only the faculty assigned to this course can enter marks.", 403)


def get_course_marks(course, user):
    """Return enrolled students with marks and ESA status."""
    check_assigned_faculty(course, user)
    roster = course_roster(course)

    marks_records = Marks.query.filter_by(course_id=course.id).all()
    marks_by_student = {m.student_id: m for m in marks_records}

    esa_regs = ExamRegistration.query.filter_by(course_id=course.id).all()
    esa_registered_ids = {r.student_id for r in esa_regs}

    students = []
    for s in roster:
        mark_rec = marks_by_student.get(s.id)
        students.append(
            {
                "student_id": s.id,
                "srn": s.srn,
                "name": s.name,
                "is_esa_registered": s.id in esa_registered_ids,
                "isa1": mark_rec.isa1 if mark_rec else None,
                "isa2": mark_rec.isa2 if mark_rec else None,
                "assessment": mark_rec.assessment if mark_rec else None,
                "esa": mark_rec.esa if mark_rec else None,
                "total": mark_rec.total if mark_rec else None,
                "grade": mark_rec.grade if mark_rec else None,
                "grade_point": mark_rec.grade_point if mark_rec else None,
            }
        )

    return {"course": course.to_dict(), "students": students}


def _check_esa_registration(course_id, student_id, validated):
    """Ensure student is registered for ESA if ESA mark is provided."""
    if "esa" in validated and validated["esa"] is not None:
        is_registered = (
            ExamRegistration.query.filter_by(course_id=course_id, student_id=student_id).first()
            is not None
        )
        if not is_registered:
            raise MarksError(
                "Cannot enter ESA marks for a student who is not registered for ESA.", 409
            )


def _compute_total(mark_rec):
    """Compute sum of non-null mark components."""
    comps = [mark_rec.isa1, mark_rec.isa2, mark_rec.assessment, mark_rec.esa]
    valid = [c for c in comps if c is not None]
    return round(sum(valid), 2) if valid else None


def _audit_value(comp, value):
    """Format one mark for the audit log, e.g. 'ISA-1: 15.0' (or 'ISA-1: empty')."""
    shown = "empty" if value is None else str(value)
    return f"{MARK_COMPONENTS[comp]['name']}: {shown}"


def save_student_marks(course, user, student_id, marks_data, before_commit_hook=None):
    """Save component marks with validation and audit logging (SRS-F-019, SRS-F-025)."""
    check_assigned_faculty(course, user)

    enrollment = Enrollment.query.filter_by(course_id=course.id, student_id=student_id).first()
    if enrollment is None:
        raise MarksError(f"Student {student_id} is not enrolled in {course.code}.", 400)

    try:
        validated = validate_marks_dict(marks_data)
    except ValidationError as err:
        raise MarksError(err.message, err.status_code) from err

    _check_esa_registration(course.id, student_id, validated)

    with atomic_transaction():
        mark_rec = Marks.query.filter_by(course_id=course.id, student_id=student_id).first()
        is_new = mark_rec is None

        if is_new:
            mark_rec = Marks(student_id=student_id, course_id=course.id)
            db.session.add(mark_rec)

        changes = []
        for comp in ("isa1", "isa2", "assessment", "esa"):
            if comp in validated:
                old_value = getattr(mark_rec, comp)
                new_value = validated[comp]
                if not is_new and old_value is not None and old_value != new_value:
                    changes.append((comp, old_value, new_value))
                setattr(mark_rec, comp, new_value)

        mark_rec.total = _compute_total(mark_rec)
        db.session.flush()

        # One audit row per changed mark, with that mark's old and new value
        # (SRS-F-025, TC-AUD-01). First-time entries are not "changes".
        for comp, old_value, new_value in changes:
            db.session.add(
                AuditLog(
                    user_id=user.id,
                    action="marks changed",
                    entity="marks",
                    entity_id=f"{course.id}:{student_id}",
                    old_value=_audit_value(comp, old_value),
                    new_value=_audit_value(comp, new_value),
                )
            )

        if before_commit_hook is not None:
            before_commit_hook()

    return mark_rec
