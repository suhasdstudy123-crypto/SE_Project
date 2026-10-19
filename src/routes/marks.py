"""Marks entry and validation API (SRS-F-019, SRS-SR-007, SRS-F-025, TC-MRK-02, TC-AUD-01)."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from src.extensions import db
from src.models.course import Course
from src.models.marks import Marks
from src.models.student import Student
from src.rbac import faculty_required
from src.services.audit_service import record_audit_log
from src.validators import ValidationError, validate_marks_dict

marks_bp = Blueprint("marks", __name__, url_prefix="/api/marks")


@marks_bp.post("/validate")
@login_required
@faculty_required
def validate_marks_endpoint():
    """Validate marks payload according to component limits (SRS-SR-007, TC-MRK-02)."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "A JSON object is required."}), 400
    try:
        validated = validate_marks_dict(data)
    except ValidationError as err:
        return jsonify({"error": err.message}), err.status_code
    return jsonify({"validated": validated}), 200


@marks_bp.route("/<int:course_id>/<int:student_id>", methods=["GET", "PUT", "POST"])
@login_required
@faculty_required
def update_or_get_marks(course_id, student_id):  # pylint: disable=too-many-return-statements
    """Get or update student marks, creating audit log rows for changes (TC-AUD-01, SRS-F-025)."""
    course = db.session.get(Course, course_id)
    if course is None:
        return jsonify({"error": "Course not found."}), 404

    student = db.session.get(Student, student_id)
    if student is None:
        return jsonify({"error": "Student not found."}), 404

    record = Marks.query.filter_by(course_id=course_id, student_id=student_id).first()

    if request.method == "GET":
        if record is None:
            return jsonify({"marks": None})
        return jsonify({"marks": record.to_dict()})

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    try:
        validated = validate_marks_dict(data)
    except ValidationError as err:
        return jsonify({"error": err.message}), err.status_code

    if record is None:
        record = Marks(
            course_id=course_id,
            student_id=student_id,
            isa1=validated.get("isa1"),
            isa2=validated.get("isa2"),
            assessment=validated.get("assessment"),
            esa=validated.get("esa"),
        )
        db.session.add(record)
        record_audit_log(
            user_id=current_user.id,
            action="marks entered",
            entity="marks",
            entity_id=f"{course_id}:{student_id}",
            old_value=None,
            new_value=str(validated),
        )
    else:
        for comp, new_val in validated.items():
            old_val = getattr(record, comp)
            if old_val != new_val:
                record_audit_log(
                    user_id=current_user.id,
                    action="marks changed",
                    entity="marks",
                    entity_id=f"{course_id}:{student_id}",
                    old_value=str(old_val) if old_val is not None else "None",
                    new_value=str(new_val) if new_val is not None else "None",
                )
                setattr(record, comp, new_val)

    components = [record.isa1, record.isa2, record.assessment, record.esa]
    if any(c is not None for c in components):
        record.total = sum(c for c in components if c is not None)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not save marks."}), 409

    return jsonify({"marks": record.to_dict()})
