"""Admin API for student record management."""

from flask import Blueprint, jsonify, request

from src.extensions import db
from src.models import Department, Section, Student
from src.rbac import admin_required
from src.validators import ValidationError, validate_email

students_bp = Blueprint(
    "students",
    __name__,
    url_prefix="/api/admin/students",
)


def validate_student_data(
    data, existing_student=None
):  # pylint: disable=too-many-return-statements,too-many-branches
    """Validate student fields and department-section consistency."""
    if not isinstance(data, dict):
        return None, "A JSON object is required."

    current = existing_student

    srn = data.get("srn", current.srn if current else None)
    name = data.get("name", current.name if current else None)
    email = data.get("email", current.email if current else None)
    semester = data.get("semester", current.semester if current else None)
    department_id = data.get("department_id", current.department_id if current else None)
    section_id = data.get("section_id", current.section_id if current else None)

    if not isinstance(srn, str) or not srn.strip():
        return None, "SRN is required."
    if not isinstance(name, str) or not name.strip():
        return None, "Student name is required."
    if not isinstance(email, str) or not email.strip():
        return None, "Student email is required."

    try:
        email = validate_email(email)
    except ValidationError as err:
        return None, err.message

    if not isinstance(semester, int) or isinstance(semester, bool) or not 1 <= semester <= 8:
        return None, "Semester must be an integer between 1 and 8."

    if not isinstance(department_id, int) or isinstance(department_id, bool):
        return None, "A valid department_id is required."

    if not isinstance(section_id, int) or isinstance(section_id, bool):
        return None, "A valid section_id is required."

    department = db.session.get(Department, department_id)
    if department is None:
        return None, "Department not found."

    section = db.session.get(Section, section_id)
    if section is None:
        return None, "Section not found."

    if section.department_id != department_id:
        return None, "Section does not belong to the selected department."

    srn = srn.strip()
    name = name.strip()
    email = email.strip().lower()

    duplicate_srn = Student.query.filter(
        Student.srn == srn,
        Student.id != (current.id if current else -1),
    ).first()
    if duplicate_srn:
        return None, "SRN already exists."

    duplicate_email = Student.query.filter(
        db.func.lower(Student.email) == email,
        Student.id != (current.id if current else -1),
    ).first()
    if duplicate_email:
        return None, "Email already exists."

    return {
        "srn": srn,
        "name": name,
        "email": email,
        "semester": semester,
        "department_id": department_id,
        "section_id": section_id,
    }, None


@students_bp.get("")
@admin_required
def list_students():
    """List all students with optional parameterized search (TC-SEC-05)."""
    query = Student.query
    search = request.args.get("search") or request.args.get("q")
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            db.or_(
                Student.name.ilike(search_term),
                Student.srn.ilike(search_term),
                Student.email.ilike(search_term),
            )
        )
    department_id = request.args.get("department_id", type=int)
    if department_id:
        query = query.filter(Student.department_id == department_id)
    section_id = request.args.get("section_id", type=int)
    if section_id:
        query = query.filter(Student.section_id == section_id)

    students = query.order_by(Student.srn).all()
    return jsonify({"students": [student.to_dict() for student in students]})


@students_bp.post("")
@admin_required
def create_student():
    """Create a student record."""
    data, error = validate_student_data(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    student = Student(**data)
    db.session.add(student)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not create student record."}), 409

    return jsonify({"student": student.to_dict()}), 201


@students_bp.put("/<int:student_id>")
@admin_required
def update_student(student_id):
    """Update an existing student record."""
    student = db.session.get(Student, student_id)
    if student is None:
        return jsonify({"error": "Student not found."}), 404

    data, error = validate_student_data(
        request.get_json(silent=True),
        existing_student=student,
    )
    if error:
        return jsonify({"error": error}), 400

    for field, value in data.items():
        setattr(student, field, value)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update student record."}), 409

    return jsonify({"student": student.to_dict()})


@students_bp.delete("/<int:student_id>")
@admin_required
def delete_student(student_id):
    """Delete a student record."""
    student = db.session.get(Student, student_id)
    if student is None:
        return jsonify({"error": "Student not found."}), 404

    db.session.delete(student)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not delete student record."}), 409

    return jsonify({"message": "Student deleted."})
