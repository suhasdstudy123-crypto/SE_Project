
"""Integration tests for CSV report exports (Issue #23)."""

import csv
import io
from datetime import date

import pytest

from src.extensions import db
from src.models import (
    Attendance,
    Course,
    Department,
    Enrollment,
    Marks,
    Section,
    Student,
    User,
)
from tests.conftest import TEST_PASSWORD


CLASS_DATE = "2026-10-12"
@pytest.fixture
def course_setup(app, make_user):
    """Create a course with three enrolled students and two faculty members."""
    make_user("faculty", email="faculty1@pes.edu")
    make_user("faculty", email="faculty2@pes.edu")

    with app.app_context():
        faculty = User.query.filter_by(email="faculty1@pes.edu").one()

        department = Department(name="CSE-AIML")
        db.session.add(department)
        db.session.flush()

        section = Section(name="H", department_id=department.id)
        db.session.add(section)
        db.session.flush()

        course = Course(
            code="UE24AM241A",
            name="Software Engineering",
            credits=4,
            department_id=department.id,
            faculty_id=faculty.id,
        )

        students = [
            Student(
                srn=f"PES1UG24AM{index:03d}",
                name=f"Student {index}",
                email=f"student{index}@pes.edu",
                semester=4,
                department_id=department.id,
                section_id=section.id,
            )
            for index in range(1, 5)
        ]

        db.session.add(course)
        db.session.add_all(students)
        db.session.flush()

        for student in students[:3]:
            db.session.add(
                Enrollment(student_id=student.id, course_id=course.id)
            )

        db.session.commit()

        return {
            "course_id": course.id,
            "enrolled": [student.id for student in students[:3]],
            "faculty_id": faculty.id,
        }


@pytest.fixture
def faculty_client(app, course_setup):
    """Return a client logged in as the assigned faculty member."""
    client = app.test_client()
    assert login(client, "faculty1@pes.edu").status_code == 200
    return client

def login(client, email, password=TEST_PASSWORD):
    """Log in through the authentication API."""
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def read_csv(response):
    """Decode an Excel-compatible CSV response."""
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.data.startswith(b"\xef\xbb\xbf")

    text = response.data.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


@pytest.fixture
def report_setup(app, course_setup):
    """Create attendance and marks data for the report tests."""
    with app.app_context():
        course = db.session.get(Course, course_setup["course_id"])

        for index, student_id in enumerate(course_setup["enrolled"]):
            db.session.add(
                Attendance(
                    student_id=student_id,
                    course_id=course.id,
                    date=date.fromisoformat(CLASS_DATE),
                    present=index != 1,
                )
            )
            db.session.add(
                Marks(
                    student_id=student_id,
                    course_id=course.id,
                    isa1=18,
                    isa2=19,
                    assessment=9,
                    esa=45,
                    total=91,
                    grade="A",
                    grade_point=9,
                )
            )

        db.session.commit()

    return course_setup


def test_tc_rpt_02_admin_can_export_students(client, make_user, course_setup):
    """TC-RPT-02: Admin downloads a student CSV with correct headers and rows."""
    make_user("admin")
    login(client, "admin@pes.edu")

    response = client.get("/api/admin/reports/students.csv")
    rows = read_csv(response)

    assert rows[0] == [
        "SRN", "Name", "Email", "Department", "Section", "Semester"
    ]
    assert len(rows) == 5
    assert rows[1][0].startswith("PES1UG24AM")
    assert 'filename="students.csv"' in response.headers["Content-Disposition"]


def test_tc_rpt_02_faculty_can_export_attendance(
    app, faculty_client, report_setup
):
    """TC-RPT-02: Faculty downloads attendance for an assigned course."""
    response = faculty_client.get(
        "/api/faculty/reports/attendance.csv"
        f"?course_id={report_setup['course_id']}&date={CLASS_DATE}"
    )
    rows = read_csv(response)

    assert rows[0] == [
        "SRN", "Name", "Course", "Date",
        "Attendance Status", "Attendance %",
    ]
    assert len(rows) == 4
    assert rows[1][3] == CLASS_DATE
    assert rows[1][4] in ("Present", "Absent")
    assert 'filename="attendance.csv"' in response.headers["Content-Disposition"]


def test_tc_rpt_02_faculty_can_export_results(
    app, faculty_client, report_setup
):
    """TC-RPT-02: Faculty downloads results for assigned courses."""
    response = faculty_client.get("/api/faculty/reports/results.csv")
    rows = read_csv(response)

    assert rows[0] == [
        "SRN", "Name", "Course", "ISA 1", "ISA 2",
        "Assessment", "ESA", "Total", "Grade", "Grade Point",
    ]
    assert len(rows) == 4
    assert rows[1][2] == "UE24AM241A"
    assert rows[1][7] == "91.0"


def test_tc_rpt_02_admin_can_export_results(
    client, make_user, report_setup
):
    """TC-RPT-02: Admin downloads the results report."""
    make_user("admin")
    login(client, "admin@pes.edu")

    response = client.get("/api/admin/reports/results.csv")
    rows = read_csv(response)

    assert rows[0][0:3] == ["SRN", "Name", "Course"]
    assert len(rows) == 4


def test_faculty_cannot_export_another_facultys_attendance(
    app, course_setup
):
    """A faculty member cannot export another faculty member's course."""
    other = app.test_client()
    login(other, "faculty2@pes.edu")

    response = other.get(
        "/api/faculty/reports/attendance.csv"
        f"?course_id={course_setup['course_id']}&date={CLASS_DATE}"
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "url",
    [
        "/api/admin/reports/students.csv",
        "/api/admin/reports/results.csv",
        "/api/faculty/reports/attendance.csv",
        "/api/faculty/reports/results.csv",
    ],
)
def test_report_exports_require_login(client, url):
    """Unauthenticated users cannot download reports."""
    response = client.get(url)
    assert response.status_code == 401


def test_student_cannot_export_admin_student_report(
    client, make_user
):
    """Students cannot access the Admin report endpoint."""
    make_user("student")
    login(client, "student@pes.edu")

    response = client.get("/api/admin/reports/students.csv")
    assert response.status_code == 403
