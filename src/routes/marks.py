"""Marks entry and validation API (SRS-F-019, SRS-SR-007, TC-MRK-02)."""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from src.rbac import faculty_required
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
