"""Integration tests for the ESA window, registration, eligibility and overrides.

Issues #17, #18, #19, #20 (TC-ESA-01 .. TC-ESA-07).
"""

from datetime import date, timedelta

import pytest

from src.extensions import db
from src.models import (
    Attendance,
    AuditLog,
    Course,
    Department,
    Enrollment,
    ExamRegistration,
    ExamWindow,
    FeeStatus,
    Section,
    Student,
    User,
)
from tests.conftest import TEST_PASSWORD

# Students: (email, fees, classes held, classes attended)
STUDENTS = {
    "eligible": ("s1@pes.edu", "PAID", 20, 18),  # 90%
    "boundary": ("s2@pes.edu", "PAID", 20, 15),  # exactly 75%
    "unpaid": ("s3@pes.edu", "UNPAID", 20, 18),  # fees unpaid, 90%
    "shortage": ("s4@pes.edu", "PAID", 20, 14),  # 70%
}


def login(client, email, password=TEST_PASSWORD):
    """Log in through the authentication API."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def esa(app, make_user):
    """One course, four enrolled students with linked logins, and an open ESA window."""
    make_user("admin")
    for email, *_ in STUDENTS.values():
        make_user("student", email=email)
    with app.app_context():
        department = Department(name="CSE-AIML")
        db.session.add(department)
        db.session.flush()
        section = Section(name="H", department_id=department.id)
        db.session.add(section)
        db.session.flush()
        course = Course(
            code="UE24AM241A", name="Software Engineering", credits=4, department_id=department.id
        )
        other = Course(code="UE24AM242A", name="ML", credits=4, department_id=department.id)
        db.session.add_all([course, other])
        db.session.flush()

        ids = {}
        for index, (key, (email, fees, held, attended)) in enumerate(STUDENTS.items(), 1):
            student = Student(
                srn=f"PES1UG24AM{index:03d}",
                name=f"Student {key}",
                email=email,
                semester=4,
                department_id=department.id,
                section_id=section.id,
                user_id=User.query.filter_by(email=email).one().id,
            )
            db.session.add(student)
            db.session.flush()
            db.session.add(Enrollment(student_id=student.id, course_id=course.id))
            db.session.add(FeeStatus(student_id=student.id, semester=4, status=fees))
            for day in range(held):
                db.session.add(
                    Attendance(
                        student_id=student.id,
                        course_id=course.id,
                        date=date(2026, 8, 1) + timedelta(days=day),
                        present=day < attended,
                    )
                )
            ids[key] = student.id
        db.session.add(ExamWindow(is_open=True))
        db.session.commit()
        return {"course_id": course.id, "other_course_id": other.id, "students": ids}


@pytest.fixture
def admin_client(app, esa):  # pylint: disable=unused-argument
    """A client logged in as Admin."""
    client = app.test_client()
    assert login(client, "admin@pes.edu").status_code == 200
    return client


def student_client(app, key):
    """A client logged in as one of the STUDENTS."""
    client = app.test_client()
    assert login(client, STUDENTS[key][0]).status_code == 200
    return client


def register(client, course_id):
    """POST /api/esa/register."""
    return client.post("/api/esa/register", json={"course_id": course_id})


def drop(client, course_id):
    """POST /api/esa/drop."""
    return client.post("/api/esa/drop", json={"course_id": course_id})


def set_window(client, is_open):
    """PUT /api/admin/esa-window."""
    return client.put("/api/admin/esa-window", json={"open": is_open})


def registrations(app):
    """Number of ESA registration rows."""
    with app.app_context():
        return ExamRegistration.query.count()


# ---------------------------------------------------------------- TC-ESA-01 window


def test_tc_esa_01_closed_window_rejects_then_open_window_accepts(app, admin_client, esa):
    """TC-ESA-01: Admin closes the window -> rejected; Admin opens it -> registration succeeds."""
    student = student_client(app, "eligible")

    response = set_window(admin_client, False)
    assert response.status_code == 200
    assert response.get_json()["window"]["is_open"] is False
    assert admin_client.get("/api/admin/esa-window").get_json()["window"]["is_open"] is False

    response = register(student, esa["course_id"])
    assert response.status_code == 403
    assert response.get_json()["reason"] == "window_closed"
    assert registrations(app) == 0

    assert set_window(admin_client, True).get_json()["window"]["is_open"] is True
    assert register(student, esa["course_id"]).status_code == 201
    assert registrations(app) == 1


@pytest.mark.parametrize("payload", [{}, {"open": "true"}, {"open": 1}])
def test_window_toggle_needs_a_boolean(admin_client, payload):
    """open must be true or false."""
    assert admin_client.put("/api/admin/esa-window", json=payload).status_code == 400


def test_only_admin_controls_window_and_overrides(app, esa, make_user):
    """Students and Faculty get HTTP 403 on the admin ESA API (SR-002)."""
    make_user("faculty")
    faculty = app.test_client()
    login(faculty, "faculty@pes.edu")
    for client in (student_client(app, "eligible"), faculty):
        assert set_window(client, False).status_code == 403
        assert client.get(f"/api/admin/esa-eligibility/{esa['course_id']}").status_code == 403
        assert client.post("/api/admin/eligibility-override", json={}).status_code == 403
    assert register(faculty, esa["course_id"]).status_code == 403
    assert faculty.get("/api/student/esa").status_code == 403


def test_not_logged_in_is_401(client):
    """Unauthenticated requests are rejected."""
    assert client.post("/api/esa/register", json={"course_id": 1}).status_code == 401
    assert client.get("/api/admin/esa-window").status_code == 401


# ---------------------------------------------------------------- TC-ESA-02 / 03 register & drop


def test_tc_esa_02_eligible_student_registers_then_drops(app, esa):
    """TC-ESA-02: registration row created, then removed."""
    student = student_client(app, "eligible")
    response = register(student, esa["course_id"])
    assert response.status_code == 201
    assert response.get_json() == {"status": "registered", "course_id": esa["course_id"]}
    assert registrations(app) == 1

    response = drop(student, esa["course_id"])
    assert response.status_code == 200
    assert response.get_json()["status"] == "dropped"
    assert registrations(app) == 0


def test_tc_esa_03_drop_after_window_closed_is_403(app, admin_client, esa):
    """TC-ESA-03: dropping after the window is closed -> HTTP 403 'registration window closed'."""
    student = student_client(app, "eligible")
    register(student, esa["course_id"])
    set_window(admin_client, False)

    response = drop(student, esa["course_id"])
    assert response.status_code == 403
    assert "registration window is closed" in response.get_json()["error"]
    assert registrations(app) == 1


def test_register_twice_is_409_and_drop_unregistered_is_404(app, esa):
    """Already registered -> 409; not registered -> 404 (SAD 4.3.2)."""
    student = student_client(app, "eligible")
    register(student, esa["course_id"])
    assert register(student, esa["course_id"]).status_code == 409

    other = student_client(app, "boundary")
    assert drop(other, esa["course_id"]).status_code == 404


def test_course_not_enrolled_or_missing(app, esa):
    """A course the student is not enrolled in is a 404; so is an unknown course."""
    student = student_client(app, "eligible")
    assert register(student, esa["other_course_id"]).status_code == 404
    assert register(student, 9999).status_code == 404
    assert student.post("/api/esa/register", json={}).status_code == 400


def test_student_login_without_record_gets_404(
    app, esa, make_user
):  # pylint: disable=unused-argument
    """A Student login not linked to a student record cannot use the ESA API."""
    make_user("student", email="nobody@pes.edu")
    client = app.test_client()
    login(client, "nobody@pes.edu")
    assert client.get("/api/student/esa").status_code == 404


# ---------------------------------------------------------------- TC-ESA-04 / 05 / 06 eligibility


def test_tc_esa_04_fees_unpaid_is_blocked_with_reason(app, esa):
    """TC-ESA-04: fees Unpaid, attendance 90% -> blocked with 'fees unpaid'."""
    response = register(student_client(app, "unpaid"), esa["course_id"])
    assert response.status_code == 403
    assert response.get_json()["reason"] == "fees_unpaid"
    assert "Fees unpaid" in response.get_json()["error"]
    assert registrations(app) == 0


def test_tc_esa_05_attendance_shortage_is_blocked_with_reason(app, esa):
    """TC-ESA-05: fees Paid, attendance 70% -> blocked with 'attendance shortage'."""
    response = register(student_client(app, "shortage"), esa["course_id"])
    assert response.status_code == 403
    assert response.get_json()["reason"] == "attendance_shortage"
    assert "Attendance 70% < 75%" in response.get_json()["error"]


def test_tc_esa_06_exactly_75_percent_is_allowed(app, esa):
    """TC-ESA-06: fees Paid, attendance exactly 75.00% -> eligible (boundary value)."""
    assert register(student_client(app, "boundary"), esa["course_id"]).status_code == 201


def test_student_overview_shows_eligibility_and_registration(app, esa):
    """GET /api/student/esa lists each enrolled course with eligibility and the window state."""
    student = student_client(app, "shortage")
    data = student.get("/api/student/esa").get_json()
    assert data["window"]["is_open"] is True
    assert len(data["courses"]) == 1
    course = data["courses"][0]
    assert course["course_code"] == "UE24AM241A"
    assert course["eligible"] is False
    assert course["reasons"] == ["Attendance 70% < 75%"]
    assert course["percentage"] == 70.0
    assert course["registered"] is False


def test_admin_course_eligibility_roster(admin_client, esa):
    """Admin sees every enrolled student's fees, attendance and eligibility for a course."""
    response = admin_client.get(f"/api/admin/esa-eligibility/{esa['course_id']}")
    assert response.status_code == 200
    rows = {row["student_id"]: row for row in response.get_json()["students"]}
    assert rows[esa["students"]["eligible"]]["eligible"] is True
    assert rows[esa["students"]["boundary"]]["eligible"] is True
    assert rows[esa["students"]["unpaid"]]["reasons"] == ["Fees unpaid"]
    assert rows[esa["students"]["shortage"]]["reasons"] == ["Attendance 70% < 75%"]
    assert admin_client.get("/api/admin/esa-eligibility/9999").status_code == 404


