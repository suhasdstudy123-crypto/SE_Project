"""ESA registration API (SRS-F-016, F-017, F-018, F-026; SAD 4.3.2)."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

from src.rbac import admin_required, student_required
from src.services import esa_service
from src.services.course_service import CourseError, student_for_user
from src.services.esa_service import EsaError

admin_esa_bp = Blueprint("admin_esa", __name__, url_prefix="/api/admin")
student_esa_bp = Blueprint("student_esa", __name__, url_prefix="/api")


@admin_esa_bp.errorhandler(EsaError)
@admin_esa_bp.errorhandler(CourseError)
@student_esa_bp.errorhandler(EsaError)
@student_esa_bp.errorhandler(CourseError)
def esa_error(error):
    """Turn a service error into JSON; blocked registrations also carry a reason code."""
    body = {"error": error.message}
    if getattr(error, "reason", None):
        body["reason"] = error.reason
    return jsonify(body), error.status_code


def _current_student():
    student = student_for_user(current_user)
    if student is None:
        raise EsaError("No student record is linked to this login.", 404)
    return student


# ---------------------------------------------------------------- Admin


@admin_esa_bp.get("/esa-window")
@admin_required
def get_window():
    """Is the ESA registration window open?"""
    return jsonify({"window": esa_service.window_state()})


@admin_esa_bp.put("/esa-window")
@admin_required
def set_window():
    """Open or close the window: {"open": true|false}."""
    data = request.get_json(silent=True) or {}
    return jsonify({"window": esa_service.set_window(data.get("open"))})


@admin_esa_bp.get("/esa-eligibility/<int:course_id>")
@admin_required
def course_eligibility(course_id):
    """Enrolled students of a course with fees, attendance, eligibility and registration."""
    return jsonify(esa_service.course_eligibility(course_id))


@admin_esa_bp.post("/eligibility-override")
@admin_required
def create_override():
    """Override eligibility: {"student_id", "course_id", "reason"} (reason is required)."""
    override = esa_service.create_override(current_user, request.get_json(silent=True))
    return jsonify({"override": override.to_dict()}), 201


# ---------------------------------------------------------------- Student


@student_esa_bp.get("/student/esa")
@student_required
def my_esa():
    """Window state and each enrolled course with eligibility and registration."""
    return jsonify(esa_service.student_overview(_current_student()))


@student_esa_bp.post("/esa/register")
@student_required
def register():
    """Register for a course's ESA: {"course_id"}."""
    data = request.get_json(silent=True) or {}
    course = esa_service.register(_current_student(), data.get("course_id"))
    return jsonify({"status": "registered", "course_id": course.id}), 201


@student_esa_bp.post("/esa/drop")
@student_required
def drop():
    """Drop a course's ESA: {"course_id"}."""
    data = request.get_json(silent=True) or {}
    course = esa_service.drop(_current_student(), data.get("course_id"))
    return jsonify({"status": "dropped", "course_id": course.id})
