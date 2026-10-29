"""Unit tests for attendance marking and correction rules (Issue #13)."""

from datetime import date

import pytest

from src.extensions import db
from src.models import Attendance, AuditLog, Course, Department, Enrollment, Section, Student
from src.services import attendance_service
from src.services.attendance_service import AttendanceError
from src.services.auth_service import create_user
from tests.conftest import TEST_PASSWORD

CLASS_DATE = date(2026, 10, 12)


@pytest.fixture
def setup(app):
    """A course taught by one faculty member, with two enrolled students."""
    with app.app_context():
        faculty = create_user("f1@pes.edu", "Dr. F", TEST_PASSWORD, "faculty")
        other = create_user("f2@pes.edu", "Dr. G", TEST_PASSWORD, "faculty")
        department = Department(name="CSE-AIML")
        db.session.add(department)
        db.session.flush()
        section = Section(name="H", department_id=department.id)
        db.session.add(section)
        db.session.flush()
        course = Course(
            code="UE24AM241A",
            name="SE",
            credits=4,
            department_id=department.id,
            faculty_id=faculty.id,
        )
        students = [
            Student(
                srn=f"PES1UG24AM{index:03d}",
                name=f"Student {index}",
                email=f"s{index}@pes.edu",
                semester=4,
                department_id=department.id,
                section_id=section.id,
            )
            for index in (1, 2)
        ]
        db.session.add(course)
        db.session.add_all(students)
        db.session.flush()
        for student in students:
            db.session.add(Enrollment(student_id=student.id, course_id=course.id))
        db.session.commit()
        yield {
            "course": course,
            "faculty": faculty,
            "other": other,
            "students": [student.id for student in students],
        }


@pytest.mark.parametrize(
    "value, expected",
    [("2026-10-12", date(2026, 10, 12)), (" 2026-10-15 ", date(2026, 10, 15))],
)
def test_parse_class_date_accepts_today_and_past(value, expected):
    """Valid ISO dates up to today are accepted."""
    assert attendance_service.parse_class_date(value, today=date(2026, 10, 15)) == expected


@pytest.mark.parametrize("value", [None, 20261012, "2026/10/12", "2026-13-01", "2026-10-16"])
def test_parse_class_date_rejects_bad_or_future_dates(value):
    """Missing, malformed and future dates are rejected (SR-007)."""
    with pytest.raises(AttendanceError):
        attendance_service.parse_class_date(value, today=date(2026, 10, 15))


def test_tc_att_01_only_assigned_faculty_can_mark(setup):
    """TC-ATT-01 (unit): another faculty member is refused with 403 and nothing is saved."""
    records = [{"student_id": sid, "present": True} for sid in setup["students"]]
    with pytest.raises(AttendanceError) as error:
        attendance_service.save_attendance(setup["course"], setup["other"], CLASS_DATE, records)
    assert error.value.status_code == 403
    assert Attendance.query.count() == 0

    saved = attendance_service.save_attendance(
        setup["course"], setup["faculty"], CLASS_DATE, records
    )
    assert saved == (2, 0)


def test_class_attendance_defaults_to_present_then_shows_saved_values(setup):
    """Unsaved dates show everyone present; saved dates show the stored values."""
    view = attendance_service.class_attendance(setup["course"], CLASS_DATE)
    assert view["recorded"] is False
    assert [row["present"] for row in view["students"]] == [True, True]

    first, second = setup["students"]
    attendance_service.save_attendance(
        setup["course"],
        setup["faculty"],
        CLASS_DATE,
        [{"student_id": first, "present": False}, {"student_id": second, "present": True}],
    )
    view = attendance_service.class_attendance(setup["course"], CLASS_DATE)
    assert view["recorded"] is True
    assert {row["student_id"]: row["present"] for row in view["students"]} == {
        first: False,
        second: True,
    }


def test_tc_att_02_correction_is_audit_logged(setup):
    """TC-ATT-02 (unit): a changed value is a correction with old and new value logged."""
    student_id = setup["students"][0]
    course, faculty = setup["course"], setup["faculty"]
    attendance_service.save_attendance(
        course, faculty, CLASS_DATE, [{"student_id": student_id, "present": True}]
    )
    result = attendance_service.save_attendance(
        course, faculty, CLASS_DATE, [{"student_id": student_id, "present": False}]
    )
    assert result == (1, 1)
    audit = AuditLog.query.one()
    assert (audit.action, audit.old_value, audit.new_value) == (
        "attendance changed",
        "present",
        "absent",
    )
    assert audit.user_id == faculty.id


