"""Report service: builds CSV reports for Admin and Faculty (SRS-F-023, Issue #23)."""

import csv
import io

from src.models import Course, Marks, Student
from src.services.attendance_service import course_attendance_summary
from src.services.course_service import course_roster

# Excel treats a cell starting with one of these as a formula (CSV injection).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

STUDENT_HEADERS = ["SRN", "Name", "Email", "Department", "Section", "Semester"]

ATTENDANCE_HEADERS = [
    "SRN",
    "Name",
    "Course",
    "Classes Attended",
    "Classes Held",
    "Attendance %",
    "Status",
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


def safe_cell(value):
    """Return a CSV cell that Excel will show as text, never run as a formula."""
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv(headers, rows):
    """Build Excel-compatible UTF-8 CSV text (with BOM) from headers and rows."""
    output = io.StringIO()
    output.write("﻿")
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return output.getvalue()


def student_rows():
    """One row per student, ordered by SRN."""
    return [
        [
            student.srn,
            student.name,
            student.email,
            student.department.name if student.department else "",
            student.section.name if student.section else "",
            student.semester,
        ]
        for student in Student.query.order_by(Student.srn).all()
    ]


def attendance_rows(course):
    """One row per enrolled student with classes attended, held, % and shortage status."""
    summary = course_attendance_summary(course)
    rows = []
    for student in course_roster(course):
        info = summary[student.id]
        rows.append(
            [
                student.srn,
                student.name,
                course.code,
                info["attended"],
                info["held"],
                info["percentage"],
                "Shortage" if info["shortage"] else "OK",
            ]
        )
    return rows


def result_rows(faculty_id=None):
    """One row per marks record; only that faculty's courses when faculty_id is given."""
    query = Marks.query.join(Course).join(Student)
    if faculty_id is not None:
        query = query.filter(Course.faculty_id == faculty_id)
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
        for record in query.order_by(Student.srn, Course.code).all()
    ]
