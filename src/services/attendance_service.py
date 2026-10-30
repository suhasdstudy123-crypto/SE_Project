"""Attendance marking, correction, percentage, and shortage calculation (SRS-F-011..F-014).

Every save is one database transaction (SRS-NF-005): the attendance rows and the
audit-log rows for any corrections are written together or not at all.
"""

from datetime import date

from src.extensions import db
from src.models import Attendance, AuditLog, Enrollment
from src.services.course_service import course_roster
from src.services.seed_service import atomic_transaction

SHORTAGE_THRESHOLD = 75.0


class AttendanceError(Exception):
    """An attendance problem, with the HTTP status code the API should return."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def calculate_percentage(attended, held):
    """Compute attendance percentage (SRS-F-013).

    % = (present / held) * 100.
    0 classes held returns 0.0 without division-by-zero error.
    """
    if not held or held <= 0:
        return 0.0
    return round((attended / held) * 100.0, 2)


def is_shortage(percentage, held=None):
    """Return True if attendance percentage is strictly below 75% (SRS-F-014).

    Exactly 75% is not flagged as a shortage.
    0 classes held is not flagged as a shortage.
    """
    if held is not None and held == 0:
        return False
    return percentage < SHORTAGE_THRESHOLD


def course_attendance_summary(course):
    """Return student_id -> {held, attended, percentage, shortage} for enrolled students."""
    roster = course_roster(course)
    records = Attendance.query.filter_by(course_id=course.id).all()
    by_student = {}
    for rec in records:
        by_student.setdefault(rec.student_id, []).append(rec)

    summary = {}
    for student in roster:
        student_records = by_student.get(student.id, [])
        held = len(student_records)
        attended = sum(1 for r in student_records if r.present)
        pct = calculate_percentage(attended, held)
        summary[student.id] = {
            "held": held,
            "attended": attended,
            "percentage": pct,
            "shortage": is_shortage(pct, held),
        }
    return summary


def student_attendance_summary(student):
    """Return attendance summary for every course the student is enrolled in (SRS-F-013, F-014)."""
    courses = sorted(
        (enrollment.course for enrollment in student.enrollments),
        key=lambda c: c.code,
    )
    result = []
    for course in courses:
        records = Attendance.query.filter_by(course_id=course.id, student_id=student.id).all()
        held = len(records)
        attended = sum(1 for r in records if r.present)
        pct = calculate_percentage(attended, held)
        result.append(
            {
                "course_id": course.id,
                "course_code": course.code,
                "course_name": course.name,
                "credits": course.credits,
                "held": held,
                "attended": attended,
                "percentage": pct,
                "shortage": is_shortage(pct, held),
            }
        )
    return result


def student_course_attendance_detail(student, course):
    """Return detailed attendance records for a specific enrolled course."""
    records = (
        Attendance.query.filter_by(course_id=course.id, student_id=student.id)
        .order_by(Attendance.date.desc())
        .all()
    )
    held = len(records)
    attended = sum(1 for r in records if r.present)
    pct = calculate_percentage(attended, held)
    return {
        "course": course.to_dict(),
        "held": held,
        "attended": attended,
        "percentage": pct,
        "shortage": is_shortage(pct, held),
        "records": [{"date": r.date.isoformat(), "present": r.present} for r in records],
    }


def parse_class_date(value, today=None):
    """Turn 'YYYY-MM-DD' into a date. Future dates are rejected (SRS-SR-007).

    `today` can be passed in by tests.
    """
    if not isinstance(value, str):
        raise AttendanceError("Date is required (YYYY-MM-DD).")
    try:
        class_date = date.fromisoformat(value.strip())
    except ValueError as error:
        raise AttendanceError("Date must be a valid date in YYYY-MM-DD format.") from error
    if class_date > (today or date.today()):
        raise AttendanceError("Attendance cannot be marked for a future date.")
    return class_date


def check_assigned_faculty(course, user):
    """Only the faculty member assigned to the course may mark its attendance."""
    if course.faculty_id != user.id:
        raise AttendanceError("Only the faculty assigned to this course can mark attendance.", 403)


def class_attendance(course, class_date):
    """Every enrolled student with their attendance for that date and cumulative attendance %.

    Students without a saved entry are shown as present ('All present' default, SAD 4.5).
    """
    saved = {
        row.student_id: row
        for row in Attendance.query.filter_by(course_id=course.id, date=class_date).all()
    }
    summary = course_attendance_summary(course)
    students = [
        {
            "student_id": student.id,
            "srn": student.srn,
            "name": student.name,
            "present": saved[student.id].present if student.id in saved else True,
            "attended": summary.get(student.id, {}).get("attended", 0),
            "held": summary.get(student.id, {}).get("held", 0),
            "percentage": summary.get(student.id, {}).get("percentage", 0.0),
            "shortage": summary.get(student.id, {}).get("shortage", False),
        }
        for student in course_roster(course)
    ]
    return {"recorded": bool(saved), "students": students}


def _validate_records(course, records):
    """Return {student_id: present}; every student must be enrolled in the course."""
    if not isinstance(records, list) or not records:
        raise AttendanceError("records must be a non-empty list.")

    enrolled = {row.student_id for row in Enrollment.query.filter_by(course_id=course.id).all()}
    cleaned = {}
    for record in records:
        if not isinstance(record, dict):
            raise AttendanceError("Each record needs a student_id and present (true/false).")
        student_id = record.get("student_id")
        present = record.get("present")
        if not isinstance(student_id, int) or isinstance(student_id, bool):
            raise AttendanceError("Each record needs a valid student_id.")
        if not isinstance(present, bool):
            raise AttendanceError("present must be true or false.")
        if student_id not in enrolled:
            raise AttendanceError(f"Student {student_id} is not enrolled in {course.code}.")
        if student_id in cleaned:
            raise AttendanceError(f"Student {student_id} is listed more than once.")
        cleaned[student_id] = present
    return cleaned


def _label(present):
    return "present" if present else "absent"


def save_attendance(course, user, class_date, records, before_commit_hook=None):
    """Create or correct attendance for one class date.

    New entries are inserted. A changed entry is a correction (SRS-F-012) and gets an
    audit-log row with the old and new value. `before_commit_hook` lets tests force an
    error mid-save to prove nothing partial is kept (TC-REL-01).
    Returns (saved_count, corrected_count).
    """
    check_assigned_faculty(course, user)
    cleaned = _validate_records(course, records)

    existing = {
        row.student_id: row
        for row in Attendance.query.filter_by(course_id=course.id, date=class_date).all()
    }
    corrected = 0
    with atomic_transaction():
        for student_id, present in cleaned.items():
            row = existing.get(student_id)
            if row is None:
                db.session.add(
                    Attendance(
                        course_id=course.id,
                        student_id=student_id,
                        date=class_date,
                        present=present,
                    )
                )
                continue
            if row.present == present:
                continue
            db.session.add(
                AuditLog(
                    user_id=user.id,
                    action="attendance changed",
                    entity="attendance",
                    entity_id=str(row.id),
                    old_value=_label(row.present),
                    new_value=_label(present),
                )
            )
            row.present = present
            corrected += 1
        db.session.flush()
        if before_commit_hook is not None:
            before_commit_hook()
    return len(cleaned), corrected
