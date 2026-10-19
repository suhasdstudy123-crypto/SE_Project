"""Integration tests for the Audit Log API and event logging (Issue #6: SRS-F-025, TC-AUD-01)."""

from tests.conftest import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD):
    """Log in via authentication endpoint."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


def setup_department_course_student(client):
    """Helper: create department, section, student, and course for marks testing."""
    dept = client.post("/api/departments", json={"name": "Computer Science"}).get_json()[
        "department"
    ]
    sec = client.post(f"/api/departments/{dept['id']}/sections", json={"name": "A"}).get_json()[
        "section"
    ]
    student = client.post(
        "/api/admin/students",
        json={
            "srn": "PES1UG24CS001",
            "name": "Ananya Sharma",
            "email": "ananya@pes.edu",
            "semester": 3,
            "department_id": dept["id"],
            "section_id": sec["id"],
        },
    ).get_json()["student"]

    course = client.post(
        "/api/admin/courses",
        json={
            "code": "CS301",
            "name": "Data Structures",
            "credits": 4,
            "department_id": dept["id"],
            "semester": 3,
        },
    ).get_json()["course"]

    return dept, sec, student, course


def test_tc_aud_01_faculty_changes_mark_generates_audit_log_entry(client, make_user):
    """TC-AUD-01: Faculty changes a mark from 15 to 18 -> Audit row with user, action, old 15, new 18, timestamp."""
    make_user("admin", email="admin@pes.edu")
    make_user("faculty", email="prof@pes.edu")

    # 1. Admin sets up department, student, and course
    login(client, "admin@pes.edu")
    _, _, student, course = setup_department_course_student(client)
    client.post("/api/auth/logout")

    # 2. Faculty logs in and enters initial mark: 15
    login(client, "prof@pes.edu")
    res_init = client.put(
        f"/api/marks/{course['id']}/{student['id']}",
        json={"isa1": 15},
    )
    assert res_init.status_code == 200
    assert res_init.get_json()["marks"]["isa1"] == 15.0

    # 3. Faculty changes the mark from 15 to 18 (TC-AUD-01)
    res_change = client.put(
        f"/api/marks/{course['id']}/{student['id']}",
        json={"isa1": 18},
    )
    assert res_change.status_code == 200
    assert res_change.get_json()["marks"]["isa1"] == 18.0
    client.post("/api/auth/logout")

    # 4. Admin opens /api/admin/audit-log and inspects the recorded audit trail
    login(client, "admin@pes.edu")
    audit_res = client.get("/api/admin/audit-log")
    assert audit_res.status_code == 200
    logs = audit_res.get_json()["audit_log"]

    # Locate the "marks changed" log row
    marks_change_log = next(
        (
            log
            for log in logs
            if log["action"] == "marks changed"
            and log["entity_id"] == f"{course['id']}:{student['id']}"
        ),
        None,
    )
    assert marks_change_log is not None, "Expected audit log row for marks changed"
    assert marks_change_log["old_value"] == "15.0"
    assert marks_change_log["new_value"] == "18.0"
    assert marks_change_log["user_email"] == "prof@pes.edu"
    assert marks_change_log["timestamp"] is not None


def test_fee_status_update_generates_audit_log_entry(client, make_user):
    """Fee status changes are recorded in the audit trail (SRS-F-025)."""
    make_user("admin", email="admin@pes.edu")
    login(client, "admin@pes.edu")
    _, _, student, _ = setup_department_course_student(client)

    # Set initial fee status
    client.put(f"/api/admin/fees/{student['id']}", json={"semester": 3, "status": "UNPAID"})

    # Change fee status to PAID
    client.put(f"/api/admin/fees/{student['id']}", json={"semester": 3, "status": "PAID"})

    # Inspect audit log
    audit_res = client.get("/api/admin/audit-log?entity=fee_status")
    assert audit_res.status_code == 200
    logs = audit_res.get_json()["audit_log"]

    fee_log = next((l for l in logs if l["action"] == "fee status changed"), None)
    assert fee_log is not None
    assert fee_log["old_value"] == "UNPAID"
    assert fee_log["new_value"] == "PAID"
    assert fee_log["user_email"] == "admin@pes.edu"


def test_non_admin_cannot_access_audit_log(client, make_user):
    """Students and Faculty cannot access the admin audit log (TC-SEC-02)."""
    make_user("faculty", email="faculty@pes.edu")
    make_user("student", email="student@pes.edu")

    # Unauthenticated -> 401
    assert client.get("/api/admin/audit-log").status_code == 401

    # Student -> 403
    login(client, "student@pes.edu")
    assert client.get("/api/admin/audit-log").status_code == 403
    client.post("/api/auth/logout")

    # Faculty -> 403
    login(client, "faculty@pes.edu")
    assert client.get("/api/admin/audit-log").status_code == 403
