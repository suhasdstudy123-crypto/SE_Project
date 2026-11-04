"""Faculty and Student Marks APIs (SRS-F-019, SRS-F-020, SRS-F-025, SRS-SR-007)."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

from src.rbac import faculty_required, student_required
from src.services import marks_service
from src.services.course_service import CourseError, get_course
from src.services.marks_service import MarksError
from src.validators import ValidationError

faculty_marks_bp = Blueprint("faculty_marks", __name__, url_prefix="/api/faculty/marks")
student_marks_bp = Blueprint("student_marks", __name__, url_prefix="/api/student")


@faculty_marks_bp.errorhandler(MarksError)
@faculty_marks_bp.errorhandler(CourseError)
@faculty_marks_bp.errorhandler(ValidationError)
@student_marks_bp.errorhandler(MarksError)
@student_marks_bp.errorhandler(CourseError)
@student_marks_bp.errorhandler(ValidationError)
def marks_error_handler(error):
    """Format service and validation errors as JSON."""
    return jsonify({"error": error.message}), error.status_code


@faculty_marks_bp.get("/<int:course_id>")
@faculty_required
def get_course_marks_endpoint(course_id):
    """Retrieve enrolled students and their marks for a course."""
    course = get_course(course_id)
    result = marks_service.get_course_marks(course, current_user)
    return jsonify(result), 200


@faculty_marks_bp.put("/<int:course_id>/<int:student_id>")
@faculty_required
def save_student_marks_endpoint(course_id, student_id):
    """Save or update marks for a student in a course (SRS-F-019, SRS-F-025)."""
    course = get_course(course_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise MarksError("A JSON object is required.")

    saved = marks_service.save_student_marks(course, current_user, student_id, data)
    return jsonify({"marks": saved.to_dict()}), 200


@student_marks_bp.get("/results")
@student_marks_bp.get("/marks")
@student_required
def get_student_results_endpoint():
    """Retrieve marks, letter grades, and calculated SGPA for logged-in student (SRS-F-020)."""
    result = marks_service.get_student_results(current_user)
    return jsonify(result), 200
