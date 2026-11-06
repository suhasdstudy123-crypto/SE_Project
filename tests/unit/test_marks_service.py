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

    with pytest.raises(MarksError, match="not registered for ESA") as exc:
        marks_service.save_student_marks(course, faculty, student2.id, {"esa": 42.0})
    assert exc.value.status_code == 409

    # Nothing saved for student 2
    assert Marks.query.filter_by(course_id=course.id, student_id=student2.id).first() is None

    # But ISA marks succeed for student 2
    saved = marks_service.save_student_marks(course, faculty, student2.id, {"isa1": 17.0})
    assert saved.isa1 == 17.0
    assert saved.total == 17.0


def test_tc_aud_01_marks_change_creates_audit_log(marks_setup):
    """TC-AUD-01: Changing a saved mark writes an AuditLog row with that mark's old/new value."""
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
    assert log.old_value == "ISA-1: 15.0"
    assert log.new_value == "ISA-1: 18.0"
    assert log.user_id == faculty.id
    assert log.timestamp is not None


def test_tc_aud_01_total_unchanged_still_logs_each_changed_mark(marks_setup):
    """TC-AUD-01: ISA-1 15->18 and ISA-2 18->15 keep the total same but write 2 audit rows."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    marks_service.save_student_marks(
        course, faculty, student1.id, {"isa1": 15.0, "isa2": 18.0, "assessment": 9.0}
    )
    saved = marks_service.save_student_marks(
        course, faculty, student1.id, {"isa1": 18.0, "isa2": 15.0, "assessment": 9.0}
    )
    assert saved.total == 42.0  # total did not change

    logs = AuditLog.query.order_by(AuditLog.id).all()
    # One row per changed mark; the unchanged Assessment mark is not logged
    assert [(log.old_value, log.new_value) for log in logs] == [
        ("ISA-1: 15.0", "ISA-1: 18.0"),
        ("ISA-2: 18.0", "ISA-2: 15.0"),
    ]
    assert all(log.action == "marks changed" for log in logs)
    assert all(log.user_id == faculty.id for log in logs)


def test_clearing_a_mark_is_logged(marks_setup):
    """TC-AUD-01: Removing a saved mark (set to null) is also a change and is logged."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    marks_service.save_student_marks(course, faculty, student1.id, {"isa1": 15.0})
    marks_service.save_student_marks(course, faculty, student1.id, {"isa1": None})

    log = AuditLog.query.one()
    assert log.old_value == "ISA-1: 15.0"
    assert log.new_value == "ISA-1: empty"


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


def test_tc_mrk_04_grade_assignment():
    """TC-MRK-04: Grade boundaries correctly mapped to letter grades and grade points."""
    cases = [
        (100.0, ("S", 10)),
        (90.0, ("S", 10)),
        (89.9, ("A", 9)),
        (89.0, ("A", 9)),
        (80.0, ("A", 9)),
        (79.9, ("B", 8)),
        (70.0, ("B", 8)),
        (69.9, ("C", 7)),
        (60.0, ("C", 7)),
        (59.9, ("D", 6)),
        (50.0, ("D", 6)),
        (49.9, ("E", 5)),
        (49.0, ("E", 5)),
        (40.0, ("E", 5)),
        (39.9, ("F", 0)),
        (39.0, ("F", 0)),
        (0.0, ("F", 0)),
        (-5.0, ("F", 0)),
        (None, (None, None)),
    ]
    for total, expected in cases:
        assert marks_service.calculate_grade_and_points(total) == expected


