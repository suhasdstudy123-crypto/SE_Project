"""Integration tests for marking and correcting attendance (Issue #13)."""

from datetime import date, timedelta

import pytest

from src.extensions import db
from src.models import (
    Attendance,
    AuditLog,
    Course,
    Department,
    Enrollment,
    Section,
    Student,
    User,
)
from tests.conftest import TEST_PASSWORD

CLASS_DATE = "2026-10-12"


def login(client, email, password=TEST_PASSWORD):
    """Log in through the authentication API."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def course_setup(app, make_user):
    """A course taught by faculty1, with 3 enrolled students and 1 student not enrolled."""
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
            db.session.add(Enrollment(student_id=student.id, course_id=course.id))
        db.session.commit()
        return {
            "course_id": course.id,
            "enrolled": [student.id for student in students[:3]],
            "not_enrolled": students[3].id,
            "faculty_id": faculty.id,
        }


@pytest.fixture
def faculty_client(app, course_setup):  # pylint: disable=unused-argument
    """A client logged in as the course's assigned faculty member."""
    client = app.test_client()
    assert login(client, "faculty1@pes.edu").status_code == 200
    return client


def mark(client, course_id, records, class_date=CLASS_DATE):
    """Save attendance for a class date."""
    return client.put(
        f"/api/faculty/attendance/{course_id}", json={"date": class_date, "records": records}
    )


