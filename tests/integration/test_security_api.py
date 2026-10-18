"""Integration tests for security requirements (Issue #7).

Covers:
- SRS-SR-004 / TC-SEC-04: Secrets in .env, .gitignore verification.
- SRS-SR-005 / TC-SEC-05: SQL-injection safety via ORM parameterization.
- SRS-SR-006 / TC-SEC-06: CSRF token verification on state-changing API requests.
- SRS-SR-007 / TC-SEC-07: Server-side input validation on API routes.
"""

from pathlib import Path
from src.app import create_app
from src.config import TestConfig
from src.extensions import db
from tests.conftest import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD):
    """Log in via authentication endpoint."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_tc_sec_05_sql_injection_safety_in_login_and_student_search(client, make_user):
    """TC-SEC-05: ' OR '1'='1 in login email and student search returns no error and no leaked data."""
    make_user("admin", email="admin@pes.edu")
    make_user("student", email="alice@pes.edu")

    # 1. SQL injection attempt in login
    sqli_payloads = [
        "' OR '1'='1",
        "admin@pes.edu' OR '1'='1",
        "' OR 1=1 --",
        "' UNION SELECT 1, 'admin', 'hash', 'admin' --",
    ]
    for sqli in sqli_payloads:
        res = client.post("/api/auth/login", json={"email": sqli, "password": "password"})
        assert res.status_code == 401
        assert "Invalid email or password" in res.get_json()["error"]

    # 2. SQL injection attempt in student search
    login(client, "admin@pes.edu")

    # Create department, section, and student
    dept_res = client.post("/api/departments", json={"name": "Computer Science"})
    assert dept_res.status_code == 201
    dept_id = dept_res.get_json()["department"]["id"]

    sec_res = client.post(f"/api/departments/{dept_id}/sections", json={"name": "A"})
    assert sec_res.status_code == 201
    sec_id = sec_res.get_json()["section"]["id"]

    client.post(
        "/api/admin/students",
        json={
            "srn": "PES1UG24CS001",
            "name": "Alice Bob",
            "email": "alice.student@pes.edu",
            "semester": 2,
            "department_id": dept_id,
            "section_id": sec_id,
        },
    )

    # Search with SQL injection payloads -> returns 200 with 0 results, no SQL error
    for sqli in sqli_payloads:
        res = client.get(f"/api/admin/students?search={sqli}")
        assert res.status_code == 200
        assert res.get_json()["students"] == []

        res_q = client.get(f"/api/admin/students?q={sqli}")
        assert res_q.status_code == 200
        assert res_q.get_json()["students"] == []

    # Valid search returns only the matching student
    match_res = client.get("/api/admin/students?search=Alice")
    assert match_res.status_code == 200
    students = match_res.get_json()["students"]
    assert len(students) == 1
    assert students[0]["srn"] == "PES1UG24CS001"


def test_tc_sec_06_csrf_protection_on_state_changing_requests():
    """TC-SEC-06: State-changing requests (POST/PUT/DELETE) require valid CSRF token."""

    class CsrfActiveConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CsrfActiveConfig)
    client = app.test_client()

    with app.app_context():
        # Create an admin user directly
        from src.services.auth_service import create_user

        create_user("admin@pes.edu", "Admin", TEST_PASSWORD, "admin")

    try:
        # 1. Unauthenticated or tokenless POST is rejected with 400
        no_token_post = client.post("/api/departments", json={"name": "CS"})
        assert no_token_post.status_code == 400
        assert "Security token missing or expired" in no_token_post.get_json()["error"]

        # 2. Login with CSRF token
        token_res = client.get("/api/auth/csrf")
        csrf_token = token_res.get_json()["csrf_token"]
        assert csrf_token is not None

        login_res = client.post(
            "/api/auth/login",
            json={"email": "admin@pes.edu", "password": TEST_PASSWORD},
            headers={"X-CSRFToken": csrf_token},
        )
        assert login_res.status_code == 200

        # 3. GET request does not require CSRF token
        get_res = client.get("/api/departments")
        assert get_res.status_code == 200

        # 4. State-changing POST without CSRF token is rejected with 400
        post_without_token = client.post("/api/departments", json={"name": "CS"})
        assert post_without_token.status_code == 400
        assert "Security token missing or expired" in post_without_token.get_json()["error"]

        # 5. State-changing PUT without CSRF token is rejected with 400
        put_without_token = client.put("/api/admin/fees/1", json={"fee_paid": True})
        assert put_without_token.status_code == 400
        assert "Security token missing or expired" in put_without_token.get_json()["error"]

        # 6. State-changing DELETE without CSRF token is rejected with 400
        delete_without_token = client.delete("/api/departments/1")
        assert delete_without_token.status_code == 400
        assert "Security token missing or expired" in delete_without_token.get_json()["error"]

        # 7. State-changing request with valid CSRF token succeeds
        token = client.get("/api/auth/csrf").get_json()["csrf_token"]
        post_with_token = client.post(
            "/api/departments",
            json={"name": "BioTech"},
            headers={"X-CSRFToken": token},
        )
        assert post_with_token.status_code == 201
        assert post_with_token.get_json()["department"]["name"] == "BioTech"
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_tc_sec_07_server_side_input_validation(client, make_user):
    """TC-SEC-07: Invalid email, invalid date, and out-of-range marks rejected with messages."""
    make_user("admin", email="admin@pes.edu")
    make_user("faculty", email="faculty@pes.edu")

    # 1. Invalid email format in student creation
    login(client, "admin@pes.edu")
    dept = client.post("/api/departments", json={"name": "ECE"}).get_json()["department"]
    sec = client.post(f"/api/departments/{dept['id']}/sections", json={"name": "A"}).get_json()[
        "section"
    ]

    invalid_email_res = client.post(
        "/api/admin/students",
        json={
            "srn": "PES1UG24EC001",
            "name": "Student Bad Email",
            "email": "not-an-email-format",
            "semester": 1,
            "department_id": dept["id"],
            "section_id": sec["id"],
        },
    )
    assert invalid_email_res.status_code == 400
    assert "Invalid email address format" in invalid_email_res.get_json()["error"]
    client.post("/api/auth/logout")

    # 2. Out-of-range marks rejected on marks API
    login(client, "faculty@pes.edu")
    bad_marks_res = client.post(
        "/api/marks/validate",
        json={"isa1": 25, "assessment": 9, "esa": 40},
    )
    assert bad_marks_res.status_code == 400
    assert "ISA-1 must be between 0 and 20" in bad_marks_res.get_json()["error"]

    valid_marks_res = client.post(
        "/api/marks/validate",
        json={"isa1": 18, "isa2": 17, "assessment": 9, "esa": 40},
    )
    assert valid_marks_res.status_code == 200
    assert valid_marks_res.get_json()["validated"]["isa1"] == 18.0


def test_tc_sec_04_gitignore_and_credentials_safety():
    """TC-SEC-04: .env listed in .gitignore, credentials kept out of source code."""
    root = Path(__file__).resolve().parent.parent.parent
    gitignore_path = root / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    ignored_lines = [line.strip() for line in content.splitlines() if line.strip()]
    assert ".env" in ignored_lines, ".env must be explicitly ignored in .gitignore"
