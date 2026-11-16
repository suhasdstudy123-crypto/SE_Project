"""Unit tests for result analysis per course (SRS-F-022, Issue #25)."""

import pytest

from src.extensions import db
from src.models import Course, Department, Marks, Section, Student
from src.services import analysis_service


def test_tc_rpt_01_analysis_for_five_totals():
    """TC-RPT-01: totals 30, 40, 60, 80, 90 -> average 60, highest 90, lowest 30, pass 80%."""
    result = analysis_service.analyse_totals([30, 40, 60, 80, 90])

    assert result["students_appeared"] == 5
    assert result["average"] == 60
    assert result["highest"] == 90
    assert result["lowest"] == 30
    assert result["pass_percentage"] == 80
    assert result["grade_distribution"] == {
        "S": 1,
        "A": 1,
        "B": 0,
        "C": 1,
        "D": 0,
        "E": 1,
        "F": 1,
    }


def test_pass_mark_boundary():
    """Exactly 40 passes (grade E); 39.9 fails (grade F)."""
    result = analysis_service.analyse_totals([40, 39.9])
    assert result["pass_percentage"] == 50
    assert result["grade_distribution"]["E"] == 1
    assert result["grade_distribution"]["F"] == 1


def test_average_is_rounded_to_two_decimals():
    """Average 200/3 = 66.666... is shown as 66.67."""
    assert analysis_service.analyse_totals([60, 70, 70])["average"] == 66.67


def test_no_students_appeared():
    """With no exam results, numbers are empty and every grade count is 0."""
    result = analysis_service.analyse_totals([])
    assert result["students_appeared"] == 0
    assert result["average"] is None
    assert result["pass_percentage"] is None
    assert set(result["grade_distribution"].values()) == {0}


@pytest.fixture
def course_with_marks(app):
    """A course with one complete result (91), one complete fail (35) and one incomplete."""
    with app.app_context():
        department = Department(name="CSE")
        db.session.add(department)
        db.session.flush()
        section = Section(name="A", department_id=department.id)
        course = Course(code="UE24AM241A", name="SE", credits=4, department_id=department.id)
        db.session.add_all([section, course])
        db.session.flush()
        students = [
            Student(
                srn=f"PES1UG24AM00{index}",
                name=f"Student {index}",
                email=f"s{index}@pes.edu",
                semester=4,
                department_id=department.id,
                section_id=section.id,
            )
            for index in range(1, 4)
        ]
        db.session.add_all(students)
        db.session.flush()
        db.session.add_all(
            [
                Marks(
                    student_id=students[0].id,
                    course_id=course.id,
                    isa1=18,
                    isa2=19,
                    assessment=9,
                    esa=45,
                    total=91,
                ),
                Marks(
                    student_id=students[1].id,
                    course_id=course.id,
                    isa1=10,
                    isa2=10,
                    assessment=5,
                    esa=10,
                    total=35,
                ),
                # ESA not entered yet: did not take the exam, must be left out
                Marks(student_id=students[2].id, course_id=course.id, isa1=20, total=20),
            ]
        )
        db.session.commit()
        yield course


def test_course_analysis_counts_only_students_who_took_the_exam(course_with_marks):
    """Incomplete marks (no ESA yet) are not part of the analysis."""
    result = analysis_service.course_analysis(course_with_marks)

    assert result["course"]["code"] == "UE24AM241A"
    assert result["students_appeared"] == 2
    assert result["average"] == 63
    assert result["highest"] == 91
    assert result["lowest"] == 35
    assert result["pass_percentage"] == 50
    assert result["grade_distribution"]["S"] == 1
    assert result["grade_distribution"]["F"] == 1