def test_roster_defaults_to_all_present(faculty_client, course_setup):
    """Before saving, every enrolled student is listed as present (SAD 4.5, NF-002)."""
    response = faculty_client.get(
        f"/api/faculty/attendance/{course_setup['course_id']}?date={CLASS_DATE}"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["recorded"] is False
    assert [row["student_id"] for row in data["students"]] == course_setup["enrolled"]
    assert all(row["present"] for row in data["students"])


def test_tc_att_01_assigned_faculty_marks_and_other_faculty_is_forbidden(
    app, faculty_client, course_setup
):
    """TC-ATT-01: 3 rows saved for the date; a different faculty member gets HTTP 403."""
    course_id = course_setup["course_id"]
    first, second, third = course_setup["enrolled"]
    records = [
        {"student_id": first, "present": True},
        {"student_id": second, "present": False},
        {"student_id": third, "present": True},
    ]
    response = mark(faculty_client, course_id, records)
    assert response.status_code == 200
    assert response.get_json() == {"date": CLASS_DATE, "saved": 3, "corrected": 0}

    with app.app_context():
        rows = Attendance.query.filter_by(course_id=course_id, date=date(2026, 10, 12)).all()
        assert len(rows) == 3
        assert {row.student_id: row.present for row in rows} == {
            first: True,
            second: False,
            third: True,
        }

    other = app.test_client()
    login(other, "faculty2@pes.edu")
    assert mark(other, course_id, records).status_code == 403
    assert other.get(f"/api/faculty/attendance/{course_id}?date={CLASS_DATE}").status_code == 403


def test_tc_att_02_correction_updates_value_and_writes_audit_row(app, faculty_client, course_setup):
    """TC-ATT-02: changing absent -> present updates the row and creates an audit-log row."""
    course_id = course_setup["course_id"]
    student_id = course_setup["enrolled"][0]
    mark(faculty_client, course_id, [{"student_id": student_id, "present": False}])

    response = mark(faculty_client, course_id, [{"student_id": student_id, "present": True}])
    assert response.status_code == 200
    assert response.get_json()["corrected"] == 1

    reopened = faculty_client.get(f"/api/faculty/attendance/{course_id}?date={CLASS_DATE}")
    assert reopened.get_json()["recorded"] is True
    row = next(r for r in reopened.get_json()["students"] if r["student_id"] == student_id)
    assert row["present"] is True

    with app.app_context():
        audits = AuditLog.query.filter_by(entity="attendance").all()
        assert len(audits) == 1
        assert audits[0].user_id == course_setup["faculty_id"]
        assert audits[0].action == "attendance changed"
        assert (audits[0].old_value, audits[0].new_value) == ("absent", "present")
        assert audits[0].timestamp is not None


def test_saving_same_values_again_creates_no_audit_rows(app, faculty_client, course_setup):
    """Re-saving unchanged attendance is not a correction."""
    course_id = course_setup["course_id"]
    records = [{"student_id": sid, "present": True} for sid in course_setup["enrolled"]]
    mark(faculty_client, course_id, records)
    response = mark(faculty_client, course_id, records)
    assert response.get_json()["corrected"] == 0
    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Attendance.query.count() == 3


@pytest.mark.parametrize("role", ["admin", "student"])
def test_only_faculty_can_use_attendance_api(client, make_user, course_setup, role):
    """Admin and Student get HTTP 403 on /api/faculty/attendance (SR-002)."""
    make_user(role)
    login(client, f"{role}@pes.edu")
    course_id = course_setup["course_id"]
    assert client.get(f"/api/faculty/attendance/{course_id}?date={CLASS_DATE}").status_code == 403
    assert mark(client, course_id, [{"student_id": 1, "present": True}]).status_code == 403


def test_student_not_enrolled_is_rejected_and_nothing_saved(app, faculty_client, course_setup):
    """A record for a student outside the course fails the whole save."""
    records = [
        {"student_id": course_setup["enrolled"][0], "present": True},
        {"student_id": course_setup["not_enrolled"], "present": True},
    ]
    response = mark(faculty_client, course_setup["course_id"], records)
    assert response.status_code == 400
    assert "not enrolled" in response.get_json()["error"]
    with app.app_context():
        assert Attendance.query.count() == 0


@pytest.mark.parametrize(
    "class_date",
    ["", "12-10-2026", "2026-02-30", (date.today() + timedelta(days=1)).isoformat(), None],
)
def test_invalid_or_future_dates_are_rejected(faculty_client, course_setup, class_date):
    """Dates are validated on the server (SR-007)."""
    student_id = course_setup["enrolled"][0]
    response = mark(
        faculty_client,
        course_setup["course_id"],
        [{"student_id": student_id, "present": True}],
        class_date=class_date,
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "records",
    [
        [],
        "all",
        [{"student_id": "1", "present": True}],
        [{"present": True}],
        ["x"],
    ],
)
def test_invalid_records_are_rejected(faculty_client, course_setup, records):
    """Malformed records get HTTP 400."""
    assert mark(faculty_client, course_setup["course_id"], records).status_code == 400


def test_invalid_present_value_and_duplicates_are_rejected(faculty_client, course_setup):
    """present must be a boolean, and a student may appear only once."""
    course_id = course_setup["course_id"]
    student_id = course_setup["enrolled"][0]
    assert (
        mark(faculty_client, course_id, [{"student_id": student_id, "present": "yes"}]).status_code
        == 400
    )
    duplicate = [
        {"student_id": student_id, "present": True},
        {"student_id": student_id, "present": False},
    ]
    assert mark(faculty_client, course_id, duplicate).status_code == 400


def test_non_object_body_and_missing_course(faculty_client, course_setup):
    """A non-JSON-object body is a 400; an unknown course is a 404."""
    url = f"/api/faculty/attendance/{course_setup['course_id']}"
    assert faculty_client.put(url, json=["not", "an", "object"]).status_code == 400
    assert faculty_client.get(f"/api/faculty/attendance/9999?date={CLASS_DATE}").status_code == 404
    assert mark(faculty_client, 9999, [{"student_id": 1, "present": True}]).status_code == 404


def test_tc_att_03_attendance_percentage_and_shortage_flag(app, faculty_client, course_setup):
    """TC-ATT-03: Attendance % = present/held*100; <75% flagged as shortage, exactly 75% not flagged (SRS-F-013, F-014)."""
    course_id = course_setup["course_id"]
    first, second, third = course_setup["enrolled"]

    # Before any class is recorded: 0 classes gives 0.0% and no shortage without error
    initial = faculty_client.get(f"/api/faculty/attendance/{course_id}?date=2026-10-01")
    assert initial.status_code == 200
    for row in initial.get_json()["students"]:
        assert row["held"] == 0
        assert row["attended"] == 0
        assert row["percentage"] == 0.0
        assert row["shortage"] is False

    # Mark 20 class dates with boundary conditions:
    # Student 1: 18 present (90.0% -> shortage False)
    # Student 2: 15 present (75.0% -> exactly 75% boundary, shortage False)
    # Student 3: 14 present (70.0% -> below 75%, shortage True)
    present_counts = {first: 18, second: 15, third: 14}
    for day in range(1, 21):
        class_date = f"2026-09-{day:02d}"
        records = [
            {"student_id": sid, "present": day <= present_counts[sid]}
            for sid in course_setup["enrolled"]
        ]
        res = mark(faculty_client, course_id, records, class_date=class_date)
        assert res.status_code == 200

    # Query attendance on the faculty route
    response = faculty_client.get(f"/api/faculty/attendance/{course_id}?date=2026-09-20")
    assert response.status_code == 200
    by_id = {row["student_id"]: row for row in response.get_json()["students"]}

    assert by_id[first]["held"] == 20
    assert by_id[first]["attended"] == 18
    assert by_id[first]["percentage"] == 90.0
    assert by_id[first]["shortage"] is False

    assert by_id[second]["held"] == 20
    assert by_id[second]["attended"] == 15
    assert by_id[second]["percentage"] == 75.0
    assert by_id[second]["shortage"] is False

    assert by_id[third]["held"] == 20
    assert by_id[third]["attended"] == 14
    assert by_id[third]["percentage"] == 70.0
    assert by_id[third]["shortage"] is True


def test_tc_att_04_student_attendance_view_and_rbac(app, client, make_user, course_setup):
    """TC-ATT-04: Student views own attendance % per course; roles enforced (SRS-F-013, F-014, F-021)."""
    course_id = course_setup["course_id"]
    first, _second, third = course_setup["enrolled"]

    # Mark 10 classes: first has 9 present (90%), third has 7 present (70%)
    faculty = app.test_client()
    login(faculty, "faculty1@pes.edu")
    for day in range(1, 11):
        class_date = f"2026-08-{day:02d}"
        records = [
            {"student_id": first, "present": day <= 9},
            {"student_id": third, "present": day <= 7},
        ]
        mark(faculty, course_id, records, class_date=class_date)

    # Student 1 logs in and views own attendance
    student1_client = app.test_client()
    make_user("student", email="student1@pes.edu")
    with app.app_context():
        stu1 = db.session.get(Student, first)
        u1 = User.query.filter_by(email="student1@pes.edu").one()
        stu1.user_id = u1.id
        db.session.commit()

    login(student1_client, "student1@pes.edu")
    res1 = student1_client.get("/api/student/attendance")
    assert res1.status_code == 200
    courses1 = res1.get_json()["attendance"]
    assert len(courses1) == 1
    assert courses1[0]["course_code"] == "UE24AM241A"
    assert courses1[0]["percentage"] == 90.0
    assert courses1[0]["shortage"] is False
    assert courses1[0]["held"] == 10
    assert courses1[0]["attended"] == 9

    # Student 1 detail view for this course
    detail1 = student1_client.get(f"/api/student/attendance/{course_id}")
    assert detail1.status_code == 200
    assert detail1.get_json()["percentage"] == 90.0
    assert len(detail1.get_json()["records"]) == 10

    # Student 3 logs in and views own attendance: has shortage flag (70%)
    student3_client = app.test_client()
    make_user("student", email="student3@pes.edu")
    with app.app_context():
        stu3 = db.session.get(Student, third)
        u3 = User.query.filter_by(email="student3@pes.edu").one()
        stu3.user_id = u3.id
        db.session.commit()

    login(student3_client, "student3@pes.edu")
    res3 = student3_client.get("/api/student/attendance")
    assert res3.status_code == 200
    courses3 = res3.get_json()["attendance"]
    assert len(courses3) == 1
    assert courses3[0]["percentage"] == 70.0
    assert courses3[0]["shortage"] is True

    # Student without linked student record gets empty list
    make_user("student", email="unlinked@pes.edu")
    unlinked_client = app.test_client()
    login(unlinked_client, "unlinked@pes.edu")
    assert unlinked_client.get("/api/student/attendance").get_json() == {"attendance": []}

    # RBAC: Admin and Faculty get HTTP 403 on /api/student/attendance
    admin_client = app.test_client()
    make_user("admin", email="admin@pes.edu")
    login(admin_client, "admin@pes.edu")
    assert admin_client.get("/api/student/attendance").status_code == 403

    assert faculty.get("/api/student/attendance").status_code == 403
