"""Integration tests for Marks API (Issue #15: SRS-F-019, SRS-F-025, TC-MRK-01..03, TC-AUD-01)."""

import pytest

from src.extensions import db
from src.models import (
    AuditLog,
    Course,
    Department,
    Enrollment,
    ExamRegistration,
    Marks,
    Section,
    Student,
    User,
)
from tests.conftest import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD):
    """Log in via authentication endpoint."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def marks_api_setup(app, make_user):
    """Course with assigned faculty, 2 enrolled students (1 ESA-registered), and 1 other faculty."""
    make_user("faculty", email="faculty1@pes.edu")
    make_user("faculty", email="faculty2@pes.edu")
    make_user("admin", email="admin@pes.edu")
    make_user("student", email="student1@pes.edu")

    with app.app_context():
        faculty1 = User.query.filter_by(email="faculty1@pes.edu").one()
        dept = Department(name="CSE-AIML")
        db.session.add(dept)
        db.session.flush()
        sec = Section(name="H", department_id=dept.id)
        db.session.add(sec)
        db.session.flush()

        course = Course(
            code="UE24AM241A",
            name="Software Engineering",
            credits=4,
            department_id=dept.id,
            faculty_id=faculty1.id,
        )
        db.session.add(course)
        db.session.flush()

        students = [
            Student(
                srn=f"PES1UG24AM{i:03d}",
                name=f"Student {i}",
                email=f"stu{i}@pes.edu",
                semester=4,
                department_id=dept.id,
                section_id=sec.id,
            )
            for i in (1, 2, 3)
        ]
        db.session.add_all(students)
        db.session.flush()

        # Enroll students 1 and 2 in course; student 3 is not enrolled
        db.session.add(Enrollment(student_id=students[0].id, course_id=course.id))
        db.session.add(Enrollment(student_id=students[1].id, course_id=course.id))

        # Student 1 is registered for ESA; Student 2 is not
        db.session.add(ExamRegistration(student_id=students[0].id, course_id=course.id))
        db.session.commit()

        return {
            "course_id": course.id,
            "faculty1_email": "faculty1@pes.edu",
            "faculty2_email": "faculty2@pes.edu",
            "student1_id": students[0].id,
            "student2_id": students[1].id,
            "student3_id": students[2].id,
        }


def test_tc_mrk_01_faculty_saves_valid_marks(client, marks_api_setup):
    """TC-MRK-01: Faculty saves valid component marks; total computed and roster reflects marks."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]

    login(client, marks_api_setup["faculty1_email"])

    payload = {"isa1": 18.5, "isa2": 17.0, "assessment": 9.0, "esa": 44.5}
    res = client.put(f"/api/faculty/marks/{course_id}/{student1_id}", json=payload)
    assert res.status_code == 200

    marks_data = res.get_json()["marks"]
    assert marks_data["isa1"] == 18.5
    assert marks_data["isa2"] == 17.0
    assert marks_data["assessment"] == 9.0
    assert marks_data["esa"] == 44.5
    assert marks_data["total"] == 89.0

    # Also test legacy alias /api/marks/<course_id>/<student_id>
    alias_res = client.put(
        f"/api/marks/{course_id}/{student1_id}",
        json={"isa1": 19.0, "isa2": 17.0, "assessment": 9.0, "esa": 44.5},
    )
    assert alias_res.status_code == 200
    assert alias_res.get_json()["marks"]["isa1"] == 19.0
    assert alias_res.get_json()["marks"]["total"] == 89.5

    # Check course marks list
    list_res = client.get(f"/api/faculty/marks/{course_id}")
    assert list_res.status_code == 200
    students_list = list_res.get_json()["students"]
    assert len(students_list) == 2
    s1 = next(s for s in students_list if s["student_id"] == student1_id)
    assert s1["isa1"] == 19.0
    assert s1["is_esa_registered"] is True


