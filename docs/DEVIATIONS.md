# Architectural and Design Deviations

This document logs intentional architectural, design, or implementation deviations from the initial Software Architecture Document (SAD) or Software Requirements Specification (SRS), along with rationales agreed upon by Team 12.

---

## 1. Faculty Marks API Endpoint Prefix (Issue #15)

- **Initial SAD Specification (SAD 3.5 / API Matrix):**
  `PUT /api/marks/<course_id>/<student_id>`
- **Implemented Routes:**
  `PUT /api/faculty/marks/<course_id>/<student_id>` and `GET /api/faculty/marks/<course_id>`
- **Rationale:**
  Team 12 established a consistent role-prefixed routing architecture where all faculty endpoints reside under `/api/faculty/...` (e.g., `/api/faculty/attendance/...`, `/api/faculty/courses/...`). The faculty marks endpoints were aligned under `/api/faculty/marks`. No alias is kept at the old SAD path, so there is one URL per action.

## 2. Student Results URL and TC-MRK-06 (Issue #16)

- **Test Plan TC-MRK-06 (SRS-F-021):**
  Student A opens own results (HTTP 200), then Student B's results URL (HTTP 403).
- **Implemented:**
  `GET /api/student/results` has no student id in the URL. The server takes the student from the login session, so a student can only ever get their own results.
- **Rationale:**
  Because there is no "other student's URL", there is nothing to answer with 403 (a URL like `/api/student/results/<id>` returns 404). This is safer than checking an id from the URL. `test_tc_mrk_06_student_sees_only_own_results` checks that Student A and Student B each get only their own marks.
