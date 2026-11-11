"""Marks entry, validation, grading, and SGPA calculation service (SRS-F-019, SRS-F-020, SRS-F-025).

Handles component marks validation, assigned faculty authorization, student enrollment checks,
ESA registration prerequisites, letter grade/grade point assignment, SGPA calculation,
and atomic audit logging.
"""

from src.extensions import db
from src.models import AuditLog, Enrollment, ExamRegistration, Marks
from src.services.course_service import course_roster, student_for_user
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


def calculate_grade_and_points(total):
    """Compute PES letter grade and grade point from total marks (SRS-F-020, TC-MRK-04).

    Grade Scale:
        90 - 100: S (10)
        80 - 89.x: A (9)
        70 - 79.x: B (8)
        60 - 69.x: C (7)
        50 - 59.x: D (6)
        40 - 49.x: E (5)
        < 40: F (0)
    """
    if total is None:
        return None, None
    cutoffs = (
        (90, "S", 10),
        (80, "A", 9),
        (70, "B", 8),
        (60, "C", 7),
        (50, "D", 6),
        (40, "E", 5),
    )
    for min_mark, grade, points in cutoffs:
        if total >= min_mark:
            return grade, points
    return "F", 0


def calculate_sgpa(records):
    """Calculate SGPA = sum(credits * grade_point) / sum(credits) (SRS-F-020, TC-MRK-05).

    Accepts an iterable of (credits, grade_point) pairs or dicts with 'credits' and 'grade_point'.
    Courses with None grade_point are excluded. F grades (grade_point=0) count in total credits.
    Returns float rounded to 2 decimal places, or None if no graded credits exist.
    """
    total_points = 0.0
    total_credits = 0

    for item in records:
        if isinstance(item, dict):
            creds = item.get("credits", 0)
            gp = item.get("grade_point")
        else:
            creds, gp = item

        if gp is not None and creds:
            total_points += float(creds) * float(gp)
            total_credits += int(creds)

    if total_credits == 0:
        return None

    return round(total_points / total_credits, 2)


def grade_for_marks(mark_rec):
    """Grade and grade point for a marks record, only once all 4 marks are entered (SRS-F-020).

    A course with any mark still missing (e.g. only ISA-1 entered, or no ESA yet)
    gets no grade, so it is not shown as F and does not count in the SGPA.
    """
    if mark_rec is None or any(getattr(mark_rec, comp) is None for comp in MARK_COMPONENTS):
        return None, None
    return calculate_grade_and_points(mark_rec.total)


def get_course_marks(course, user):
    """Return enrolled students with marks, computed grades, and ESA status."""
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
    """Save component marks with validation, auto-grade assignment, and audit logging."""
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
        mark_rec.grade, mark_rec.grade_point = grade_for_marks(mark_rec)
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


def _build_course_result(enrollment, marks_by_course):
    """Format single course result dict and return (result_dict, sgpa_tuple)."""
    course = enrollment.course
    mark_rec = marks_by_course.get(course.id)
    grade, grade_point = grade_for_marks(mark_rec)

    sgpa_item = (course.credits, grade_point) if grade_point is not None else None
    data = {
        "course_id": course.id,
        "code": course.code,
        "name": course.name,
        "credits": course.credits,
        "isa1": mark_rec.isa1 if mark_rec else None,
        "isa2": mark_rec.isa2 if mark_rec else None,
        "assessment": mark_rec.assessment if mark_rec else None,
        "esa": mark_rec.esa if mark_rec else None,
        "total": mark_rec.total if mark_rec else None,
        "grade": grade,
        "grade_point": grade_point,
    }
    return data, sgpa_item


def get_student_results(user):
    """Retrieve enrolled courses, marks, letter grades, and calculated SGPA for student."""
    student = student_for_user(user)
    if student is None:
        return {"courses": [], "sgpa": None, "total_credits": 0, "earned_credits": 0}

    enrollments = sorted(student.enrollments, key=lambda e: e.course.code)
    course_ids = [e.course_id for e in enrollments]

    marks_records = (
        Marks.query.filter(
            Marks.student_id == student.id,
            Marks.course_id.in_(course_ids),
        ).all()
        if course_ids
        else []
    )
    marks_by_course = {m.course_id: m for m in marks_records}

    course_results = []
    sgpa_inputs = []

    for enr in enrollments:
        data, sgpa_item = _build_course_result(enr, marks_by_course)
        course_results.append(data)
        if sgpa_item is not None:
            sgpa_inputs.append(sgpa_item)

    sgpa = calculate_sgpa(sgpa_inputs)
    total_credits = sum(c["credits"] for c in course_results)
    earned_credits = sum(
        c["credits"] for c in course_results if c.get("grade") and c["grade"] != "F"
    )

    return {
        "student": student.to_dict(),
        "courses": course_results,
        "sgpa": sgpa,
        "total_credits": total_credits,
        "earned_credits": earned_credits,
    }
