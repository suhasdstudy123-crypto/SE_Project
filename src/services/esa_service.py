"""ESA registration window, eligibility, registration and override rules.

EligibilityService + ExamRegModule in the SAD (SRS-F-016, F-017, F-018, F-026).

BR-1: a student is eligible for a course's ESA if fees for their semester are PAID
      AND attendance in that course is >= 75%, OR an Admin override exists.
BR-2: ESA registration and drop are allowed only while the registration window is open.
"""

from src.extensions import db
from src.models import (
    Attendance,
    EligibilityOverride,
    Enrollment,
    ExamRegistration,
    ExamWindow,
    FeeState,
    FeeStatus,
    Marks,
    Student,
)
from src.models.user import utc_now
from src.services.attendance_service import SHORTAGE_THRESHOLD, calculate_percentage, is_shortage
from src.services.audit_service import record_audit_log
from src.services.course_service import get_course
from src.services.seed_service import atomic_transaction

MAX_REASON_LENGTH = 255

FEES_UNPAID = "fees_unpaid"
ATTENDANCE_SHORTAGE = "attendance_shortage"
WINDOW_CLOSED = "window_closed"


class EsaError(Exception):
    """An ESA problem, with the HTTP status code and an optional machine-readable reason."""

    def __init__(self, message, status_code=400, reason=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.reason = reason


# ---------------------------------------------------------------- window (F-016)


def window_is_open():
    """True while the Admin has the ESA registration window open."""
    window = ExamWindow.query.order_by(ExamWindow.id).first()
    return bool(window and window.is_open)


def window_state():
    """The window as JSON: {is_open, opened_at, closed_at}."""
    window = ExamWindow.query.order_by(ExamWindow.id).first()
    if window is None:
        return {"is_open": False, "opened_at": None, "closed_at": None}
    data = window.to_dict()
    data.pop("id")
    return data


def set_window(is_open):
    """Open or close the registration window (there is only one window row)."""
    if not isinstance(is_open, bool):
        raise EsaError("open must be true or false.")
    with atomic_transaction():
        window = ExamWindow.query.order_by(ExamWindow.id).first()
        if window is None:
            window = ExamWindow(is_open=False)
            db.session.add(window)
        if window.is_open != is_open:
            window.is_open = is_open
            if is_open:
                window.opened_at = utc_now()
            else:
                window.closed_at = utc_now()
    return window_state()


def _require_open_window():
    if not window_is_open():
        raise EsaError("ESA registration window is closed.", 403, WINDOW_CLOSED)


# ---------------------------------------------------------------- eligibility (F-018, F-026)


def blocking_reasons(fees_paid, percentage, held):
    """BR-1 without overrides: list of (code, message) that block registration.

    Exactly 75.00% is allowed. A course with no classes held yet is not a shortage
    (same rule as the attendance shortage flag, SRS-F-014).
    """
    reasons = []
    if not fees_paid:
        reasons.append((FEES_UNPAID, "Fees unpaid"))
    if is_shortage(percentage, held):
        reasons.append(
            (
                ATTENDANCE_SHORTAGE,
                f"Attendance {percentage:g}% < {SHORTAGE_THRESHOLD:g}%",
            )
        )
    return reasons


def _fees_paid(student):
    fee = FeeStatus.query.filter_by(student_id=student.id, semester=student.semester).first()
    return fee is not None and fee.status == FeeState.PAID


def _attendance(student, course):
    rows = Attendance.query.filter_by(student_id=student.id, course_id=course.id).all()
    held = len(rows)
    attended = sum(1 for row in rows if row.present)
    return held, attended, calculate_percentage(attended, held)


def check_eligibility(student, course):
    """Eligibility of one student for one course's ESA, with the exact reason if blocked."""
    fees_paid = _fees_paid(student)
    held, attended, percentage = _attendance(student, course)
    override = EligibilityOverride.query.filter_by(
        student_id=student.id, course_id=course.id
    ).first()
    reasons = blocking_reasons(fees_paid, percentage, held)
    return {
        "eligible": not reasons or override is not None,
        "reasons": [message for _, message in reasons],
        "reason_codes": [code for code, _ in reasons],
        "fees_paid": fees_paid,
        "held": held,
        "attended": attended,
        "percentage": percentage,
        "override": (
            {"reason": override.reason, "created_at": override.to_dict()["created_at"]}
            if override
            else None
        ),
    }


def _is_registered(student, course):
    return (
        ExamRegistration.query.filter_by(student_id=student.id, course_id=course.id).first()
        is not None
    )


def _require_enrollment(student, course):
    enrolled = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if enrolled is None:
        raise EsaError(f"{student.srn} is not enrolled in {course.code}.", 404)


# ---------------------------------------------------------------- student view and actions (F-017)


def student_overview(student):
    """Window state plus every enrolled course with its eligibility and registration."""
    courses = sorted(
        (enrollment.course for enrollment in student.enrollments), key=lambda c: c.code
    )
    return {
        "window": window_state(),
        "courses": [
            {
                "course_id": course.id,
                "course_code": course.code,
                "course_name": course.name,
                "credits": course.credits,
                "registered": _is_registered(student, course),
                **check_eligibility(student, course),
            }
            for course in courses
        ],
    }


def _course_id(course_id):
    if not isinstance(course_id, int) or isinstance(course_id, bool):
        raise EsaError("A valid course_id is required.")
    return get_course(course_id)


def register(student, course_id):
    """Register the student for a course's ESA (window open, enrolled, eligible, not yet)."""
    _require_open_window()
    course = _course_id(course_id)
    _require_enrollment(student, course)
    if _is_registered(student, course):
        raise EsaError(f"You are already registered for the {course.code} ESA.", 409)

    eligibility = check_eligibility(student, course)
    if not eligibility["eligible"]:
        raise EsaError(
            f"Not eligible for the {course.code} ESA: {'; '.join(eligibility['reasons'])}.",
            403,
            eligibility["reason_codes"][0],
        )

    with atomic_transaction():
        db.session.add(ExamRegistration(student_id=student.id, course_id=course.id))
    return course


def drop(student, course_id):
    """Drop a registered ESA while the window is open (not once ESA marks exist)."""
    _require_open_window()
    course = _course_id(course_id)
    registration = ExamRegistration.query.filter_by(
        student_id=student.id, course_id=course.id
    ).first()
    if registration is None:
        raise EsaError(f"You are not registered for the {course.code} ESA.", 404)

    marks = Marks.query.filter_by(student_id=student.id, course_id=course.id).first()
    if marks is not None and marks.esa is not None:
        raise EsaError(
            f"ESA marks are already entered for {course.code}; it cannot be dropped.", 409
        )

    with atomic_transaction():
        db.session.delete(registration)
    return course


# ---------------------------------------------------------------- admin (F-018 view, F-026)


def course_eligibility(course_id):
    """Every enrolled student of a course with eligibility, override and registration."""
    course = get_course(course_id)
    students = (
        Student.query.join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.course_id == course.id)
        .order_by(Student.srn)
        .all()
    )
    return {
        "course": course.to_dict(),
        "students": [
            {
                "student_id": student.id,
                "srn": student.srn,
                "name": student.name,
                "semester": student.semester,
                "registered": _is_registered(student, course),
                **check_eligibility(student, course),
            }
            for student in students
        ],
    }


