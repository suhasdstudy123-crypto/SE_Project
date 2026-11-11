"""Integration tests for CSV report exports (SRS-F-023, Issue #23)."""

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

CLASS_DATES = ["2026-10-12", "2026-10-13"]
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


@pytest.fixture
def course_setup(app, make_user):
    """Two faculty, one course each; 6 students, 5 enrolled in faculty 1's course."""
    make_user("faculty", email="faculty1@pes.edu")
    make_user("faculty", email="faculty2@pes.edu")

    with app.app_context():
        faculty1 = User.query.filter_by(email="faculty1@pes.edu").one()
        faculty2 = User.query.filter_by(email="faculty2@pes.edu").one()

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
            faculty_id=faculty1.id,
        )
        other_course = Course(
            code="UE24AM242A",
            name="Machine Learning",
            credits=4,
            department_id=department.id,
            faculty_id=faculty2.id,
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
            for index in range(1, 7)
        ]
        db.session.add_all([course, other_course, *students])
        db.session.flush()

        for student in students[:5]:
            db.session.add(Enrollment(student_id=student.id, course_id=course.id))
        db.session.add(Enrollment(student_id=students[0].id, course_id=other_course.id))
        db.session.commit()

        return {
            "course_id": course.id,
            "other_course_id": other_course.id,
            "enrolled": [student.id for student in students[:5]],
            "not_enrolled_srn": students[5].srn,
        }


@pytest.fixture
def report_setup(app, course_setup):
    """Two classes of attendance (Student 3 absent both times) and marks."""
    with app.app_context():
        course_id = course_setup["course_id"]
        for index, student_id in enumerate(course_setup["enrolled"]):
            for class_date in CLASS_DATES:
                db.session.add(
                    Attendance(
                        student_id=student_id,
                        course_id=course_id,
                        date=date.fromisoformat(class_date),
                        present=index != 2,
                    )
                )
            db.session.add(
                Marks(
                    student_id=student_id,
                    course_id=course_id,
                    isa1=18,
                    isa2=19,
                    assessment=9,
                    esa=45,
                    total=91,
                    grade="S",
                    grade_point=10,
                )
            )
        # Marks in faculty 2's course: must not appear in faculty 1's results export
        db.session.add(
            Marks(
                student_id=course_setup["enrolled"][0],
                course_id=course_setup["other_course_id"],
                isa1=10,
                isa2=10,
                assessment=5,
                esa=25,
                total=50,
                grade="D",
                grade_point=6,
            )
        )
        db.session.commit()
    return course_setup


def login(client, email, password=TEST_PASSWORD):
    """Log in through the authentication API."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def faculty_client(app, course_setup):
    """A client logged in as the assigned faculty member (faculty 1)."""
    client = app.test_client()
    assert login(client, "faculty1@pes.edu").status_code == 200
    return client


@pytest.fixture
def admin_client(app, make_user):
    """A client logged in as Admin."""
    make_user("admin")
    client = app.test_client()
    assert login(client, "admin@pes.edu").status_code == 200
    return client


def read_csv(response):
    """Decode an Excel-compatible (UTF-8 with BOM) CSV response into rows."""
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.data.startswith(b"\xef\xbb\xbf")
    return list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))


def test_tc_rpt_02_export_attendance_csv_for_course_with_5_students(faculty_client, report_setup):
    """TC-RPT-02: Attendance CSV for a course with 5 students -> header row + 5 data rows."""
    response = faculty_client.get(
        f"/api/faculty/reports/attendance.csv?course_id={report_setup['course_id']}"
    )
    rows = read_csv(response)

    assert rows[0] == ATTENDANCE_HEADERS
    assert len(rows) == 1 + 5
    srns = [row[0] for row in rows[1:]]
    assert srns == [f"PES1UG24AM{index:03d}" for index in range(1, 6)]
    assert report_setup["not_enrolled_srn"] not in srns
    assert rows[1] == ["PES1UG24AM001", "Student 1", "UE24AM241A", "2", "2", "100.0", "OK"]
    assert rows[3] == ["PES1UG24AM003", "Student 3", "UE24AM241A", "0", "2", "0.0", "Shortage"]
    assert 'filename="attendance_UE24AM241A.csv"' in response.headers["Content-Disposition"]


def test_admin_can_export_attendance_for_any_course(admin_client, report_setup):
    """Admin can download the attendance report of any course (SRS-F-023)."""
    response = admin_client.get(
        f"/api/admin/reports/attendance.csv?course_id={report_setup['course_id']}"
    )
    rows = read_csv(response)
    assert rows[0] == ATTENDANCE_HEADERS
    assert len(rows) == 6


def test_attendance_export_needs_a_valid_course(admin_client, faculty_client):
    """Missing course_id -> 400; unknown course -> 404."""
    assert admin_client.get("/api/admin/reports/attendance.csv").status_code == 400
    assert faculty_client.get("/api/faculty/reports/attendance.csv").status_code == 400
    assert admin_client.get("/api/admin/reports/attendance.csv?course_id=9999").status_code == 404
    assert (
        faculty_client.get("/api/faculty/reports/attendance.csv?course_id=9999").status_code == 404
    )


def test_faculty_cannot_export_another_facultys_attendance(app, course_setup):
    """Faculty 2 cannot download the attendance of faculty 1's course."""
    other = app.test_client()
    assert login(other, "faculty2@pes.edu").status_code == 200
    response = other.get(
        f"/api/faculty/reports/attendance.csv?course_id={course_setup['course_id']}"
    )
    assert response.status_code == 403


