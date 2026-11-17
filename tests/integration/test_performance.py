"""Performance check with a large data set (TC-PERF-01, SRS-NF-001, Issue #26).

Seeds 500 students and 20 courses (125 students per course, 10 classes of attendance
and full marks for everyone), then times the API behind each key page.
Target: each page loads in <= 2 s. This test checks the API part; the React render
part is timed by hand in the browser (see docs/testing/Performance_Usability_Check.md).
"""

import time
from datetime import date, timedelta

import pytest
from sqlalchemy import insert

from src.extensions import db
from src.models import (
    Attendance,
    Course,
    Department,
    Enrollment,
    ExamRegistration,
    FeeState,
    FeeStatus,
    Marks,
    Section,
    Student,
    User,
)
from tests.conftest import TEST_PASSWORD

STUDENTS = 500
COURSES = 20
COURSES_PER_STUDENT = 5
CLASSES = 10
LIMIT_SECONDS = 2.0


def login(client, email):
    """Log in through the authentication API."""
    return client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})


@pytest.fixture
def big_data(app, make_user):
    """500 students, 20 courses, 2,500 enrollments, 25,000 attendance rows, 2,500 marks."""
    make_user("admin")
    make_user("faculty", "faculty1@pes.edu")
    make_user("student", "student1@pes.edu")

    with app.app_context():
        faculty = User.query.filter_by(email="faculty1@pes.edu").one()
        student_user = User.query.filter_by(email="student1@pes.edu").one()
        department = Department(name="CSE-AIML")
        db.session.add(department)
        db.session.flush()
        section = Section(name="A", department_id=department.id)
        db.session.add(section)
        db.session.flush()

        db.session.execute(
            insert(Course),
            [
                {
                    "code": f"UE24AM{index:03d}",
                    "name": f"Course {index}",
                    "credits": 4,
                    "department_id": department.id,
                    "faculty_id": faculty.id,
                    "syllabus": "",
                }
                for index in range(1, COURSES + 1)
            ],
        )
        db.session.execute(
            insert(Student),
            [
                {
                    "srn": f"PES1UG24AM{index:03d}",
                    "name": f"Student {index}",
                    "email": f"student{index}@pes.edu",
                    "semester": 4,
                    "department_id": department.id,
                    "section_id": section.id,
                    "user_id": student_user.id if index == 1 else None,
                }
                for index in range(1, STUDENTS + 1)
            ],
        )
        course_ids = [course.id for course in Course.query.order_by(Course.id)]
        student_ids = [student.id for student in Student.query.order_by(Student.id)]

        enrollments, attendance, marks, registrations = [], [], [], []
        for position, student_id in enumerate(student_ids):
            for offset in range(COURSES_PER_STUDENT):
                course_id = course_ids[(position + offset * 4) % COURSES]
                enrollments.append({"student_id": student_id, "course_id": course_id})
                registrations.append({"student_id": student_id, "course_id": course_id})
                marks.append(
                    {
                        "student_id": student_id,
                        "course_id": course_id,
                        "isa1": 15,
                        "isa2": 16,
                        "assessment": 8,
                        "esa": 40,
                        "total": 79,
                        "grade": "B",
                        "grade_point": 8,
                    }
                )
                for day in range(CLASSES):
                    attendance.append(
                        {
                            "student_id": student_id,
                            "course_id": course_id,
                            "date": date(2026, 10, 1) + timedelta(days=day),
                            "present": (position + day) % 5 != 0,
                        }
                    )
        db.session.execute(insert(Enrollment), enrollments)
        db.session.execute(insert(ExamRegistration), registrations)
        db.session.execute(insert(Marks), marks)
        db.session.execute(insert(Attendance), attendance)
        db.session.execute(
            insert(FeeStatus),
            [
                {
                    "student_id": student_id,
                    "semester": 4,
                    "status": FeeState.PAID if index % 10 else FeeState.UNPAID,
                }
                for index, student_id in enumerate(student_ids)
            ],
        )
        db.session.commit()
        return {"course_id": course_ids[0]}


def timed_get(client, url):
    """GET a URL and return (status code, seconds taken)."""
    start = time.perf_counter()
    response = client.get(url)
    return response.status_code, time.perf_counter() - start


def check_pages(client, urls):
    """Every page must answer 200 within the limit; returns the timings for the report."""
    timings = {}
    for url in urls:
        status, seconds = timed_get(client, url)
        assert status == 200, url
        timings[url] = round(seconds, 3)
    print("\nTC-PERF-01 timings (seconds):", timings)
    slow = {url: seconds for url, seconds in timings.items() if seconds > LIMIT_SECONDS}
    assert not slow, f"Slower than {LIMIT_SECONDS} s: {slow}"
    return timings


def test_tc_perf_01_admin_pages_with_500_students(client, big_data):
    """TC-PERF-01: Admin student list, dashboard, ESA roster and reports load in <= 2 s."""
    assert login(client, "admin@pes.edu").status_code == 200
    course_id = big_data["course_id"]
    check_pages(
        client,
        [
            "/api/admin/students",
            "/api/admin/dashboard",
            f"/api/admin/esa-eligibility/{course_id}",
            f"/api/admin/analysis/{course_id}",
            "/api/admin/reports/results.csv",
            f"/api/admin/reports/attendance.csv?course_id={course_id}",
        ],
    )
    assert len(client.get("/api/admin/students").get_json()["students"]) == STUDENTS


def test_tc_perf_01_faculty_pages_with_500_students(client, big_data):
    """TC-PERF-01: Faculty attendance and marks pages for a 125-student course load in <= 2 s."""
    assert login(client, "faculty1@pes.edu").status_code == 200
    course_id = big_data["course_id"]
    check_pages(
        client,
        [
            "/api/faculty/courses",
            f"/api/faculty/attendance/{course_id}?date=2026-10-05",
            f"/api/faculty/marks/{course_id}",
            "/api/faculty/dashboard",
            f"/api/faculty/analysis/{course_id}",
        ],
    )


def test_tc_perf_01_student_pages_with_500_students(client, big_data):
    """TC-PERF-01: Student results, attendance and ESA pages load in <= 2 s."""
    assert login(client, "student1@pes.edu").status_code == 200
    check_pages(
        client,
        ["/api/student/results", "/api/student/attendance", "/api/student/esa"],
    )
