"""CSV report downloads for Admin and Faculty (SRS-F-023, Issue #23).

Routes only check access and build the response; the report rows come
from src/services/report_service.py (layered architecture, SAD Report service).
"""

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user

from src.extensions import db
from src.models import Course
from src.rbac import admin_required, faculty_required
from src.services import report_service

reports_bp = Blueprint("reports", __name__)


def csv_download(headers, rows, filename):
    """Send rows as a downloadable CSV file."""
    return Response(
        report_service.to_csv(headers, rows),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _course_from_query():
    """Return (course, None) or (None, error response) for ?course_id=."""
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return None, (jsonify({"error": "course_id is required."}), 400)
    course = db.session.get(Course, course_id)
    if course is None:
        return None, (jsonify({"error": "Course not found."}), 404)
    return course, None


def _attendance_download(course):
    return csv_download(
        report_service.ATTENDANCE_HEADERS,
        report_service.attendance_rows(course),
        f"attendance_{course.code}.csv",
    )


@reports_bp.get("/api/admin/reports/students.csv")
@admin_required
def export_students():
    """Admin: all student records."""
    return csv_download(
        report_service.STUDENT_HEADERS, report_service.student_rows(), "students.csv"
    )


@reports_bp.get("/api/admin/reports/attendance.csv")
@admin_required
def export_admin_attendance():
    """Admin: attendance report for any course."""
    course, error = _course_from_query()
    if error:
        return error
    return _attendance_download(course)


@reports_bp.get("/api/faculty/reports/attendance.csv")
@faculty_required
def export_faculty_attendance():
    """Faculty: attendance report for a course assigned to them."""
    course, error = _course_from_query()
    if error:
        return error
    if course.faculty_id != current_user.id:
        return jsonify({"error": "You are not assigned to this course."}), 403
    return _attendance_download(course)


@reports_bp.get("/api/admin/reports/results.csv")
@admin_required
def export_admin_results():
    """Admin: results for all students and courses."""
    return csv_download(report_service.RESULT_HEADERS, report_service.result_rows(), "results.csv")


@reports_bp.get("/api/faculty/reports/results.csv")
@faculty_required
def export_faculty_results():
    """Faculty: results for courses assigned to them."""
    return csv_download(
        report_service.RESULT_HEADERS,
        report_service.result_rows(current_user.id),
        "results.csv",
    )
