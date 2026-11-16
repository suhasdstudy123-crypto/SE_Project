"""Result analysis API for Admin, Faculty and Student (SRS-F-022, Issue #25)."""

from flask import Blueprint, jsonify
from flask_login import current_user

from src.rbac import admin_required, faculty_required, student_required
from src.services import analysis_service
from src.services.analysis_service import AnalysisError
from src.services.course_service import CourseError, get_course, student_for_user

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api")


@analysis_bp.errorhandler(AnalysisError)
@analysis_bp.errorhandler(CourseError)
def analysis_error(error):
    """Turn a service error into JSON."""
    return jsonify({"error": error.message}), error.status_code


def _analysis(course_id, student=None):
    course = get_course(course_id)
    analysis_service.check_access(course, current_user, student)
    return jsonify(analysis_service.course_analysis(course))


@analysis_bp.get("/admin/analysis/<int:course_id>")
@admin_required
def admin_analysis(course_id):
    """Admin: result analysis of any course."""
    return _analysis(course_id)


@analysis_bp.get("/faculty/analysis/<int:course_id>")
@faculty_required
def faculty_analysis(course_id):
    """Faculty: result analysis of a course they teach."""
    return _analysis(course_id)


@analysis_bp.get("/student/analysis/<int:course_id>")
@student_required
def student_analysis(course_id):
    """Student: class result analysis of a course they are enrolled in (no names, only totals)."""
    return _analysis(course_id, student_for_user(current_user))