def test_admin_can_export_students(admin_client, course_setup):
    """Admin downloads all students with the right headers."""
    response = admin_client.get("/api/admin/reports/students.csv")
    rows = read_csv(response)
    assert rows[0] == ["SRN", "Name", "Email", "Department", "Section", "Semester"]
    assert len(rows) == 1 + 6
    assert rows[1][:2] == ["PES1UG24AM001", "Student 1"]
    assert 'filename="students.csv"' in response.headers["Content-Disposition"]


def test_faculty_results_export_only_has_own_courses(faculty_client, report_setup):
    """Faculty 1 gets results for their own course only, not faculty 2's course."""
    rows = read_csv(faculty_client.get("/api/faculty/reports/results.csv"))
    assert rows[0] == RESULT_HEADERS
    assert len(rows) == 1 + 5
    assert {row[2] for row in rows[1:]} == {"UE24AM241A"}
    assert rows[1][7:] == ["91.0", "S", "10"]


def test_admin_results_export_has_all_courses(admin_client, report_setup):
    """Admin gets results for every course."""
    rows = read_csv(admin_client.get("/api/admin/reports/results.csv"))
    assert rows[0] == RESULT_HEADERS
    assert len(rows) == 1 + 6
    assert {row[2] for row in rows[1:]} == {"UE24AM241A", "UE24AM242A"}


def test_csv_export_escapes_formula_cells(app, admin_client, course_setup):
    """A name starting with '=' is exported as text, not as an Excel formula."""
    with app.app_context():
        student = Student.query.filter_by(srn="PES1UG24AM001").one()
        student.name = '=HYPERLINK("http://evil.example","Click")'
        db.session.commit()

    rows = read_csv(admin_client.get("/api/admin/reports/students.csv"))
    assert rows[1][1] == '\'=HYPERLINK("http://evil.example","Click")'


@pytest.mark.parametrize(
    "url",
    [
        "/api/admin/reports/students.csv",
        "/api/admin/reports/attendance.csv",
        "/api/admin/reports/results.csv",
        "/api/faculty/reports/attendance.csv",
        "/api/faculty/reports/results.csv",
    ],
)
def test_report_exports_require_login(client, url):
    """Logged-out users cannot download reports."""
    assert client.get(url).status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "/api/admin/reports/students.csv",
        "/api/admin/reports/attendance.csv?course_id=1",
        "/api/faculty/reports/results.csv",
    ],
)
def test_student_cannot_export_reports(client, make_user, url):
    """Students cannot use Admin or Faculty report endpoints."""
    make_user("student")
    assert login(client, "student@pes.edu").status_code == 200
    assert client.get(url).status_code == 403
