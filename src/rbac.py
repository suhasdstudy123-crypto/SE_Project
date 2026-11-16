"""Server-side Role-Based Access Control (RBAC) decorators and request guards (Issue #5).

Enforces SRS-F-002 and SRS-SR-002:
- Role is always read from the server session (current_user.role), never from request data.
- Unauthenticated requests receive HTTP 401.
- Authenticated requests with a role not permitted for the route receive HTTP 403.
"""

from functools import wraps

from flask import jsonify, request
from flask_login import current_user

from src.models.user import Role

FORBIDDEN_MESSAGE = "Forbidden: you do not have permission to access this resource."

# Prefix-level role rules enforced on every /api request before route handlers run.
PREFIX_ROLE_RULES = (
    ("/api/admin", (Role.ADMIN,)),
    ("/api/faculty", (Role.FACULTY,)),
    ("/api/marks", (Role.FACULTY,)),
    ("/api/student", (Role.STUDENT,)),
    ("/api/esa/register", (Role.STUDENT,)),
    ("/api/esa/drop", (Role.STUDENT,)),
    ("/api/results/me", (Role.STUDENT,)),
)

ROLE_MENUS = {
    Role.ADMIN: [
        {"label": "Dashboard", "path": "/admin"},
        {"label": "Departments & Sections", "path": "/admin/departments"},
        {"label": "Students", "path": "/admin/students"},
        {"label": "Courses & Enrollment", "path": "/admin/courses"},
        {"label": "Fee Status", "path": "/admin/fees"},
        {"label": "ESA Window", "path": "/admin/esa"},
        {"label": "Audit Log", "path": "/admin/audit"},
        {"label": "CSV Reports", "path": "/admin/results"},
        {"label": "Result Analysis", "path": "/admin/analysis"},
    ],
    Role.FACULTY: [
        {"label": "Dashboard", "path": "/faculty"},
        {"label": "My Courses", "path": "/faculty/courses"},
        {"label": "Mark Attendance", "path": "/faculty/attendance"},
        {"label": "Enter Marks", "path": "/faculty/marks"},
        {"label": "Course Analysis", "path": "/faculty/reports"},
        {"label": "CSV Reports", "path": "/faculty/results"},
    ],
    Role.STUDENT: [
        {"label": "Dashboard", "path": "/student"},
        {"label": "My Courses", "path": "/student/courses"},
        {"label": "My Attendance", "path": "/student/attendance"},
        {"label": "ESA Registration", "path": "/student/esa"},
        {"label": "My Results", "path": "/student/results"},
        {"label": "Class Analysis", "path": "/student/analysis"},
    ],
}


def roles_required(*allowed_roles):
    """Decorator restricting a Flask route to users whose session role is in allowed_roles."""
    if not allowed_roles or any(role not in Role.ALL for role in allowed_roles):
        raise ValueError(f"roles_required expects roles from {Role.ALL}, got {allowed_roles}")

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Please log in first."}), 401
            if current_user.role not in allowed_roles:
                return jsonify({"error": FORBIDDEN_MESSAGE}), 403
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


admin_required = roles_required(Role.ADMIN)
faculty_required = roles_required(Role.FACULTY)
student_required = roles_required(Role.STUDENT)
staff_required = roles_required(Role.ADMIN, Role.FACULTY)


def check_required_roles_for_path(path):
    """Return the tuple of allowed roles if path matches a protected prefix, else None."""
    for prefix, allowed_roles in PREFIX_ROLE_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return allowed_roles
    return None


def register_rbac(app):
    """Attach a server-side before_request RBAC guard to the Flask app."""

    @app.before_request
    def enforce_prefix_rbac():
        allowed_roles = check_required_roles_for_path(request.path)
        if allowed_roles is None:
            return None
        if not current_user.is_authenticated:
            return jsonify({"error": "Please log in first."}), 401
        if current_user.role not in allowed_roles:
            return jsonify({"error": FORBIDDEN_MESSAGE}), 403
        return None
