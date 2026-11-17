# Student Record System

Software Engineering Mini Project — Team 12, PES University.

A web application to manage student records: departments and sections, courses, enrollment,
attendance, fee status, ESA (exam) registration with eligibility rules, marks, grades, SGPA and result analysis.

**Status (Nov 2026):** all 27 backlog cards of Sprint 1 and Sprint 2 are done and merged through pull requests.
Changes from the SRS / SAD / Test Plan are listed in [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md).

## What each role can do
| Role | Features |
|---|---|
| **Admin** | Dashboard (students, courses, fee defaulters, attendance shortages) · departments and sections · add / edit / delete / search students · courses, syllabus and enrollment · fee status · open/close the ESA registration window, see eligibility, override with a reason · audit log · CSV reports (students, attendance, results) · result analysis of any course |
| **Faculty** | Dashboard for own courses · mark and correct attendance (everyone starts as present) with attendance % and shortage flag · enter marks (ISA-1 /20, ISA-2 /20, Assessment /10, ESA /50) with grade · course analysis (average, highest, lowest, pass %, grade distribution) · CSV reports for own courses |
| **Student** | Own courses and syllabus · own attendance with shortage warning · ESA registration / drop (only if fees paid and attendance ≥ 75%, or an Admin override) · own results with grade and SGPA · class result analysis of own courses |

Security: hashed passwords, account lock after 5 wrong passwords, role checks on every API route,
CSRF protection, parameterised queries (no SQL injection), server-side validation, audit log for
changes to marks, attendance, fee status and eligibility overrides.

## Team
| Name | Role |
|---|---|
| Suhas D | QA Lead, Developer |
| Gowri T N | Test Engineer, Developer |
| Ankit Umadi | Developer (defect triage lead) |
| Sidhant Holla | Product Owner, Developer |

## Tech stack
- **Frontend:** React 18 + Vite, React-Bootstrap, React Router, axios — in `frontend/`
- **Backend:** Python 3.10+ with Flask (JSON REST API under `/api`), Flask-Login, Flask-WTF (CSRF) — in `src/`
- **Database:** MySQL 8 via SQLAlchemy (tests use in-memory SQLite)
- **Testing & quality:** pytest, pytest-cov, pylint, black, bandit · Vitest, React Testing Library, ESLint, Prettier, npm audit
- **CI/CD:** GitHub Actions

## Folder structure
```
SE_Project/
├── src/                  # Flask backend (Python)
│   ├── app.py            #   creates the app
│   ├── config.py         #   settings (reads .env)
│   ├── extensions.py     #   database, login, CSRF objects
│   ├── routes/           #   API endpoints (one file per module)
│   ├── services/         #   business rules (eligibility, grading, ...)
│   └── models/           #   database tables
├── tests/
│   ├── unit/             # tests for single functions
│   └── integration/      # tests for API + database together
├── frontend/             # React app
│   └── src/              #   pages, components, api client, tests (*.test.jsx)
├── .github/workflows/    # CI/CD pipeline (ci.yml)
├── docs/                 # SRS, SAD, Test Plan, deviations, test reports, demo video
├── scripts/              # create the database, demo data, users, performance data
├── requirements.txt      # Python libraries
├── .env.example          # copy to .env and fill in your MySQL password
└── run.py                # starts the backend
```

## First-time setup (Windows, PowerShell)
You need: Git, Python 3.10+, Node.js 20 or newer, MySQL 8.

```powershell
# 1. Get the code
git clone https://github.com/suhasdstudy123-crypto/SE_Project.git
cd SE_Project

# 2. Backend: create and activate a virtual environment, then install libraries
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Your settings: copy the example and put YOUR MySQL password in .env
#    If the password has @ : / # or %, write @ as %40, : as %3A, / as %2F, # as %23, % as %25
#    (example: password Root@123 -> mysql+pymysql://root:Root%40123@localhost:3306/student_records)
copy .env.example .env

# 4. Frontend: install libraries
cd frontend
npm install
cd ..
```
If `Activate.ps1` is blocked, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Create the database once (reads your `.env`, safe to re-run):
```powershell
python scripts/create_db.py
```

Load the shared demo data (1 Admin, 3 Faculty, 30 Students, 2 Departments, 3 Sections, 5 Courses, sample attendance; safe to re-run):
```powershell
python scripts/seed.py
```

Or create an individual login account interactively:
```powershell
python scripts/create_user.py admin@pes.edu "Admin User" admin
```
Roles: `admin`, `faculty`, `student`.