def test_failed_save_leaves_no_partial_rows(setup):
    """NF-005 / TC-REL-01: an error mid-save rolls back both attendance and audit rows."""
    first, second = setup["students"]
    course, faculty = setup["course"], setup["faculty"]
    attendance_service.save_attendance(
        course, faculty, CLASS_DATE, [{"student_id": first, "present": True}]
    )

    def explode():
        raise RuntimeError("simulated failure")

    with pytest.raises(RuntimeError):
        attendance_service.save_attendance(
            course,
            faculty,
            CLASS_DATE,
            [{"student_id": first, "present": False}, {"student_id": second, "present": False}],
            before_commit_hook=explode,
        )

    rows = {row.student_id: row.present for row in Attendance.query.all()}
    assert rows == {first: True}
    assert AuditLog.query.count() == 0


@pytest.mark.parametrize(
    "records",
    [
        None,
        [],
        [7],
        [{"student_id": True, "present": True}],
        [{"student_id": 1, "present": 1}],
    ],
)
def test_invalid_records_are_rejected(setup, records):
    """Malformed records are rejected before anything is saved."""
    with pytest.raises(AttendanceError):
        attendance_service.save_attendance(setup["course"], setup["faculty"], CLASS_DATE, records)


@pytest.mark.parametrize(
    "attended, held, expected_pct",
    [
        (18, 20, 90.0),
        (15, 20, 75.0),
        (14, 20, 70.0),
        (0, 0, 0.0),
        (0, 10, 0.0),
        (10, 10, 100.0),
        (2, 3, 66.67),
    ],
)
def test_calculate_percentage(attended, held, expected_pct):
    """Attendance % formula: (present / held) * 100 with 0 held giving 0.0 without error (SRS-F-013)."""
    assert attendance_service.calculate_percentage(attended, held) == expected_pct


@pytest.mark.parametrize(
    "pct, held, expected_shortage",
    [
        (90.0, 20, False),
        (75.0, 20, False),  # exactly 75% boundary is NOT shortage
        (74.99, 20, True),  # strictly below 75% is shortage
        (70.0, 20, True),
        (0.0, 0, False),  # 0 classes held is NOT flagged as shortage
        (0.0, 10, True),  # 0 present out of 10 held IS shortage
    ],
)
def test_is_shortage(pct, held, expected_shortage):
    """Shortage is flagged strictly below 75%; 75% boundary and 0 classes are not flagged (SRS-F-014)."""
    assert attendance_service.is_shortage(pct, held) == expected_shortage


def test_course_attendance_summary_and_class_attendance(setup):
    """Course summary computes correct stats and flags shortage per student (SRS-F-013, SRS-F-014)."""
    first, second = setup["students"]
    course, faculty = setup["course"], setup["faculty"]

    # Save attendance for 4 dates:
    # Student 1: 3 present / 4 held = 75.0% (no shortage)
    # Student 2: 2 present / 4 held = 50.0% (shortage)
    for day, (p1, p2) in enumerate(
        [(True, True), (True, False), (True, False), (False, True)], start=1
    ):
        attendance_service.save_attendance(
            course,
            faculty,
            date(2026, 10, day),
            [{"student_id": first, "present": p1}, {"student_id": second, "present": p2}],
        )

    summary = attendance_service.course_attendance_summary(course)
    assert summary[first] == {
        "held": 4,
        "attended": 3,
        "percentage": 75.0,
        "shortage": False,
    }
    assert summary[second] == {
        "held": 4,
        "attended": 2,
        "percentage": 50.0,
        "shortage": True,
    }

    # class_attendance also includes these fields
    view = attendance_service.class_attendance(course, date(2026, 10, 1))
    s1 = next(s for s in view["students"] if s["student_id"] == first)
    s2 = next(s for s in view["students"] if s["student_id"] == second)
    assert s1["percentage"] == 75.0
    assert s1["shortage"] is False
    assert s2["percentage"] == 50.0
    assert s2["shortage"] is True


def test_student_attendance_summary(app, setup):
    """Student summary returns all enrolled courses with attendance stats (SRS-F-013, F-014)."""
    first = setup["students"][0]
    course, faculty = setup["course"], setup["faculty"]
    attendance_service.save_attendance(
        course,
        faculty,
        CLASS_DATE,
        [{"student_id": first, "present": True}],
    )
    with app.app_context():
        student = db.session.get(Student, first)
        summary = attendance_service.student_attendance_summary(student)
        assert len(summary) == 1
        assert summary[0]["course_code"] == course.code
        assert summary[0]["held"] == 1
        assert summary[0]["attended"] == 1
        assert summary[0]["percentage"] == 100.0
        assert summary[0]["shortage"] is False

        detail = attendance_service.student_course_attendance_detail(student, course)
        assert detail["held"] == 1
        assert detail["attended"] == 1
        assert detail["percentage"] == 100.0
        assert len(detail["records"]) == 1
        assert detail["records"][0] == {"date": "2026-10-12", "present": True}
