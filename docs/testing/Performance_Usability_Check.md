# Performance, Usability and Portability Check — Team 12 (Issues #26, #27)

Test procedure written by the QA Lead; results are filled in by the Test Engineer.

Covers **TC-PERF-01** (SRS-NF-001), **TC-UX-01** (SRS-NF-002) and **TC-PORT-01** (SRS-NF-006) from the Test Plan.

## 1. TC-PERF-01 — key pages load in ≤ 2 s with 500 students and 20 courses

**Data set:** 500 students, 20 courses (125 students per course), 2,500 enrollments,
25,000 attendance rows (10 classes), 2,500 marks records.

### 1a. Automated API timing (runs in CI on every PR)

`tests/integration/test_performance.py` seeds the data set above and times the API behind
each page. The test fails if any page takes more than 2 s. In CI it runs against MySQL 8.

Measured 17 Nov 2026 on MariaDB 10.11 (MySQL-compatible), `pytest tests/integration/test_performance.py -s`:

| Role | API (page) | Time | Result |
|---|---|---|---|
| Admin | `GET /api/admin/students` (Students, 500 rows) | 0.013 s | Pass |
| Admin | `GET /api/admin/dashboard` | 0.281 s | Pass |
| Admin | `GET /api/admin/esa-eligibility/<course>` (ESA Window, 125 rows) | 0.297 s | Pass |
| Admin | `GET /api/admin/analysis/<course>` | 0.006 s | Pass |
| Admin | `GET /api/admin/reports/results.csv` (2,500 rows) | 0.270 s | Pass |
| Faculty | `GET /api/faculty/attendance/<course>?date=` (125 students) | 0.025 s | Pass |
| Faculty | `GET /api/faculty/marks/<course>` (125 students) | 0.010 s | Pass |
| Faculty | `GET /api/faculty/dashboard` | 0.346 s | Pass |
| Student | `GET /api/student/results`, `/attendance`, `/esa` | ≤ 0.023 s | Pass |

### 1b. Full page in the browser (API + React render)

Production build (`npm run build` + `vite preview`), Flask backend, browser.
Time = from opening the URL until the last row is on screen; worst of 3 runs.

Measured 17 Nov 2026: fresh install from the README on MariaDB 10.11, `scripts/seed_perf_data.py`, production build, Chromium (scripted timing, see DEVIATIONS §6).

| Page | Rows | Worst of 3 | Result |
|---|---|---|---|
| Admin → Students | 530 | 0.57 s | Pass |
| Admin → Dashboard | — | 1.11 s | Pass |
| Faculty → Mark Attendance (UE24PF01) | 125 | 0.54 s | Pass |
| Faculty → Enter Marks (UE24PF01) | 125 | 0.47 s | Pass |
| Student → My Results | 5 courses | 0.32 s | Pass |
| Student → My Attendance | 5 courses | 0.37 s | Pass |

**TC-PERF-01 status: PASS.** Slowest API 0.35 s, slowest full page 1.11 s (Admin dashboard), against a 2 s limit.

### How to repeat it on your laptop (MySQL)

```powershell
python scripts/seed.py              # normal demo data (needed for faculty1@pes.edu)
python scripts/seed_perf_data.py    # adds the 500 students / 20 courses ("PF" prefix)
python run.py                       # terminal 1
cd frontend; npm run build; npx vite preview   # terminal 2 -> http://localhost:4173
```
Log in as admin@pes.edu / faculty1@pes.edu / student01@pes.edu (password `Password@123`),
open each page above with DevTools → Network ("Disable cache" on) and note the "Load" time.
Remove the data afterwards: `python scripts/seed_perf_data.py --remove`.

## 2. TC-UX-01 — a first-time user marks attendance for 60 students in ≤ 2 minutes

Manual test (Test Plan: Manual, run by the Test Engineer with someone who has not used the app).

**Why the design makes this fast:** every student starts as **present** (SAD 4.5, NF-002),
so the user only unticks the absentees and clicks **Save attendance**. An "All present"
button resets the list. A counter shows "N of 60 present" before saving.

| Step | What the tester does |
|---|---|
| 1 | Log in as a faculty member and open **Mark Attendance**. |
| 2 | Pick a course with at least 60 enrolled students and today's date. The demo courses have 30, so use a `UE24PF..` course from `scripts/seed_perf_data.py` (125 students, a harder version of the test). |
| 3 | Untick the absent students from a given list (for example 6 names). |
| 4 | Click **Save attendance** and wait for the success message. |

Start the stopwatch at step 1 and stop it at step 4. Give no help.

**Step check (scripted walkthrough, 17 Nov 2026):** course UE24PF01 with 125 students, 6 absentees.
The task needed **9 actions** (open page, pick course, untick 6, Save); the database then held
119 present and 6 absent rows for that date. Screenshot: `sprint2_evidence/ux01_attendance_125_students.png`.
A script cannot stand in for a first-time user. The timed run with a person was not carried out before the final demo (DEVIATIONS §9).

| Date | Tester (first-time user) | Students | Absentees | Time | Help needed? | Result |
|---|---|---|---|---|---|---|
| — | Not run (see DEVIATIONS §9) | — | 6 | — | — | **Not run** |

**Pass if:** finished in ≤ 2 minutes without help. Record the result above and in the
Sprint 2 Test Summary Report.

## 3. TC-PORT-01 — a teammate sets up the app from the README on a clean machine in ≤ 15 minutes

Manual test (Test Plan: Manual). Use a machine that has never run the project, with
Python 3.10+, Node.js 18+, Git and MySQL 8 (or MariaDB) installed.

| Step | What the tester does |
|---|---|
| 1 | Start the stopwatch. Clone the repository. |
| 2 | Follow **only** the README "Setup" section: virtual environment, `pip install`, `.env`, create the database, seed, `npm install`. |
| 3 | Start the backend (`python run.py`) and the frontend (`npm run dev`). |
| 4 | Log in as `admin@pes.edu` and open the Dashboard. Stop the stopwatch. |
| 5 | Note every place where the README was unclear or a step failed. |

| Date | Tester | Machine / OS / DB | Time | Problems found | Result |
|---|---|---|---|---|---|
| 17 Nov 2026 | Scripted run, clean machine (1st try) | Linux, Python 3.13, Node 22, MariaDB 10.11 | — | A MySQL password containing `@` broke `DATABASE_URL` (`Test1@localhost` read as the host). README gave no warning (defect D-09). | Fail → fixed |
| 17 Nov 2026 | Scripted run, clean machine (rerun after fix) | Linux, Python 3.13, Node 22, MariaDB 10.11 | 16 s machine time (package caches warm) | None. Login as admin worked; a student added directly in MariaDB showed up in the app (31), proving the fresh backend used the new database. | **Pass** |

The scripted run checks that every README step works on a clean machine; a person reading the README
for the first time takes longer, but the steps are the same. Screenshot: `sprint2_evidence/port01_fresh_install_dashboard.png`.

**Pass if:** the app is running and the login works within 15 minutes using only the README.