## Running the app (two terminals)
```powershell
# Terminal 1 — backend (http://localhost:5000)
.venv\Scripts\Activate.ps1
python run.py

# Terminal 2 — frontend (http://localhost:5173)
cd frontend
npm run dev
```
Open http://localhost:5173 and log in. Demo accounts from `scripts/seed.py` (password `Password@123`):

| Role | Email |
|---|---|
| Admin | `admin@pes.edu` |
| Faculty | `faculty1@pes.edu`, `faculty2@pes.edu`, `faculty3@pes.edu` |
| Student | `student01@pes.edu` … `student30@pes.edu` |

## Checks to run before every pull request
These are the same checks the CI pipeline runs.
```powershell
# Backend
pytest tests --cov=src --cov-fail-under=80   # unit + integration tests, coverage must be >= 80%
pylint src/ --fail-under=7.0                 # code quality must be >= 7.0
black --check src tests scripts              # formatting (run "black src tests scripts" to fix)
bandit -r src --severity-level high          # security scan: no high-severity issues

# Frontend (inside frontend/)
npm run lint                                 # ESLint: 0 errors
npm run format:check                         # Prettier (run "npm run format" to fix)
npm run coverage                             # Vitest tests, line coverage must be >= 60%
npm run build                                # production build
npm audit --audit-level=high                 # no high-severity vulnerable packages
```
On Windows, `npm run format:check` may warn about every file because Git checks files out with
Windows line endings (CRLF). CI runs on Linux with the stored LF files, so it is not affected.

## CI/CD pipeline
`.github/workflows/ci.yml` runs on every pull request to `main` and every push to `main`:

1. **Build**: install the backend and check the app starts
2. **Test**: unit tests, then integration tests on a real MySQL 8 database
3. **Coverage**: pytest-cov, fails below 80% (HTML report uploaded as an artifact)
4. **Lint**: pylint, fails below 7.0 (report uploaded as an artifact)
5. **Format**: black --check
6. **Security**: bandit (JSON report uploaded as an artifact)
7. **Package**: zips the application as a downloadable artifact

A separate **Frontend** job runs ESLint, Prettier, Vitest with coverage, the production build and
npm audit. Branch protection on `main` needs a pull request, 1 approval and all checks green.

## Testing
- Test names follow the Test Plan IDs: `test_tc_<id>_<what it checks>`, for example
  `test_tc_esa_06_attendance_exactly_75_percent_is_eligible` for **TC-ESA-06**.
- `tests/unit/`: one function at a time (grades, SGPA, eligibility, validators, ...).
- `tests/integration/`: API + services + database together (on MySQL in CI).
- `frontend/src/**/*.test.jsx`: React pages with Vitest and React Testing Library.
- **Performance (TC-PERF-01):** `tests/integration/test_performance.py` seeds 500 students and
  20 courses and checks every key page answers in ≤ 2 s. To try it in the browser:
  `python scripts/seed_perf_data.py` (and `--remove` to delete it again).
- Results: [`docs/testing/`](docs/testing/) has the Sprint 1 and Sprint 2 Test Summary Reports and
  the performance and usability check.

## How we work (Git workflow)
1. Pick your card on the GitHub Project board and move it to **In Progress**.
2. `git checkout main` → `git pull` → `git checkout -b feature/<issue-number>-<short-name>`
3. Write code + tests, run the checks above, commit with a clear message.
4. `git push -u origin <branch>` and open a Pull Request with `Closes #<issue-number>` in the description.
5. A teammate reviews; once CI is green and approved, it is merged. Never push directly to `main`.

## Documents
| File | What it is |
|---|---|
| [`docs/SRS_Student_Record_System_Team12.docx`](docs/SRS_Student_Record_System_Team12.docx) | Software Requirements Specification (v1.1) |
| [`docs/SAD_Student_Record_System_Team12.docx`](docs/SAD_Student_Record_System_Team12.docx) | Software Architecture Document (v1.1) |
| [`docs/STP_Student_Record_System_Team12.docx`](docs/STP_Student_Record_System_Team12.docx) | Software Test Plan (v1.1) |
| [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md) | Where the build differs from the SRS / SAD / Test Plan, and why |
| [`docs/testing/`](docs/testing/) | Test Summary Reports (Sprint 1, Sprint 2), performance and usability check |
| [`docs/videos/`](docs/videos/) | Sprint demo videos |
