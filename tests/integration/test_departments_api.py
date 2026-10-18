"""Integration tests for department and section management."""

import pytest

from tests.conftest import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD):
    """Log in through the API."""
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


@pytest.fixture
def admin_client(client, make_user):
    """Return the test client logged in as an Admin."""
    make_user("admin")
    response = login(client, "admin@pes.edu")
    assert response.status_code == 200
    return client


@pytest.mark.parametrize("role", ["faculty", "student"])
def test_non_admin_cannot_access_departments(client, make_user, role):
    """Faculty and Students must receive 403."""
    make_user(role)
    login(client, f"{role}@pes.edu")

    response = client.get("/api/departments")
    assert response.status_code == 403


def test_unauthenticated_user_cannot_access_departments(client):
    """Unauthenticated users must receive 401."""
    response = client.get("/api/departments")
    assert response.status_code == 401


def test_tc_stu_01_create_and_list_department(admin_client):
    """An Admin can create a department and list it."""
    response = admin_client.post(
        "/api/departments",
        json={"name": "Computer Science"},
    )

    assert response.status_code == 201
    department = response.get_json()["department"]
    assert department["name"] == "Computer Science"

    response = admin_client.get("/api/departments")
    assert response.status_code == 200
    departments = response.get_json()["departments"]
    assert any(item["name"] == "Computer Science" for item in departments)


def test_department_name_is_required(admin_client):
    """An empty department name must be rejected."""
    for payload in ({}, {"name": ""}, {"name": "   "}):
        response = admin_client.post("/api/departments", json=payload)
        assert response.status_code == 400


def test_duplicate_department_is_rejected(admin_client):
    """Department names must be unique."""
    payload = {"name": "Computer Science"}

    assert admin_client.post("/api/departments", json=payload).status_code == 201
    assert admin_client.post("/api/departments", json=payload).status_code == 409


def test_update_and_delete_department(admin_client):
    """An Admin can update and delete a department."""
    response = admin_client.post(
        "/api/departments",
        json={"name": "Old Name"},
    )
    department_id = response.get_json()["department"]["id"]

    response = admin_client.put(
        f"/api/departments/{department_id}",
        json={"name": "New Name"},
    )
    assert response.status_code == 200
    assert response.get_json()["department"]["name"] == "New Name"

    response = admin_client.delete(f"/api/departments/{department_id}")
    assert response.status_code == 200

    response = admin_client.put(
        f"/api/departments/{department_id}",
        json={"name": "Another Name"},
    )
    assert response.status_code == 404


def test_tc_stu_01_create_section_under_department(admin_client):
    """An Admin can create a section belonging to a department."""
    response = admin_client.post(
        "/api/departments",
        json={"name": "Computer Science"},
    )
    department_id = response.get_json()["department"]["id"]

    response = admin_client.post(
        f"/api/departments/{department_id}/sections",
        json={"name": "A"},
    )

    assert response.status_code == 201
    section = response.get_json()["section"]
    assert section["name"] == "A"
    assert section["department_id"] == department_id


def test_duplicate_section_in_same_department_is_rejected(admin_client):
    """The same section name cannot repeat within a department."""
    response = admin_client.post(
        "/api/departments",
        json={"name": "Computer Science"},
    )
    department_id = response.get_json()["department"]["id"]
    url = f"/api/departments/{department_id}/sections"

    assert admin_client.post(url, json={"name": "A"}).status_code == 201
    assert admin_client.post(url, json={"name": "A"}).status_code == 409


def test_section_requires_existing_department(admin_client):
    """Sections cannot be created under a nonexistent department."""
    response = admin_client.post(
        "/api/departments/9999/sections",
        json={"name": "A"},
    )
    assert response.status_code == 404


def test_update_and_delete_section(admin_client):
    """An Admin can update and delete a section."""
    response = admin_client.post(
        "/api/departments",
        json={"name": "Computer Science"},
    )
    department_id = response.get_json()["department"]["id"]

    response = admin_client.post(
        f"/api/departments/{department_id}/sections",
        json={"name": "A"},
    )
    section_id = response.get_json()["section"]["id"]

    response = admin_client.put(
        f"/api/departments/sections/{section_id}",
        json={"name": "B"},
    )
    assert response.status_code == 200
    assert response.get_json()["section"]["name"] == "B"

    response = admin_client.delete(f"/api/departments/sections/{section_id}")
    assert response.status_code == 200

    response = admin_client.delete(f"/api/departments/sections/{section_id}")
    assert response.status_code == 404
