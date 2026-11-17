# Sprint 2 test evidence (17 Nov 2026)

Evidence for the Sprint 2 Test Summary Report (`../Sprint2_Test_Summary_Report_Team12.docx`).
All runs used a fresh install from the README on MariaDB 10.11 with `scripts/seed.py` demo data.

| File | What it shows | Test |
|---|---|---|
| `e2e_results.json` | Result of every end-to-end flow (7/7 PASS) | E2E-16, E2E-20 – E2E-25 |
| `e2e_sprint2.js` | The browser script that ran the flows (each flow checks its own result) | — |
| `e2e20_admin_dashboard.png` | Dashboard counts match the data (30 students, 1 fee defaulter, 1 shortage) | E2E-20, TC-RPT-03 |
| `e2e21_search_filter.png` | Department filter: 10 of 30 students | E2E-21, TC-STU-05 |
| `e2e22_audit_override.png` | Eligibility override written to the audit log with its reason | E2E-22, TC-ESA-07 |
| `e2e22_student03_registered.png` | Student 03 registered after the override | E2E-22, TC-ESA-02 |
| `e2e23_window_closed.png` | Window closed: student sees the message, Register disabled | E2E-23, TC-ESA-03 |
| `e2e16_course_analysis.png` | Course analysis after marks were entered | E2E-16, TC-RPT-01 |
| `e2e16_student_results.png` | Student sees 91 / grade S / grade point 10 and SGPA | E2E-16, TC-MRK-04 |
| `attendance_UE24AM241A_export.csv` | The downloaded attendance report (header + 20 rows) | E2E-24, TC-RPT-02 |
| `port01_fresh_install_dashboard.png` | App running from a fresh clone set up only from the README | E2E-27, TC-PORT-01 |
| `ux01_attendance_125_students.png` | Attendance for 125 students with 6 absentees, before Save | E2E-26, TC-UX-01 |
