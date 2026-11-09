"""CSV report exports for Admin and Faculty (Issue #23)."""

import csv
import io
from datetime import date
from src.extensions import db

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user

from src.models import Attendance, Course, Marks, Student
from src.rbac import admin_required, faculty_required
from src.services import attendance_service

reports_bp = Blueprint("reports", __name__)


def csv_response(headers, rows, filename):
    """Build an Excel-compatible UTF-8 CSV download."""
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def get_results_rows(faculty_id=None):
    """Get result rows, optionally restricted to one faculty member."""
    query = Marks.query.join(Course).join(Student)

    if faculty_id is not None:
        query = query.filter(Course.faculty_id == faculty_id)

    records = query.order_by(Student.srn, Course.code).all()

    return [
        [
            record.student.srn,
            record.student.name,
            record.course.code,
            record.isa1,
            record.isa2,
            record.assessment,
            record.esa,
            record.total,
            record.grade,
            record.grade_point,
        ]
        for record in records
    ]


RESULT_HEADERS = [
    "SRN",
    "Name",
    "Course",
    "ISA 1",
    "ISA 2",
    "Assessment",
    "ESA",
    "Total",
    "Grade",
    "Grade Point",
]


@reports_bp.get("/api/admin/reports/students.csv")
@admin_required
def export_students():
    """Export student records for Admin."""
    students = Student.query.order_by(Student.srn).all()

    rows = [
        [
            student.srn,
            student.name,
            student.email,
            student.department.name if student.department else "",
            student.section.name if student.section else "",
            student.semester,
        ]
        for student in students
    ]

    return csv_response(
        ["SRN", "Name", "Email", "Department", "Section", "Semester"],
        rows,
        "students.csv",
    )


@reports_bp.get("/api/faculty/reports/attendance.csv")
@faculty_required
def export_attendance():
    """Export attendance for a course assigned to the logged-in faculty."""
    course_id = request.args.get("course_id", type=int)
    class_date = request.args.get("date")

    if not course_id or not class_date:
        return jsonify({"error": "course_id and date are required."}), 400

    course = db.session.get(Course, course_id)

    if course is None:
        return jsonify({"error": "Course not found."}), 404

    if course.faculty_id != current_user.id:
        return jsonify({"error": "You are not assigned to this course."}), 403

    try:
        parsed_date = date.fromisoformat(class_date)
    except ValueError:
        return jsonify({"error": "Invalid date. Use YYYY-MM-DD."}), 400

    records = (
        Attendance.query.filter_by(course_id=course.id, date=parsed_date)
        .order_by(Attendance.id)
        .all()
    )

    summary = attendance_service.course_attendance_summary(course)

    rows = [
        [
            record.student.srn,
            record.student.name,
            course.code,
            parsed_date.isoformat(),
            "Present" if record.present else "Absent",
            summary.get(record.student_id, {}).get("percentage", 0.0),
        ]
        for record in records
    ]

    return csv_response(
        ["SRN", "Name", "Course", "Date", "Attendance Status", "Attendance %"],
        rows,
        "attendance.csv",
    )


@reports_bp.get("/api/admin/reports/results.csv")
@admin_required
def export_admin_results():
    """Export all student results for Admin."""
    return csv_response(
        RESULT_HEADERS,
        get_results_rows(),
        "results.csv",
    )


@reports_bp.get("/api/faculty/reports/results.csv")
@faculty_required
def export_faculty_results():
    """Export results for courses assigned to the logged-in faculty."""
    return csv_response(
        RESULT_HEADERS,
        get_results_rows(current_user.id),
        "results.csv",
    )
