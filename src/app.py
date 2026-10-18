"""Application factory: builds and configures the Flask app."""

from flask import Flask, jsonify
from flask_wtf.csrf import CSRFError

from src import models  # pylint: disable=unused-import  # registers all tables
from src.config import Config
from src.extensions import csrf, db, login_manager
from src.rbac import FORBIDDEN_MESSAGE, register_rbac
from src.routes.attendance import attendance_bp
from src.routes.auth import auth_bp
from src.routes.courses import courses_bp
from src.routes.departments import departments_bp
from src.routes.fees import fees_bp
from src.routes.health import health_bp
from src.routes.marks import marks_bp
from src.routes.my_courses import my_courses_bp
from src.routes.rbac_routes import rbac_bp
from src.routes.students import students_bp
from src.validators import ValidationError


def create_app(config_class=Config):
    """Create the Flask app with the given settings class."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    register_rbac(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(rbac_bp)
    app.register_blueprint(fees_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(my_courses_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(marks_bp)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app


def register_error_handlers(app):
    """Return JSON errors (not HTML pages) so React can show a clear message."""

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"error": "Please log in first."}), 401

    @app.errorhandler(403)
    def forbidden(_error):
        return jsonify({"error": FORBIDDEN_MESSAGE}), 403

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return jsonify({"error": f"Security token missing or expired: {error.description}"}), 400

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify({"error": error.message}), error.status_code
