"""Integration tests for Admin and Faculty dashboards (TC-RPT-03)."""

from datetime import date, timedelta

import pytest

from src.extensions import db
from src.models import (
    Attendance,
    Course,
    Department,
    Enrollment,
    FeeState,
    FeeStatus,
    Section,
    Student,
    User,
)
from tests.conftest import TEST_PASSWORD


def login(client, email):
    """Log in through the authentication API."""
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )


@pytest.fixture
def dashboard_data(app, make_user):
    """Create students, courses, fee records and attendance for dashboard tests."""
    make_user("faculty", "faculty1@pes.edu")
    make_user("faculty", "faculty2@pes.edu")
    make_user("admin")
    make_user("student")

    with app.app_context():
        faculty1_id = User.query.filter_by(email="faculty1@pes.edu").first().id
        faculty2_id = User.query.filter_by(email="faculty2@pes.edu").first().id
        department = Department(name="Computer Science")
        db.session.add(department)
        db.session.flush()

        section = Section(name="A", department_id=department.id)
        db.session.add(section)
        db.session.flush()

        student_a = Student(
            srn="PES1UG24CS001",
            name="Student A",
            email="a@example.com",
            semester=2,
            department_id=department.id,
            section_id=section.id,
        )
        student_b = Student(
            srn="PES1UG24CS002",
            name="Student B",
            email="b@example.com",
            semester=2,
            department_id=department.id,
            section_id=section.id,
        )
        student_c = Student(
            srn="PES1UG24CS003",
            name="Student C",
            email="c@example.com",
            semester=2,
            department_id=department.id,
            section_id=section.id,
        )
        db.session.add_all([student_a, student_b, student_c])
        db.session.flush()

        course1 = Course(
            code="CS101",
            name="Data Structures",
            credits=4,
            department_id=department.id,
            faculty_id=faculty1_id,
        )
        course2 = Course(
            code="CS102",
            name="Database Systems",
            credits=4,
            department_id=department.id,
            faculty_id=faculty1_id,
        )
        course3 = Course(
            code="CS103",
            name="Computer Networks",
            credits=4,
            department_id=department.id,
            faculty_id=faculty2_id,
        )
        db.session.add_all([course1, course2, course3])
        db.session.flush()

        db.session.add_all(
            [
                Enrollment(student_id=student_a.id, course_id=course1.id),
                Enrollment(student_id=student_b.id, course_id=course1.id),
                Enrollment(student_id=student_a.id, course_id=course2.id),
                Enrollment(student_id=student_c.id, course_id=course3.id),
            ]
        )

        # Student A: 0/4 in CS101 -> shortage.
        # Student B: 3/4 in CS101 -> exactly 75%, no shortage.
        # Student A: 3/4 in CS102 -> exactly 75%, no shortage.
        # Student C: 0/2 in CS103 -> shortage.
        attendance_records = []
        attendance_data = [
            (course1.id, student_a.id, 0, 4),
            (course1.id, student_b.id, 3, 4),
            (course2.id, student_a.id, 3, 4),
            (course3.id, student_c.id, 0, 2),
        ]

        for course_id, student_id, attended, held in attendance_data:
            for index in range(held):
                attendance_records.append(
                    Attendance(
                        course_id=course_id,
                        student_id=student_id,
                        date=date(2026, 1, 1) + timedelta(days=index),
                        present=index < attended,
                    )
                )

        db.session.add_all(attendance_records)

        # Student A has two unpaid semesters but counts as one defaulter.
        db.session.add_all(
            [
                FeeStatus(
                    student_id=student_a.id,
                    semester=1,
                    status=FeeState.UNPAID,
                ),
                FeeStatus(
                    student_id=student_a.id,
                    semester=2,
                    status=FeeState.UNPAID,
                ),
                FeeStatus(
                    student_id=student_b.id,
                    semester=1,
                    status=FeeState.PAID,
                ),
                FeeStatus(
                    student_id=student_c.id,
                    semester=1,
                    status=FeeState.UNPAID,
                ),
            ]
        )

        db.session.commit()

    return {
        "faculty1_email": "faculty1@pes.edu",
        "faculty2_email": "faculty2@pes.edu",
    }


def test_tc_rpt_03_admin_dashboard_counts_correctly(client, dashboard_data):
    """Admin sees institution-wide counts with unique students."""
    assert login(client, "admin@pes.edu").status_code == 200

    response = client.get("/api/admin/dashboard")

    assert response.status_code == 200
    assert response.get_json() == {
        "total_students": 3,
        "total_courses": 3,
        "attendance_shortages": 2,
        "fee_defaulters": 2,
    }


def test_tc_rpt_03_faculty_dashboard_shows_assigned_courses_only(client, dashboard_data):
    """Faculty sees only students and shortages from assigned courses."""
    assert login(client, dashboard_data["faculty1_email"]).status_code == 200

    response = client.get("/api/faculty/dashboard")

    assert response.status_code == 200
    assert response.get_json() == {
        "total_students": 2,
        "total_courses": 2,
        "attendance_shortages": 1,
    }


def test_tc_rpt_03_unauthenticated_dashboard_access_is_rejected(client):
    """Unauthenticated users cannot access either dashboard."""
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/faculty/dashboard").status_code == 401


@pytest.mark.parametrize("role", ["faculty", "student"])
def test_tc_rpt_03_non_admin_cannot_access_admin_dashboard(client, make_user, role):
    """Only Admin can access institution-wide dashboard information."""
    email = f"{role}@pes.edu"
    make_user(role)

    assert login(client, email).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 403


@pytest.mark.parametrize("role", ["admin", "student"])
def test_tc_rpt_03_non_faculty_cannot_access_faculty_dashboard(client, make_user, role):
    """Only Faculty can access the Faculty dashboard."""
    email = f"{role}@pes.edu"
    make_user(role)

    assert login(client, email).status_code == 200
    assert client.get("/api/faculty/dashboard").status_code == 403
