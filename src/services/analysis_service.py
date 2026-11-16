"""Result analysis per course (SRS-F-022, Issue #25, TC-RPT-01).

For one course: how many students took the exam, the average, highest and lowest
total, the pass percentage and how many students got each grade.
"Took the exam" means all four marks (ISA-1, ISA-2, Assessment, ESA) are entered,
which is the same rule used to give a grade (SRS-F-020).
"""

from src.models import Enrollment, Marks
from src.models.user import Role
from src.services.marks_service import calculate_grade_and_points, grade_for_marks

GRADES = ("S", "A", "B", "C", "D", "E", "F")
PASS_MARK = 40  # below 40 is grade F (BR-5)


class AnalysisError(Exception):
    """An analysis problem, with the HTTP status code."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def analyse_totals(totals):
    """Average, highest, lowest, pass % and grade counts for a list of totals out of 100."""
    distribution = {grade: 0 for grade in GRADES}
    for total in totals:
        grade, _ = calculate_grade_and_points(total)
        distribution[grade] += 1

    count = len(totals)
    if count == 0:
        return {
            "students_appeared": 0,
            "average": None,
            "highest": None,
            "lowest": None,
            "pass_percentage": None,
            "grade_distribution": distribution,
        }

    passed = sum(1 for total in totals if total >= PASS_MARK)
    return {
        "students_appeared": count,
        "average": round(sum(totals) / count, 2),
        "highest": max(totals),
        "lowest": min(totals),
        "pass_percentage": round(passed * 100 / count, 2),
        "grade_distribution": distribution,
    }


def check_access(course, user, student=None):
    """Admin: any course. Faculty: only their own course. Student: only an enrolled course."""
    if user.role == Role.ADMIN:
        return
    if user.role == Role.FACULTY:
        if course.faculty_id != user.id:
            raise AnalysisError("You are not assigned to this course.", 403)
        return
    if (
        student is None
        or not Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    ):
        raise AnalysisError("You are not enrolled in this course.", 403)


def course_analysis(course):
    """Result analysis for one course, using only students who took the exam."""
    totals = [
        record.total
        for record in Marks.query.filter_by(course_id=course.id).all()
        if grade_for_marks(record)[0] is not None
    ]
    return {
        "course": {
            "id": course.id,
            "code": course.code,
            "name": course.name,
            "credits": course.credits,
        },
        **analyse_totals(totals),
    }
