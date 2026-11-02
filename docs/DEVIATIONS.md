# Architectural and Design Deviations

This document logs intentional architectural, design, or implementation deviations from the initial Software Architecture Document (SAD) or Software Requirements Specification (SRS), along with rationales agreed upon by Team 12.

---

## 1. Faculty Marks API Endpoint Prefix (Issue #15)

- **Initial SAD Specification (SAD 3.5 / API Matrix):**
  `PUT /api/marks/<course_id>/<student_id>`
- **Implemented Routes:**
  - Primary: `PUT /api/faculty/marks/<course_id>/<student_id>` and `GET /api/faculty/marks/<course_id>`
  - Legacy Compatibility Alias: `PUT /api/marks/<course_id>/<student_id>`
- **Rationale:**
  Team 12 established a consistent role-prefixed routing architecture where all faculty endpoints reside under `/api/faculty/...` (e.g., `/api/faculty/attendance/...`, `/api/faculty/courses/...`). The primary faculty marks endpoints were aligned under `/api/faculty/marks`, and an alias was provided for backward compatibility with SAD 3.5 clients.
