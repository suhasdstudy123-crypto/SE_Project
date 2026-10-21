"""Integration tests for the Audit Log API and event logging (Issue #6: SRS-F-025, TC-FEE-01)."""

from tests.conftest import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD):
    """Log in via authentication endpoint."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


def setup_department_and_student(client):
    """Helper: create department, section, and student for fee testing."""
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

    return dept, sec, student


def test_tc_fee_01_paid_to_unpaid_creates_audit_log_entry(client, make_user):
    """TC-FEE-01 / SRS-F-025: Changing status from PAID to UNPAID creates an audit log row."""
    make_user("admin", email="admin@pes.edu")
    login(client, "admin@pes.edu")
    _, _, student = setup_department_and_student(client)

    student_id = student["id"]
    fee_url = f"/api/admin/fees/{student_id}"

    # 1. Mark as PAID initially
    res_paid = client.put(fee_url, json={"semester": 3, "status": "PAID"})
    assert res_paid.status_code == 200
    assert res_paid.get_json()["fee"]["status"] == "PAID"

    # 2. Change status from PAID to UNPAID
    res_unpaid = client.put(fee_url, json={"semester": 3, "status": "UNPAID"})
    assert res_unpaid.status_code == 200
    assert res_unpaid.get_json()["fee"]["status"] == "UNPAID"

    # 3. Query audit log and verify audit row for PAID -> UNPAID change
    audit_res = client.get("/api/admin/audit-log?entity=fee_status")
    assert audit_res.status_code == 200
    logs = audit_res.get_json()["audit_log"]

    change_log = next(
        (
            l
            for l in logs
            if l["action"] == "fee status changed"
            and l["old_value"] == "PAID"
            and l["new_value"] == "UNPAID"
        ),
        None,
    )
    assert change_log is not None, "Expected audit log row for PAID -> UNPAID fee change"
    assert change_log["entity"] == "fee_status"
    assert change_log["entity_id"] == f"{student_id}:3"
    assert change_log["user_email"] == "admin@pes.edu"
    assert change_log["timestamp"] is not None


def test_admin_audit_log_filters_by_action_and_limit(client, make_user):
    """Audit log endpoint supports entity, action, and limit query filters."""
    make_user("admin", email="admin@pes.edu")
    login(client, "admin@pes.edu")
    _, _, student = setup_department_and_student(client)

    student_id = student["id"]
    client.put(f"/api/admin/fees/{student_id}", json={"semester": 1, "status": "PAID"})
    client.put(f"/api/admin/fees/{student_id}", json={"semester": 1, "status": "UNPAID"})

    # Filter by action
    action_res = client.get("/api/admin/audit-log?action=fee+status+changed")
    assert action_res.status_code == 200
    for log in action_res.get_json()["audit_log"]:
        assert log["action"] == "fee status changed"

    # Limit parameter
    limit_res = client.get("/api/admin/audit-log?limit=1")
    assert limit_res.status_code == 200
    assert len(limit_res.get_json()["audit_log"]) == 1


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
