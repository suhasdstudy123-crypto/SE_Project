"""Dashboard summary APIs for Admin and Faculty (SRS-F-024)."""

from flask import Blueprint, jsonify
from flask_login import current_user

from src.models import Course, FeeState, FeeStatus, Student
from src.rbac import admin_required, faculty_required
from src.services import attendance_service, course_service

dashboard_bp = Blueprint("dashboard", __name__)


def _attendance_shortage_count(courses):
    """Count unique students below 75% in at least one supplied course."""
    students_with_shortage = set()

    for course in courses:
        summary = attendance_service.course_attendance_summary(course)

        for student_id, details in summary.items():
            if details["shortage"]:
                students_with_shortage.add(student_id)

    return len(students_with_shortage)


@dashboard_bp.get("/api/admin/dashboard")
@admin_required
def admin_dashboard():
    """Return institution-wide summary numbers for Admin."""
    courses = Course.query.all()

    fee_defaulters = (
        FeeStatus.query.with_entities(FeeStatus.student_id)
        .filter(FeeStatus.status == FeeState.UNPAID)
        .distinct()
        .count()
    )

    return jsonify(
        {
            "total_students": Student.query.count(),
            "total_courses": len(courses),
            "attendance_shortages": _attendance_shortage_count(courses),
            "fee_defaulters": fee_defaulters,
        }
    )


@dashboard_bp.get("/api/faculty/dashboard")
@faculty_required
def faculty_dashboard():
    """Return summary numbers for the logged-in Faculty member."""
    courses = Course.query.filter_by(faculty_id=current_user.id).all()

    enrolled_student_ids = set()
    for course in courses:
        for student in course_service.course_roster(course):
            enrolled_student_ids.add(student.id)

    return jsonify(
        {
            "total_students": len(enrolled_student_ids),
            "total_courses": len(courses),
            "attendance_shortages": _attendance_shortage_count(courses),
        }
    )