def test_tc_mrk_05_sgpa_calculation():
    """TC-MRK-05: SGPA = sum(credits * grade_point) / sum(credits) weighted by credits."""
    # Standard multi-course calculation
    courses = [
        (4, 10),  # 4 * 10 = 40
        (4, 9),  # 4 * 9 = 36
        (2, 8),  # 2 * 8 = 16
    ]
    # (40 + 36 + 16) / 10 = 92 / 10 = 9.2
    assert marks_service.calculate_sgpa(courses) == 9.2

    # With F grade (0 points, but credits still count)
    courses_with_fail = [
        (4, 10),  # 40
        (4, 0),  # 0
    ]
    # 40 / 8 = 5.0
    assert marks_service.calculate_sgpa(courses_with_fail) == 5.0

    # With dicts
    dict_courses = [
        {"credits": 4, "grade_point": 9},  # 36
        {"credits": 3, "grade_point": 8},  # 24
    ]
    # 60 / 7 = 8.57
    assert marks_service.calculate_sgpa(dict_courses) == 8.57

    # With un-graded courses (None grade_point ignored from denominator and numerator)
    partial_graded = [
        (4, 10),
        (4, None),
    ]
    assert marks_service.calculate_sgpa(partial_graded) == 10.0

    # Empty or all ungraded returns None
    assert marks_service.calculate_sgpa([]) is None
    assert marks_service.calculate_sgpa([(4, None), (3, None)]) is None


def test_no_grade_until_all_four_marks_entered(marks_setup):
    """SRS-F-020: A course with a missing mark gets no grade and is left out of the SGPA."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    # Only ISA-1 entered: total 18, but no grade (not "F")
    rec = marks_service.save_student_marks(course, faculty, student1.id, {"isa1": 18.0})
    assert rec.total == 18.0
    assert rec.grade is None
    assert rec.grade_point is None

    # Second course fully marked: total 100 -> S
    course2 = Course(
        code="UE24AM302",
        name="Deep Learning",
        credits=4,
        department_id=course.department_id,
        faculty_id=faculty.id,
    )
    db.session.add(course2)
    db.session.flush()
    db.session.add(Enrollment(student_id=student1.id, course_id=course2.id))
    db.session.add(ExamRegistration(student_id=student1.id, course_id=course2.id))
    db.session.commit()
    marks_service.save_student_marks(
        course2, faculty, student1.id, {"isa1": 20, "isa2": 20, "assessment": 10, "esa": 50}
    )

    user = create_user("s1_partial@pes.edu", "Student One", TEST_PASSWORD, "student")
    student1.user_id = user.id
    db.session.commit()

    res = marks_service.get_student_results(user)
    grades = {c["code"]: c["grade"] for c in res["courses"]}
    assert grades == {"UE24AM301": None, "UE24AM302": "S"}
    # SGPA uses only the fully graded course (10.0), not dragged down to 5.0
    assert res["sgpa"] == 10.0
    assert res["earned_credits"] == 4

    # Entering the remaining marks gives the grade
    rec = marks_service.save_student_marks(
        course, faculty, student1.id, {"isa2": 18.0, "assessment": 9.0, "esa": 45.0}
    )
    assert rec.total == 90.0
    assert (rec.grade, rec.grade_point) == ("S", 10)


def test_get_student_results_service(marks_setup):
    """Test get_student_results returns student's courses, marks, and calculated SGPA."""
    course = marks_setup["course"]
    faculty = marks_setup["faculty"]
    student1 = marks_setup["student1"]

    # Save marks for student1
    marks_service.save_student_marks(
        course, faculty, student1.id, {"isa1": 18.0, "isa2": 18.0, "assessment": 9.0, "esa": 45.0}
    )

    # Link a user to student1
    user = create_user("s1_login@pes.edu", "Student One Login", TEST_PASSWORD, "student")
    student1.user_id = user.id
    db.session.commit()

    res = marks_service.get_student_results(user)
    assert len(res["courses"]) == 1
    c_res = res["courses"][0]
    assert c_res["code"] == "UE24AM301"
    assert c_res["total"] == 90.0
    assert c_res["grade"] == "S"
    assert c_res["grade_point"] == 10
    assert res["sgpa"] == 10.0
    assert res["total_credits"] == 4
    assert res["earned_credits"] == 4

    # Non-student user returns empty
    non_student = create_user("admin_test_res@pes.edu", "Admin", TEST_PASSWORD, "admin")
    empty_res = marks_service.get_student_results(non_student)
    assert empty_res["courses"] == []
    assert empty_res["sgpa"] is None
