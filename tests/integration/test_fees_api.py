"""Integration tests for Admin fee-status management."""

import pytest

from tests.conftest import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD):
    """Log in through the authentication API."""
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


@pytest.fixture
def admin_client(client, make_user):
    """Return a client authenticated as Admin."""
    make_user("admin")
    response = login(client, "admin@pes.edu")
    assert response.status_code == 200
    return client


@pytest.fixture
def student_record(admin_client):
    """Create a department, section, and student for fee tests."""
    response = admin_client.post(
        "/api/departments",
        json={"name": "Computer Science"},
    )
    assert response.status_code == 201
    department_id = response.get_json()["department"]["id"]

    response = admin_client.post(
        f"/api/departments/{department_id}/sections",
        json={"name": "A"},
    )
    assert response.status_code == 201
    section_id = response.get_json()["section"]["id"]

    response = admin_client.post(
        "/api/admin/students",
        json={
            "srn": "PES1UG24CS001",
            "name": "Test Student",
            "email": "student@example.com",
            "semester": 2,
            "department_id": department_id,
            "section_id": section_id,
        },
    )
    assert response.status_code == 201
    return response.get_json()["student"]


def test_unauthenticated_user_cannot_list_fees(client):
    """Unauthenticated requests are rejected."""
    assert client.get("/api/admin/fees").status_code == 401


@pytest.mark.parametrize("role", ["faculty", "student"])
def test_tc_fee_02_non_admin_cannot_manage_fees(client, make_user, role):
    """Faculty and Students receive HTTP 403."""
    make_user(role)
    assert login(client, f"{role}@pes.edu").status_code == 200

    assert client.get("/api/admin/fees").status_code == 403
    assert (
        client.put(
            "/api/admin/fees/1",
            json={"semester": 1, "status": "PAID"},
        ).status_code
        == 403
    )


def test_tc_fee_01_admin_can_set_paid_status(admin_client, student_record):
    """Admin can mark a student's semester fees as PAID."""
    student_id = student_record["id"]

    response = admin_client.put(
        f"/api/admin/fees/{student_id}",
        json={"semester": 2, "status": "PAID"},
    )

    assert response.status_code == 200
    assert response.get_json()["fee"]["student_id"] == student_id
    assert response.get_json()["fee"]["semester"] == 2
    assert response.get_json()["fee"]["status"] == "PAID"


def test_tc_fee_01_admin_can_update_fee_status(admin_client, student_record):
    """Updating a semester status changes the existing record."""
    student_id = student_record["id"]
    url = f"/api/admin/fees/{student_id}"

    first = admin_client.put(
        url,
        json={"semester": 2, "status": "PAID"},
    )
    assert first.status_code == 200

    second = admin_client.put(
        url,
        json={"semester": 2, "status": "UNPAID"},
    )
    assert second.status_code == 200
    assert second.get_json()["fee"]["status"] == "UNPAID"

    fees = admin_client.get("/api/admin/fees?semester=2")
    matching = [fee for fee in fees.get_json()["fees"] if fee["student_id"] == student_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "UNPAID"


def test_admin_can_set_different_semesters(admin_client, student_record):
    """A student can have separate fee statuses for different semesters."""
    student_id = student_record["id"]

    for semester, status in [(1, "PAID"), (2, "UNPAID")]:
        response = admin_client.put(
            f"/api/admin/fees/{student_id}",
            json={"semester": semester, "status": status},
        )
        assert response.status_code == 200

    response = admin_client.get("/api/admin/fees")
    records = [fee for fee in response.get_json()["fees"] if fee["student_id"] == student_id]
    assert len(records) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"semester": 0, "status": "PAID"},
        {"semester": 9, "status": "PAID"},
        {"semester": True, "status": "PAID"},
        {"semester": 1, "status": "PENDING"},
        {"semester": 1, "status": ""},
    ],
)
def test_invalid_fee_status_is_rejected(admin_client, student_record, payload):
    """Invalid semesters and status values receive HTTP 400."""
    response = admin_client.put(
        f"/api/admin/fees/{student_record['id']}",
        json=payload,
    )
    assert response.status_code == 400


def test_missing_student_returns_404(admin_client):
    """A nonexistent student cannot receive a fee record."""
    response = admin_client.put(
        "/api/admin/fees/999999",
        json={"semester": 1, "status": "PAID"},
    )
    assert response.status_code == 404


def test_invalid_semester_filter_is_rejected(admin_client):
    """Invalid semester filters receive HTTP 400."""
    assert admin_client.get("/api/admin/fees?semester=abc").status_code == 400
