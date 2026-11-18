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

## 3. Student search for Faculty (Issue #22, SRS-F-007)

- **SRS-F-007:** Admin **and Faculty** can search and filter students by SRN, name, department, section or semester.
- **Implemented:** search and filters on the Admin Students page (`GET /api/admin/students?search=&department_id=&section_id=&semester=`). Faculty see their own enrolled students on the Attendance and Enter Marks pages, but have no separate search page.
- **Rationale:** SRS-F-007 is a "Could" requirement. Faculty only work with the students of their own courses, which are already listed on their pages. Faculty search is therefore left out of this release (decision to be confirmed by the Product Owner, Sidhant Holla).

## 4. TC-STU-03 and TC-SEC-07 test level (Test Plan)

- **Test Plan:** TC-STU-03 (duplicate SRN/email) and TC-SEC-07 (server-side validation) are listed as **Unit** tests.
- **Implemented:** both are checked as **Integration** tests (`test_tc_stu_03_duplicate_srn_is_rejected`, `test_tc_stu_03_duplicate_email_is_rejected`, `test_tc_sec_07_server_side_input_validation`), with unit tests for the validators in `tests/unit/test_validators.py`.
- **Rationale:** the duplicate check needs the database, and "rejected server-side" is best proven through the real API. The integration test covers more than a unit test would.

## 5. Issue #21 closed without its own pull request

- **Plan:** each card is delivered by its owner's pull request.
- **What happened:** every part of Issue #21 (SRS-F-021, student view of own attendance, ESA registrations, marks and results) was already built by other cards: My Attendance (PR #42, Issue #14), My Results (PR #45, Issue #16) and ESA Registration (PR #49, Issues #17–#20). Issue #21 was verified on `main` and closed with a comment linking those PRs.
- **Rationale:** writing the same pages again would have duplicated code.

## 6. Performance timing in the browser (TC-PERF-01)

- **Test Plan:** system tests are manual end-to-end flows (no browser-automation tool).
- **Implemented:** the API part of TC-PERF-01 is an automated test (`tests/integration/test_performance.py`) that runs in CI. The page load (API + React render) was timed with a short scripted Chromium run, because timing 6 pages × 3 runs by hand with a stopwatch is not accurate. The manual steps to repeat it are in `docs/testing/Performance_Usability_Check.md`.

## 7. Schedule

- **Plan (Deliverables Part-2):** Sprint 1 video by Oct 23; Sprint 2 (working product, 2-minute video, documentation, code freeze) Oct 26–30.
- **Actual:** the Sprint 1 video and test report were merged on Oct 30 (PR #43). Sprint 2 cards were merged between Oct 30 and Nov 12.
- **Rationale:** the team fell behind on Sprint 2 cards; work was reordered by dependency (marks → grades → reports) so the critical path finished first.

## 8. Git workflow exceptions

- **Rule:** every change reaches `main` through a reviewed pull request; no direct pushes.
- **Exceptions:**
  - Oct 18: commit `e3aa951` (renaming Gowri's tests to Test Plan IDs) was pushed directly to `main` with the teacher's approval.
  - Oct 30: PR #43 (Sprint 1 video and test report) was merged by the repository owner using the branch-protection bypass, without a second approval.
  - Nov 17: commits `fe813e1` and `d1338ac` (SRS v1.2: traceability-matrix status updated after testing) were pushed directly to `main` by the repository owner. They change only `docs/SRS_Student_Record_System_Team12.docx`, no code.
- All other changes went through pull requests with green CI and a review.

## 9. How the Sprint 2 system tests were run (Test Plan section on system testing)

- **Test Plan:** system tests are manual end-to-end flows run by the Test Engineer; TC-PORT-01 is a teammate setting up the app on a clean laptop; TC-UX-01 is a first-time user timed by hand.
- **What was done:**
  - The Sprint 2 end-to-end flows (E2E-16, E2E-20 to E2E-25) were run by a browser script against a fresh install. Each flow checks its own result and saves a screenshot (`docs/testing/sprint2_evidence/`). This is repeatable and leaves evidence, which a manual run does not.
  - TC-PORT-01 was run as a scripted clean install on Linux with MariaDB 10.11 (MySQL-compatible) instead of a teammate's Windows laptop with MySQL 8. It still caught a real setup bug (defect D-09, passwords containing `@`), which was fixed in the README, `.env.example` and `scripts/create_db.py`.
  - TC-UX-01: the steps were checked by script (9 actions for 125 students, saved correctly). The timed run with a first-time user was **not carried out** because of the time left before the final demo. The 2-minute target is therefore not formally measured; the design supports it (everyone starts as present, so only absentees are unticked).

## 10. Frontend dependency audit gate (Test Plan quality gate "npm audit: 0 high")

- **Planned:** CI fails if `npm audit` reports any high-severity issue.
- **What happened:** on 17–18 Nov 2026 a new advisory was published for `picomatch` (GHSA-fc5q-39xc-vjpf, ReDoS). It covers every released version, so no upgrade fixes it yet. `picomatch` is only used by developer tools (Vite, Vitest) through `tinyglobby`; it is not part of the built app that users download.
- **Change:** the blocking CI step is now `npm audit --omit=dev --audit-level=high` (packages that ship to users: 0 issues). The full audit still runs in CI and prints its findings, but does not block. When a fixed `picomatch` is released, the full audit can be made blocking again.


## 11. Documents updated after the sprints

- **SRS v1.2 (17 Nov 2026):** the traceability matrix (Section 8) now shows the final test status: 38 requirements Passed, SRS-NF-002 (TC-UX-01) Not run (see §9).
- **Test Plan v1.2 (18 Nov 2026):** test cases updated to match §1–4, §6 and §9 (Deliverables Part-3); schedule shows the actual dates from §7.
- **Branch coverage:** switched on for the backend (`pyproject.toml`, `branch = true`), so the CI coverage stage now measures statements and branches together. Report: `docs/testing/Backend_Branch_Coverage_Report.md` (93.3% of branches, 96.9% combined, gate ≥ 80%).