# ---------------------------------------------------------------- TC-ESA-07 override


def test_tc_esa_07_override_without_reason_400_then_with_reason_eligible(app, admin_client, esa):
    """TC-ESA-07: no reason -> 400. With reason -> student eligible and an audit row is created."""
    payload = {"student_id": esa["students"]["shortage"], "course_id": esa["course_id"]}

    response = admin_client.post("/api/admin/eligibility-override", json=payload)
    assert response.status_code == 400
    assert "reason is required" in response.get_json()["error"]

    response = admin_client.post(
        "/api/admin/eligibility-override", json={**payload, "reason": "Medical certificate"}
    )
    assert response.status_code == 201
    override_id = response.get_json()["override"]["id"]

    with app.app_context():
        audit = AuditLog.query.filter_by(entity="eligibility_override").one()
        assert audit.entity_id == str(override_id)
        assert audit.user_id == User.query.filter_by(email="admin@pes.edu").one().id
        assert audit.timestamp is not None

    rows = admin_client.get(f"/api/admin/esa-eligibility/{esa['course_id']}").get_json()
    row = next(r for r in rows["students"] if r["student_id"] == payload["student_id"])
    assert row["eligible"] is True
    assert row["override"]["reason"] == "Medical certificate"

    assert register(student_client(app, "shortage"), esa["course_id"]).status_code == 201

    duplicate = admin_client.post(
        "/api/admin/eligibility-override", json={**payload, "reason": "Again"}
    )
    assert duplicate.status_code == 409


def test_override_for_student_not_in_course_is_404(admin_client, esa):
    """The override must be for a course the student is enrolled in."""
    response = admin_client.post(
        "/api/admin/eligibility-override",
        json={
            "student_id": esa["students"]["eligible"],
            "course_id": esa["other_course_id"],
            "reason": "Medical",
        },
    )
    assert response.status_code == 404
