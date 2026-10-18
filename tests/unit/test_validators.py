"""Unit tests for input validators (Issue #7: SRS-SR-007, TC-SEC-07, TC-MRK-02)."""

from datetime import date, timedelta
import pytest

from src.validators import (
    ValidationError,
    validate_date,
    validate_email,
    validate_mark_component,
    validate_marks_dict,
    validate_semester,
    validate_srn,
)


def test_validate_email_accepts_valid_formats():
    assert validate_email("student@pes.edu") == "student@pes.edu"
    assert validate_email("  ADMIN@PES.EDU  ") == "admin@pes.edu"
    assert validate_email("user.name+tag@domain.co.in") == "user.name+tag@domain.co.in"


@pytest.mark.parametrize(
    "invalid_email",
    [
        "",
        "   ",
        None,
        123,
        "plainaddress",
        "@missingusername.com",
        "username@.com",
        "username@domain..com",
        "username@domain",
    ],
)
def test_validate_email_rejects_invalid_formats(invalid_email):
    with pytest.raises(ValidationError):
        validate_email(invalid_email)


def test_validate_date_accepts_valid_dates():
    parsed = validate_date("2026-10-15")
    assert parsed == date(2026, 10, 15)


def test_validate_date_rejects_invalid_and_future_dates():
    with pytest.raises(ValidationError, match="Date is required"):
        validate_date("")

    with pytest.raises(ValidationError, match="Date is required"):
        validate_date(None)

    with pytest.raises(ValidationError, match="valid date in YYYY-MM-DD format"):
        validate_date("2026-02-30")

    with pytest.raises(ValidationError, match="valid date in YYYY-MM-DD format"):
        validate_date("not-a-date")

    today = date(2026, 10, 15)
    tomorrow = (today + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="Attendance cannot be marked for a future date"):
        validate_date(tomorrow, allow_future=False, today=today)

    # Future date permitted when allow_future=True
    assert validate_date(tomorrow, allow_future=True, today=today) == today + timedelta(days=1)


def test_tc_mrk_02_validate_marks_component_boundaries():
    """TC-MRK-02: ISA-1=21, Assessment=11, ESA=51, ISA-2=-1, ESA='abc' each rejected."""
    # ISA-1 = 21 -> rejected
    with pytest.raises(ValidationError, match="ISA-1 must be between 0 and 20"):
        validate_mark_component("isa1", 21)

    # Assessment = 11 -> rejected
    with pytest.raises(ValidationError, match="Assessment must be between 0 and 10"):
        validate_mark_component("assessment", 11)

    # ESA = 51 -> rejected
    with pytest.raises(ValidationError, match="ESA must be between 0 and 50"):
        validate_mark_component("esa", 51)

    # ISA-2 = -1 -> rejected
    with pytest.raises(ValidationError, match="ISA-2 must be between 0 and 20"):
        validate_mark_component("isa2", -1)

    # ESA = 'abc' -> rejected with number message
    with pytest.raises(ValidationError, match="ESA mark must be a number"):
        validate_mark_component("esa", "abc")

    # Booleans are rejected
    with pytest.raises(ValidationError, match="mark must be a number"):
        validate_mark_component("isa1", True)

    # Unknown component raises error
    with pytest.raises(ValidationError, match="Unknown mark component"):
        validate_mark_component("lab_exam", 15)


def test_validate_mark_component_accepts_valid_values():
    assert validate_mark_component("isa1", 20) == 20.0
    assert validate_mark_component("isa1", 0) == 0.0
    assert validate_mark_component("isa2", 17.5) == 17.5
    assert validate_mark_component("assessment", 10) == 10.0
    assert validate_mark_component("esa", 45) == 45.0
    assert validate_mark_component("esa", None) is None


def test_validate_marks_dict():
    payload = {"isa1": 18, "isa2": 17, "assessment": 9, "esa": 40}
    validated = validate_marks_dict(payload)
    assert validated == {"isa1": 18.0, "isa2": 17.0, "assessment": 9.0, "esa": 40.0}

    with pytest.raises(ValidationError, match="must be a JSON object"):
        validate_marks_dict("not-a-dict")


def test_validate_srn_and_semester():
    assert validate_srn("PES1UG24CS001") == "PES1UG24CS001"
    with pytest.raises(ValidationError, match="SRN is required"):
        validate_srn("")
    with pytest.raises(ValidationError, match="SRN is required"):
        validate_srn(None)

    assert validate_semester(1) == 1
    assert validate_semester(8) == 8
    for invalid in (0, 9, -1, "3", True, False):
        with pytest.raises(ValidationError, match="integer between 1 and 8"):
            validate_semester(invalid)