def create_override(admin, data):
    """Admin override with a mandatory reason; audit-logged in the same transaction (F-025)."""
    if not isinstance(data, dict):
        raise EsaError("A JSON object is required.")
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise EsaError("A reason is required for an eligibility override.")
    reason = reason.strip()
    if len(reason) > MAX_REASON_LENGTH:
        raise EsaError(f"Reason must be at most {MAX_REASON_LENGTH} characters.")

    student_id = data.get("student_id")
    if not isinstance(student_id, int) or isinstance(student_id, bool):
        raise EsaError("A valid student_id is required.")
    student = db.session.get(Student, student_id)
    if student is None:
        raise EsaError("Student not found.", 404)
    course = _course_id(data.get("course_id"))
    _require_enrollment(student, course)

    existing = EligibilityOverride.query.filter_by(
        student_id=student.id, course_id=course.id
    ).first()
    if existing:
        raise EsaError(f"{student.srn} already has an override for {course.code}.", 409)

    override = EligibilityOverride(
        student_id=student.id, course_id=course.id, reason=reason, admin_id=admin.id
    )
    with atomic_transaction():
        db.session.add(override)
        db.session.flush()
        record_audit_log(
            admin.id,
            "eligibility override",
            "eligibility_override",
            override.id,
            old_value="not eligible",
            new_value=f"eligible for {course.code} ESA ({student.srn}): {reason}",
        )
    return override