def test_tc_mrk_02_invalid_or_out_of_bounds_marks_rejected(client, marks_api_setup):
    """TC-MRK-02: Component boundary violations and non-numeric values rejected with 400."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]

    login(client, marks_api_setup["faculty1_email"])

    cases = [
        ({"isa1": 21}, "ISA-1 must be between 0 and 20"),
        ({"isa1": -1}, "ISA-1 must be between 0 and 20"),
        ({"isa2": 25}, "ISA-2 must be between 0 and 20"),
        ({"assessment": 11}, "Assessment must be between 0 and 10"),
        ({"esa": 55}, "ESA must be between 0 and 50"),
        ({"isa1": "abc"}, "ISA-1 mark must be a number"),
        ({"isa1": True}, "ISA-1 mark must be a number"),
    ]
    for body, expected_msg in cases:
        res = client.put(f"/api/faculty/marks/{course_id}/{student1_id}", json=body)
        assert res.status_code == 400
        assert expected_msg in res.get_json()["error"]


def test_tc_mrk_03_esa_marks_only_for_esa_registered_students(client, marks_api_setup):
    """TC-MRK-03: Entering ESA marks for student not registered for ESA is rejected with 400."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]
    student2_id = marks_api_setup["student2_id"]

    login(client, marks_api_setup["faculty1_email"])

    # Student 2 is NOT registered for ESA
    res_s2 = client.put(f"/api/faculty/marks/{course_id}/{student2_id}", json={"esa": 35.0})
    assert res_s2.status_code == 400
    assert "not registered for ESA" in res_s2.get_json()["error"]

    # Student 2 CAN receive internal marks
    res_s2_isa = client.put(f"/api/faculty/marks/{course_id}/{student2_id}", json={"isa1": 16.0})
    assert res_s2_isa.status_code == 200
    assert res_s2_isa.get_json()["marks"]["isa1"] == 16.0

    # Student 1 IS registered for ESA -> succeeds
    res_s1 = client.put(f"/api/faculty/marks/{course_id}/{student1_id}", json={"esa": 40.0})
    assert res_s1.status_code == 200
    assert res_s1.get_json()["marks"]["esa"] == 40.0


def test_tc_aud_01_marks_change_creates_audit_log_entry(client, marks_api_setup):
    """TC-AUD-01 / SRS-F-025: Changing a mark writes an audit log row visible to Admin."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]

    login(client, marks_api_setup["faculty1_email"])

    # 1. Faculty enters initial mark: 15.0
    res_init = client.put(
        f"/api/faculty/marks/{course_id}/{student1_id}",
        json={"isa1": 15.0},
    )
    assert res_init.status_code == 200

    # 2. Faculty changes the mark from 15.0 to 18.0
    res_change = client.put(
        f"/api/faculty/marks/{course_id}/{student1_id}",
        json={"isa1": 18.0},
    )
    assert res_change.status_code == 200
    client.post("/api/auth/logout")

    # 3. Admin verifies audit log entry
    login(client, "admin@pes.edu")
    audit_res = client.get("/api/admin/audit-log?entity=marks")
    assert audit_res.status_code == 200
    logs = audit_res.get_json()["audit_log"]

    marks_log = next(
        (
            log
            for log in logs
            if log["action"] == "marks changed" and log["entity_id"] == f"{course_id}:{student1_id}"
        ),
        None,
    )
    assert marks_log is not None
    assert marks_log["old_value"] == "15.0"
    assert marks_log["new_value"] == "18.0"
    assert marks_log["user_email"] == marks_api_setup["faculty1_email"]
    assert marks_log["timestamp"] is not None


def test_unauthorized_access_to_marks_api(client, marks_api_setup):
    """RBAC: Non-assigned faculty, Admin, Student, and unauthenticated get 401/403."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]

    url_get = f"/api/faculty/marks/{course_id}"
    url_put = f"/api/faculty/marks/{course_id}/{student1_id}"

    # 1. Unauthenticated -> 401
    assert client.get(url_get).status_code == 401
    assert client.put(url_put, json={"isa1": 15}).status_code == 401

    # 2. Other faculty member -> 403
    login(client, marks_api_setup["faculty2_email"])
    assert client.get(url_get).status_code == 403
    assert client.put(url_put, json={"isa1": 15}).status_code == 403
    client.post("/api/auth/logout")

    # 3. Student -> 403
    login(client, "student1@pes.edu")
    assert client.get(url_get).status_code == 403
    assert client.put(url_put, json={"isa1": 15}).status_code == 403
    client.post("/api/auth/logout")

    # 4. Admin -> 403
    login(client, "admin@pes.edu")
    assert client.get(url_get).status_code == 403
    assert client.put(url_put, json={"isa1": 15}).status_code == 403


def test_non_enrolled_student_marks_rejected_with_400(client, marks_api_setup):
    """Saving marks for a non-enrolled student returns 400."""
    course_id = marks_api_setup["course_id"]
    student3_id = marks_api_setup["student3_id"]

    login(client, marks_api_setup["faculty1_email"])
    res = client.put(f"/api/faculty/marks/{course_id}/{student3_id}", json={"isa1": 15.0})
    assert res.status_code == 400
    assert "not enrolled" in res.get_json()["error"]
