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
                email=f"stu{i}@pes.edu" if i != 1 else "student1@pes.edu",
                semester=4,
                department_id=dept.id,
                section_id=sec.id,
            )
            for i in (1, 2, 3)
        ]
        student_user = User.query.filter_by(email="student1@pes.edu").one()
        students[0].user_id = student_user.id
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

    # Check course marks list
    list_res = client.get(f"/api/faculty/marks/{course_id}")
    assert list_res.status_code == 200
    students_list = list_res.get_json()["students"]
    assert len(students_list) == 2
    s1 = next(s for s in students_list if s["student_id"] == student1_id)
    assert s1["isa1"] == 18.5
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
    """TC-MRK-03: ESA marks for a student not registered for ESA -> HTTP 409, nothing saved."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]
    student2_id = marks_api_setup["student2_id"]

    login(client, marks_api_setup["faculty1_email"])

    # Student 2 is NOT registered for ESA
    res_s2 = client.put(f"/api/faculty/marks/{course_id}/{student2_id}", json={"esa": 35.0})
    assert res_s2.status_code == 409
    assert "not registered for ESA" in res_s2.get_json()["error"]

    # Nothing saved for student 2
    roster = client.get(f"/api/faculty/marks/{course_id}").get_json()["students"]
    s2 = next(s for s in roster if s["student_id"] == student2_id)
    assert s2["esa"] is None
    assert s2["total"] is None

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
    assert marks_log["old_value"] == "ISA-1: 15.0"
    assert marks_log["new_value"] == "ISA-1: 18.0"
    assert marks_log["user_email"] == marks_api_setup["faculty1_email"]
    assert marks_log["timestamp"] is not None


def test_tc_aud_01_swapped_marks_logged_even_if_total_same(client, marks_api_setup):
    """TC-AUD-01: Two marks change but the total stays the same -> one audit row per mark."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]
    url = f"/api/faculty/marks/{course_id}/{student1_id}"

    login(client, marks_api_setup["faculty1_email"])
    assert client.put(url, json={"isa1": 15.0, "isa2": 18.0}).status_code == 200
    res = client.put(url, json={"isa1": 18.0, "isa2": 15.0})
    assert res.status_code == 200
    assert res.get_json()["marks"]["total"] == 33.0
    client.post("/api/auth/logout")

    login(client, "admin@pes.edu")
    logs = client.get("/api/admin/audit-log?entity=marks").get_json()["audit_log"]
    changes = {(log["old_value"], log["new_value"]) for log in logs}
    assert changes == {
        ("ISA-1: 15.0", "ISA-1: 18.0"),
        ("ISA-2: 18.0", "ISA-2: 15.0"),
    }


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


def test_tc_mrk_04_save_marks_persists_grade_and_grade_points(client, marks_api_setup):
    """TC-MRK-04: Saving marks calculates and persists letter grade and grade point."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]

    login(client, marks_api_setup["faculty1_email"])

    # 1. Grade S (>= 90)
    res_s = client.put(
        f"/api/faculty/marks/{course_id}/{student1_id}",
        json={"isa1": 20.0, "isa2": 19.0, "assessment": 10.0, "esa": 45.0},
    )
    assert res_s.status_code == 200
    marks_s = res_s.get_json()["marks"]
    assert marks_s["total"] == 94.0
    assert marks_s["grade"] == "S"
    assert marks_s["grade_point"] == 10

    # 2. Grade A (80-89)
    res_a = client.put(
        f"/api/faculty/marks/{course_id}/{student1_id}",
        json={"isa1": 18.0, "isa2": 18.0, "assessment": 8.0, "esa": 40.0},
    )
    assert res_a.status_code == 200
    marks_a = res_a.get_json()["marks"]
    assert marks_a["total"] == 84.0
    assert marks_a["grade"] == "A"
    assert marks_a["grade_point"] == 9

    # 3. Grade F (< 40)
    res_f = client.put(
        f"/api/faculty/marks/{course_id}/{student1_id}",
        json={"isa1": 10.0, "isa2": 10.0, "assessment": 5.0, "esa": 10.0},
    )
    assert res_f.status_code == 200
    marks_f = res_f.get_json()["marks"]
    assert marks_f["total"] == 35.0
    assert marks_f["grade"] == "F"
    assert marks_f["grade_point"] == 0


def test_tc_mrk_05_student_results_and_sgpa(client, marks_api_setup):
    """TC-MRK-05: Student views results with component marks, letter grades, and SGPA."""
    course_id = marks_api_setup["course_id"]
    student1_id = marks_api_setup["student1_id"]

    # 1. Faculty sets marks for student 1 (total 90 -> Grade S, grade_point 10, credits 4)
    login(client, marks_api_setup["faculty1_email"])
    save_res = client.put(
        f"/api/faculty/marks/{course_id}/{student1_id}",
        json={"isa1": 18.0, "isa2": 18.0, "assessment": 9.0, "esa": 45.0},
    )
    assert save_res.status_code == 200
    client.post("/api/auth/logout")

    # 2. Student 1 logs in and views results
    login(client, "student1@pes.edu")
    results_res = client.get("/api/student/results")
    assert results_res.status_code == 200
    data = results_res.get_json()

    assert data["student"]["email"] == "student1@pes.edu"
    assert len(data["courses"]) >= 1

    c1 = next(c for c in data["courses"] if c["course_id"] == course_id)
    assert c1["code"] == "UE24AM241A"
    assert c1["credits"] == 4
    assert c1["total"] == 90.0
    assert c1["grade"] == "S"
    assert c1["grade_point"] == 10
    assert data["sgpa"] == 10.0
    assert data["total_credits"] == 4
    assert data["earned_credits"] == 4

    # Also test /api/student/marks alias
    alias_res = client.get("/api/student/marks")
    assert alias_res.status_code == 200
    assert alias_res.get_json()["sgpa"] == 10.0


def test_student_results_rbac(client, marks_api_setup):
    """Student results endpoint requires student login (401 unauth, 403 non-student)."""
    # 1. Unauthenticated -> 401
    assert client.get("/api/student/results").status_code == 401

    # 2. Admin -> 403
    login(client, "admin@pes.edu")
    assert client.get("/api/student/results").status_code == 403
    client.post("/api/auth/logout")

    # 3. Faculty -> 403
    login(client, marks_api_setup["faculty1_email"])
    assert client.get("/api/student/results").status_code == 403
