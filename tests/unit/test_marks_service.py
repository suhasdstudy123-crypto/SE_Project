"""Unit tests for Marks service (Issue #15: SRS-F-019, SRS-F-025, TC-MRK-01..03, TC-AUD-01)."""

import pytest

from src.extensions import db
from src.models import (
    AuditLog,
    Course,
    Department,
    Enrollment,
    ExamRegistration,
    Marks,
    Section,
    Student,
)
from src.services import marks_service
from src.services.auth_service import create_user
from src.services.marks_service import MarksError
from tests.conftest import TEST_PASSWORD


@pytest.fixture
def marks_setup(app):
    """Set up course, assigned faculty, another faculty, and two enrolled students."""
    with app.app_context():
        faculty = create_user("faculty_marks@pes.edu", "Dr. Marks", TEST_PASSWORD, "faculty")
        other_faculty = create_user("other_faculty@pes.edu", "Dr. Other", TEST_PASSWORD, "faculty")
        dept = Department(name="CSE-AIML")
        db.session.add(dept)
        db.session.flush()
        sec = Section(name="H", department_id=dept.id)
        db.session.add(sec)
        db.session.flush()

        course = Course(
            code="UE24AM301",
            name="Machine Learning",
            credits=4,
            department_id=dept.id,
            faculty_id=faculty.id,
        )
        db.session.add(course)
        db.session.flush()

        students = [
            Student(
                srn=f"PES1UG24AM{i:03d}",
                name=f"Student {i}",
                email=f"stu{i}@pes.edu",
                semester=5,
                department_id=dept.id,
                section_id=sec.id,
            )
            for i in (1, 2)
        ]
        db.session.add_all(students)
        db.session.flush()

        # Enroll both students
        for s in students:
            db.session.add(Enrollment(student_id=s.id, course_id=course.id))

        # Only Student 1 is registered for ESA
        db.session.add(ExamRegistration(student_id=students[0].id, course_id=course.id))
        db.session.commit()

        yield {
            "course": course,
            "faculty": faculty,
            "other_faculty": other_faculty,
            "student1": students[0],
            "student2": students[1],
        }


def test_tc_mrk_01_save_valid_marks(marks_setup):
    """TC-MRK-01: Valid component marks saved and total computed correctly."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    marks_data = {"isa1": 19.5, "isa2": 18.0, "assessment": 9.5, "esa": 48.0}
    saved = marks_service.save_student_marks(course, faculty, student1.id, marks_data)

    assert saved.isa1 == 19.5
    assert saved.isa2 == 18.0
    assert saved.assessment == 9.5
    assert saved.esa == 48.0
    assert saved.total == 95.0

    # Roster view lists the student with saved marks
    roster = marks_service.get_course_marks(course, faculty)
    s1_view = next(s for s in roster["students"] if s["student_id"] == student1.id)
    assert s1_view["total"] == 95.0
    assert s1_view["is_esa_registered"] is True


def test_tc_mrk_02_out_of_range_marks_rejected(marks_setup):
    """TC-MRK-02: Above-max marks rejected by service."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    with pytest.raises(MarksError, match="ISA-1 must be between 0 and 20"):
        marks_service.save_student_marks(course, faculty, student1.id, {"isa1": 21})

    with pytest.raises(MarksError, match="Assessment must be between 0 and 10"):
        marks_service.save_student_marks(course, faculty, student1.id, {"assessment": 11})

    with pytest.raises(MarksError, match="ESA must be between 0 and 50"):
        marks_service.save_student_marks(course, faculty, student1.id, {"esa": 55})


def test_tc_mrk_03_esa_marks_requires_registration(marks_setup):
    """TC-MRK-03: Student 2 (not registered for ESA) cannot receive ESA marks."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student2 = marks_setup["student2"]

    with pytest.raises(MarksError, match="not registered for ESA"):
        marks_service.save_student_marks(course, faculty, student2.id, {"esa": 42.0})

    # But ISA marks succeed for student 2
    saved = marks_service.save_student_marks(course, faculty, student2.id, {"isa1": 17.0})
    assert saved.isa1 == 17.0
    assert saved.total == 17.0


def test_tc_aud_01_marks_change_creates_audit_log(marks_setup):
    """TC-AUD-01: Changing a saved mark writes an AuditLog row with old and new total."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    # Initial save: 15.0
    marks_service.save_student_marks(course, faculty, student1.id, {"isa1": 15.0})
    assert AuditLog.query.count() == 0

    # Change mark: 15.0 -> 18.0
    marks_service.save_student_marks(course, faculty, student1.id, {"isa1": 18.0})
    assert AuditLog.query.count() == 1

    log = AuditLog.query.one()
    assert log.action == "marks changed"
    assert log.entity == "marks"
    assert log.entity_id == f"{course.id}:{student1.id}"
    assert log.old_value == "15.0"
    assert log.new_value == "18.0"
    assert log.user_id == faculty.id


def test_unassigned_faculty_cannot_view_or_save_marks(marks_setup):
    """Only the assigned faculty member can view or save marks for a course (SRS-SR-002)."""
    course = marks_setup["course"]
    other_faculty = marks_setup["other_faculty"]
    student1 = marks_setup["student1"]

    with pytest.raises(MarksError, match="Only the faculty assigned"):
        marks_service.get_course_marks(course, other_faculty)

    with pytest.raises(MarksError, match="Only the faculty assigned"):
        marks_service.save_student_marks(course, other_faculty, student1.id, {"isa1": 15.0})


def test_non_enrolled_student_marks_rejected(marks_setup):
    """Attempting to save marks for a non-enrolled student is rejected."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]

    with pytest.raises(MarksError, match="not enrolled"):
        marks_service.save_student_marks(course, faculty, 9999, {"isa1": 15.0})


def test_failed_save_rolls_back_everything(marks_setup):
    """NF-005 / TC-REL-01: An error mid-save leaves no partial marks or audit entries."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    marks_service.save_student_marks(course, faculty, student1.id, {"isa1": 15.0})

    def boom():
        raise RuntimeError("database exploded")

    with pytest.raises(RuntimeError):
        marks_service.save_student_marks(
            course, faculty, student1.id, {"isa1": 19.0}, before_commit_hook=boom
        )

    # Persisted value should still be 15.0 and no audit log row
    db.session.expire_all()
    rec = Marks.query.filter_by(course_id=course.id, student_id=student1.id).one()
    assert rec.isa1 == 15.0
    assert rec.total == 15.0
    assert AuditLog.query.count() == 0
