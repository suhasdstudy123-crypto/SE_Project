"""Integration tests for the result analysis API (SRS-F-022, Issue #25)."""

import pytest

from src.extensions import db
from src.models import Course, Department, Enrollment, Marks, Section, Student, User
from tests.conftest import TEST_PASSWORD

COMPLETE_MARKS = [
    (6, 6, 3, 15),  # 30 -> F
    (8, 8, 4, 20),  # 40 -> E
    (12, 12, 6, 30),  # 60 -> C
    (16, 16, 8, 40),  # 80 -> A
    (18, 18, 9, 45),  # 90 -> S
]


def login(client, email):
    """Log in through the authentication API."""
    return client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})


@pytest.fixture
def analysis_data(app, make_user):
    """Faculty 1 teaches a course with 5 results; a 6th student is enrolled elsewhere only."""
    make_user("faculty", "faculty1@pes.edu")
    make_user("faculty", "faculty2@pes.edu")
    make_user("admin")
    make_user("student", "student1@pes.edu")
    make_user("student", "student6@pes.edu")

    with app.app_context():
        faculty1 = User.query.filter_by(email="faculty1@pes.edu").one()
        faculty2 = User.query.filter_by(email="faculty2@pes.edu").one()
        department = Department(name="CSE-AIML")
        db.session.add(department)
        db.session.flush()
        section = Section(name="H", department_id=department.id)
        course = Course(
            code="UE24AM241A",
            name="Software Engineering",
            credits=4,
            department_id=department.id,
            faculty_id=faculty1.id,
        )
        other = Course(
            code="UE24AM242A",
            name="Machine Learning",
            credits=4,
            department_id=department.id,
            faculty_id=faculty2.id,
        )
        db.session.add_all([section, course, other])
        db.session.flush()

        students = []
        for index in range(1, 7):
            user = User.query.filter_by(email=f"student{index}@pes.edu").first()
            students.append(
                Student(
                    srn=f"PES1UG24AM00{index}",
                    name=f"Student {index}",
                    email=f"student{index}@pes.edu",
                    semester=4,
                    department_id=department.id,
                    section_id=section.id,
                    user_id=user.id if user else None,
                )
            )
        db.session.add_all(students)
        db.session.flush()

        for student, (isa1, isa2, assessment, esa) in zip(students[:5], COMPLETE_MARKS):
            db.session.add(Enrollment(student_id=student.id, course_id=course.id))
            db.session.add(
                Marks(
                    student_id=student.id,
                    course_id=course.id,
                    isa1=isa1,
                    isa2=isa2,
                    assessment=assessment,
                    esa=esa,
                    total=isa1 + isa2 + assessment + esa,
                )
            )
        db.session.add(Enrollment(student_id=students[5].id, course_id=other.id))
        db.session.commit()
        return {"course_id": course.id, "other_course_id": other.id}


def test_faculty_sees_analysis_of_own_course(client, analysis_data):
    """Faculty gets average, highest, lowest, pass % and grade counts (TC-RPT-01 numbers)."""
    assert login(client, "faculty1@pes.edu").status_code == 200

    response = client.get(f"/api/faculty/analysis/{analysis_data['course_id']}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["course"]["code"] == "UE24AM241A"
    assert body["students_appeared"] == 5
    assert body["average"] == 60
    assert body["highest"] == 90
    assert body["lowest"] == 30
    assert body["pass_percentage"] == 80
    assert body["grade_distribution"] == {
        "S": 1,
        "A": 1,
        "B": 0,
        "C": 1,
        "D": 0,
        "E": 1,
        "F": 1,
    }


def test_faculty_cannot_see_another_facultys_course(client, analysis_data):
    """Faculty 2 does not teach this course -> 403."""
    assert login(client, "faculty2@pes.edu").status_code == 200
    assert client.get(f"/api/faculty/analysis/{analysis_data['course_id']}").status_code == 403


def test_admin_sees_any_course(client, analysis_data):
    """Admin can see the analysis of every course, even with no results yet."""
    assert login(client, "admin@pes.edu").status_code == 200
    assert client.get(f"/api/admin/analysis/{analysis_data['course_id']}").status_code == 200

    response = client.get(f"/api/admin/analysis/{analysis_data['other_course_id']}")
    assert response.status_code == 200
    assert response.get_json()["students_appeared"] == 0


def test_student_sees_class_analysis_of_enrolled_course_only(client, analysis_data):
    """Student 1 is enrolled -> 200 (totals only, no names); Student 6 is not -> 403."""
    assert login(client, "student1@pes.edu").status_code == 200
    response = client.get(f"/api/student/analysis/{analysis_data['course_id']}")
    assert response.status_code == 200
    assert "Student 2" not in response.get_data(as_text=True)
    client.post("/api/auth/logout")

    assert login(client, "student6@pes.edu").status_code == 200
    assert client.get(f"/api/student/analysis/{analysis_data['course_id']}").status_code == 403


def test_unknown_course_is_404(client, analysis_data):
    """A course that does not exist -> 404."""
    assert login(client, "admin@pes.edu").status_code == 200
    assert client.get("/api/admin/analysis/9999").status_code == 404


@pytest.mark.parametrize(
    "url",
    ["/api/admin/analysis/1", "/api/faculty/analysis/1", "/api/student/analysis/1"],
)
def test_analysis_needs_login(client, url):
    """Logged-out users get 401."""
    assert client.get(url).status_code == 401


def test_student_cannot_use_faculty_analysis_url(client, analysis_data):
    """A student calling the Faculty URL gets 403 (role check)."""
    assert login(client, "student1@pes.edu").status_code == 200
    assert client.get(f"/api/faculty/analysis/{analysis_data['course_id']}").status_code == 403
