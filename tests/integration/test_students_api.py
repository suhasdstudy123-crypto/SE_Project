"""Integration tests for Admin student management."""

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
def department_and_section(admin_client):
    """Create a department and a section for student tests."""
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

    return department_id, section_id


def student_payload(department_id, section_id, **overrides):
    """Return a valid student payload."""
    payload = {
        "srn": "PES1UG24CS001",
        "name": "Test Student",
        "email": "student1@example.com",
        "semester": 2,
        "department_id": department_id,
        "section_id": section_id,
    }
    payload.update(overrides)
    return payload


def create_student(client, department_id, section_id, **overrides):
    """Create one student and return its response."""
    return client.post(
        "/api/admin/students",
        json=student_payload(department_id, section_id, **overrides),
    )


def test_unauthenticated_user_cannot_list_students(client):
    """Unauthenticated requests should receive 401."""
    response = client.get("/api/admin/students")
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["faculty", "student"])
def test_non_admin_cannot_manage_students(client, make_user, role):
    """Faculty and Student users must receive 403."""
    make_user(role)
    assert login(client, f"{role}@pes.edu").status_code == 200

    assert client.get("/api/admin/students").status_code == 403
    assert client.post("/api/admin/students", json={}).status_code == 403


def test_tc_stu_02_admin_can_create_and_list_students(admin_client, department_and_section):
    """Admin can create a student and find it in the list."""
    department_id, section_id = department_and_section

    response = create_student(admin_client, department_id, section_id)
    assert response.status_code == 201
    student = response.get_json()["student"]
    assert student["srn"] == "PES1UG24CS001"
    assert student["email"] == "student1@example.com"
    student_id = student["id"]

    response = admin_client.get("/api/admin/students")
    assert response.status_code == 200
    assert any(item["id"] == student_id for item in response.get_json()["students"])


def test_tc_stu_03_duplicate_srn_is_rejected(admin_client, department_and_section):
    """An SRN cannot be reused."""
    department_id, section_id = department_and_section

    assert create_student(admin_client, department_id, section_id).status_code == 201

    response = create_student(
        admin_client,
        department_id,
        section_id,
        email="another@example.com",
    )
    assert response.status_code == 400
    assert "SRN already exists" in response.get_json()["error"]


def test_tc_stu_03_duplicate_email_is_rejected(admin_client, department_and_section):
    """An email address cannot be reused."""
    department_id, section_id = department_and_section

    assert create_student(admin_client, department_id, section_id).status_code == 201

    response = create_student(
        admin_client,
        department_id,
        section_id,
        srn="PES1UG24CS002",
        email="STUDENT1@example.com",
    )
    assert response.status_code == 400
    assert "Email already exists" in response.get_json()["error"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"srn": ""},
        {"name": ""},
        {"email": ""},
        {"semester": 0},
        {"semester": 9},
        {"semester": True},
    ],
)
def test_invalid_student_fields_are_rejected(admin_client, department_and_section, overrides):
    """Missing required values and invalid semesters are rejected."""
    department_id, section_id = department_and_section

    response = create_student(admin_client, department_id, section_id, **overrides)
    assert response.status_code == 400


def test_student_cannot_use_section_from_another_department(admin_client, department_and_section):
    """The selected section must belong to the selected department."""
    _, first_section_id = department_and_section

    response = admin_client.post(
        "/api/departments",
        json={"name": "Electronics"},
    )
    second_department_id = response.get_json()["department"]["id"]

    response = create_student(
        admin_client,
        second_department_id,
        first_section_id,
    )
    assert response.status_code == 400
    assert "does not belong" in response.get_json()["error"]


def test_tc_stu_04_admin_can_update_student(admin_client, department_and_section):
    """Admin can update a student's details."""
    department_id, section_id = department_and_section
    response = create_student(admin_client, department_id, section_id)
    student_id = response.get_json()["student"]["id"]

    response = admin_client.put(
        f"/api/admin/students/{student_id}",
        json={"name": "Updated Student"},
    )
    assert response.status_code == 200
    assert response.get_json()["student"]["name"] == "Updated Student"


def test_update_rejects_duplicate_email(admin_client, department_and_section):
    """Updating a student cannot reuse another student's email."""
    department_id, section_id = department_and_section

    first = create_student(admin_client, department_id, section_id)
    assert first.status_code == 201

    second = create_student(
        admin_client,
        department_id,
        section_id,
        srn="PES1UG24CS002",
        email="student2@example.com",
    )
    assert second.status_code == 201
    second_id = second.get_json()["student"]["id"]

    response = admin_client.put(
        f"/api/admin/students/{second_id}",
        json={"email": "student1@example.com"},
    )
    assert response.status_code == 400
    assert "Email already exists" in response.get_json()["error"]


def test_tc_stu_04_admin_can_delete_student(admin_client, department_and_section):
    """Admin can delete a student record."""
    department_id, section_id = department_and_section
    response = create_student(admin_client, department_id, section_id)
    student_id = response.get_json()["student"]["id"]

    response = admin_client.delete(f"/api/admin/students/{student_id}")
    assert response.status_code == 200

    response = admin_client.delete(f"/api/admin/students/{student_id}")
    assert response.status_code == 404


def test_missing_student_returns_404(admin_client):
    """Updating or deleting a nonexistent student returns 404."""
    assert (
        admin_client.put(
            "/api/admin/students/9999",
            json={"name": "Nobody"},
        ).status_code
        == 404
    )
    assert admin_client.delete("/api/admin/students/9999").status_code == 404
