"""Add (or remove) a large data set for the manual performance check (TC-PERF-01, Issue #26).

Adds 500 students and 20 courses taught by faculty1@pes.edu, with 125 students per course,
10 classes of attendance and full marks for everyone. Run scripts/seed.py first.

Usage (from the SE_Project folder, with the venv active):
    python scripts/seed_perf_data.py           # add the data (skipped if already there)
    python scripts/seed_perf_data.py --remove  # delete it again

All rows use the "PF" prefix (SRN PES1UG24PF001.., course UE24PF01..), so the normal
demo data is never touched.
"""

import os
import sys
from datetime import date, timedelta

# Let Python find the src package when run as "python scripts/seed_perf_data.py"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pylint: disable=wrong-import-position
from sqlalchemy import insert

from src.app import create_app
from src.extensions import db
from src.models import (
    Attendance,
    Course,
    Department,
    Enrollment,
    ExamRegistration,
    Marks,
    Section,
    Student,
    User,
)

STUDENTS = 500
COURSES = 20
COURSES_PER_STUDENT = 5
CLASSES = 10
DEPARTMENT = "Performance Test"


def remove():
    """Delete every row this script added."""
    course_ids = [c.id for c in Course.query.filter(Course.code.like("UE24PF%"))]
    student_ids = [s.id for s in Student.query.filter(Student.srn.like("PES1UG24PF%"))]
    for model in (Attendance, Marks, ExamRegistration, Enrollment):
        model.query.filter(model.course_id.in_(course_ids)).delete(synchronize_session=False)
    Course.query.filter(Course.id.in_(course_ids)).delete(synchronize_session=False)
    Student.query.filter(Student.id.in_(student_ids)).delete(synchronize_session=False)
    department = Department.query.filter_by(name=DEPARTMENT).first()
    if department:
        Section.query.filter_by(department_id=department.id).delete()
        db.session.delete(department)
    db.session.commit()
    print(f"Removed {len(student_ids)} students and {len(course_ids)} courses.")


def add():
    """Insert the large data set in a few bulk statements."""
    if Department.query.filter_by(name=DEPARTMENT).first():
        print("Performance data is already there (use --remove to delete it).")
        return
    faculty = User.query.filter_by(email="faculty1@pes.edu").first()
    if faculty is None:
        print("Run python scripts/seed.py first (faculty1@pes.edu is needed).")
        return

    department = Department(name=DEPARTMENT)
    db.session.add(department)
    db.session.flush()
    section = Section(name="PF", department_id=department.id)
    db.session.add(section)
    db.session.flush()

    db.session.execute(
        insert(Course),
        [
            {
                "code": f"UE24PF{index:02d}",
                "name": f"Performance Course {index}",
                "credits": 4,
                "department_id": department.id,
                "faculty_id": faculty.id,
                "syllabus": "",
            }
            for index in range(1, COURSES + 1)
        ],
    )
    db.session.execute(
        insert(Student),
        [
            {
                "srn": f"PES1UG24PF{index:03d}",
                "name": f"Perf Student {index}",
                "email": f"perf{index}@pes.edu",
                "semester": 4,
                "department_id": department.id,
                "section_id": section.id,
            }
            for index in range(1, STUDENTS + 1)
        ],
    )
    course_ids = [c.id for c in Course.query.filter(Course.code.like("UE24PF%"))]
    student_ids = [s.id for s in Student.query.filter(Student.srn.like("PES1UG24PF%"))]

    enrollments, marks, attendance = [], [], []
    for position, student_id in enumerate(student_ids):
        for offset in range(COURSES_PER_STUDENT):
            course_id = course_ids[(position + offset * 4) % COURSES]
            enrollments.append({"student_id": student_id, "course_id": course_id})
            marks.append(
                {
                    "student_id": student_id,
                    "course_id": course_id,
                    "isa1": 15,
                    "isa2": 16,
                    "assessment": 8,
                    "esa": 40,
                    "total": 79,
                    "grade": "B",
                    "grade_point": 8,
                }
            )
            for day in range(CLASSES):
                attendance.append(
                    {
                        "student_id": student_id,
                        "course_id": course_id,
                        "date": date(2026, 10, 1) + timedelta(days=day),
                        "present": (position + day) % 5 != 0,
                    }
                )
    db.session.execute(insert(Enrollment), enrollments)
    db.session.execute(insert(ExamRegistration), enrollments)
    db.session.execute(insert(Marks), marks)
    db.session.execute(insert(Attendance), attendance)
    db.session.commit()
    print(
        f"Added {STUDENTS} students, {COURSES} courses (faculty1@pes.edu), "
        f"{len(enrollments)} enrollments, {len(attendance)} attendance rows."
    )


def main():
    """Add the data, or remove it with --remove."""
    app = create_app()
    with app.app_context():
        if "--remove" in sys.argv:
            remove()
        else:
            add()


if __name__ == "__main__":
    main()
