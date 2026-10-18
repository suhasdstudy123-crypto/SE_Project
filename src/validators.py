"""Server-side input validation module (Issue #7: SRS-SR-007, TC-SEC-07, TC-MRK-02).

Validates all untrusted user input on the server:
- Email addresses (format, whitespace, lowercase normalization)
- Dates (ISO format, future date rejection for attendance)
- Marks (type check, ISA-1: 0-20, ISA-2: 0-20, Assessment: 0-10, ESA: 0-50)
- Student identifiers (SRN, Semester 1-8)
"""

from datetime import date
import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$")

MARK_COMPONENTS = {
    "isa1": {"name": "ISA-1", "min": 0, "max": 20},
    "isa2": {"name": "ISA-2", "min": 0, "max": 20},
    "assessment": {"name": "Assessment", "min": 0, "max": 10},
    "esa": {"name": "ESA", "min": 0, "max": 50},
}


class ValidationError(Exception):
    """Raised when user input fails server-side validation rules."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_email(email):
    """Validate email address format (SRS-SR-007, TC-SEC-07)."""
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("Email is required.")
    email_clean = email.strip()
    if not EMAIL_REGEX.match(email_clean):
        raise ValidationError("Invalid email address format.")
    return email_clean.lower()


def validate_date(value, allow_future=False, today=None):
    """Validate a date string in YYYY-MM-DD format (SRS-SR-007, SRS-F-011)."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Date is required (YYYY-MM-DD).")
    try:
        parsed_date = date.fromisoformat(value.strip())
    except ValueError as err:
        raise ValidationError("Date must be a valid date in YYYY-MM-DD format.") from err
    if not allow_future and parsed_date > (today or date.today()):
        raise ValidationError("Attendance cannot be marked for a future date.")
    return parsed_date


def validate_mark_component(component, value):
    """Validate a single marks component (SRS-SR-007, TC-MRK-02).

    Accepts None (not yet entered) or a number within bounds.
    """
    if component not in MARK_COMPONENTS:
        raise ValidationError(f"Unknown mark component: {component}.")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{MARK_COMPONENTS[component]['name']} mark must be a number.")

    config = MARK_COMPONENTS[component]
    if value < config["min"] or value > config["max"]:
        raise ValidationError(
            f"{config['name']} must be between {config['min']} and {config['max']}."
        )
    return float(value)


def validate_marks_dict(marks):
    """Validate a dictionary of marks components (isa1, isa2, assessment, esa)."""
    if not isinstance(marks, dict):
        raise ValidationError("Marks data must be a JSON object.")
    validated = {}
    for comp in ("isa1", "isa2", "assessment", "esa"):
        if comp in marks:
            validated[comp] = validate_mark_component(comp, marks[comp])
    return validated


def validate_srn(srn):
    """Validate that an SRN is a non-empty string."""
    if not isinstance(srn, str) or not srn.strip():
        raise ValidationError("SRN is required.")
    return srn.strip()


def validate_semester(semester):
    """Validate that semester is an integer between 1 and 8."""
    if isinstance(semester, bool) or not isinstance(semester, int) or not 1 <= semester <= 8:
        raise ValidationError("Semester must be an integer between 1 and 8.")
    return semester
