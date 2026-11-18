# Backend Branch Coverage Report — Student Record System (Team 12)

Part-3 deliverable: **Branch Coverage Report**. Companion to the Sprint 2 Test Summary Report
(`docs/testing/Sprint2_Test_Summary_Report_Team12.docx`), which reports statement coverage and the
frontend branch coverage (88.02%).

## 1. What branch coverage measures
Statement (line) coverage checks that every line ran at least once. **Branch coverage** checks that
every decision (`if`/`else`, loop conditions) was tested **both ways**: for example, in the ESA
eligibility rule both the "eligible" and the "blocked" paths.

## 2. How it was run
- Date: 18 November 2026, on `main` after PR #52 (final code).
- Command: `pytest tests --cov=src --cov-branch --cov-report=term-missing`
  (branch coverage is also switched on permanently in `pyproject.toml`: `[tool.coverage.run] branch = true`,
  so the CI coverage stage measures it on every push and pull request).
- Tests: the full backend suite, 321 tests (138 unit + 183 integration), database = in-memory SQLite
  (the same setup as the CI coverage stage). Result: **321 passed, 0 failed**.

## 3. Results
| Measure | Covered | Total | Result |
|---|---|---|---|
| Statements (lines) | 1782 | 1823 | **97.8%** |
| Branches | 407 | 436 | **93.3%** |
| Combined (statements + branches) | – | – | **96.9%** |
| Quality gate (Test Plan / SRS-NF-004) | | | ≥ 80% → **PASS** |

All business-rule services have **100% branch coverage**: attendance (% and 75% shortage),
marks (grades, SGPA), analysis, reports, audit, auth, course and seed services, `rbac.py` and
`validators.py`. `esa_service.py` (eligibility) is at 39 of 40 branches.

The 29 uncovered branches:
- **28 are in route files**, mostly error-handling paths for unusual requests: the early "access denied"
  return repeated in each department/section route (the RBAC logic itself is 100% covered in
  `rbac.py`), rejection of malformed request bodies (not a JSON object, missing or blank name,
  `department_id` / `section_id` not a number, department or section not found, semester outside 1-8),
  the department filter of the Admin student search (`routes/students.py` line 118; search by
  SRN/name and the section filter are tested), a student record or enrollment not found
  (`routes/attendance.py`), an out-of-range audit-log page size (`routes/audit.py`), and saving a
  fee status that is unchanged (`routes/fees.py`).
- **1 is in `esa_service.py`** (`set_window`, line 73 -> 79): opening the ESA window when it is
  already open, which leaves it unchanged.

None of them is in a business rule (eligibility, attendance %, marks limits, grades, SGPA).

## 4. Branch coverage per file (files with at least one decision)
| File | Branches | Covered | Missed | Branch coverage |
|---|---|---|---|---|
| `src/rbac.py` | 16 | 16 | 0 | 100.0% |
| `src/routes/attendance.py` | 8 | 6 | 2 | 75.0% |
| `src/routes/audit.py` | 2 | 1 | 1 | 50.0% |
| `src/routes/auth.py` | 4 | 4 | 0 | 100.0% |
| `src/routes/courses.py` | 2 | 2 | 0 | 100.0% |
| `src/routes/dashboard.py` | 10 | 10 | 0 | 100.0% |
| `src/routes/departments.py` | 46 | 31 | 15 | 67.4% |
| `src/routes/esa.py` | 4 | 4 | 0 | 100.0% |
| `src/routes/fees.py` | 14 | 11 | 3 | 78.6% |
| `src/routes/marks.py` | 2 | 1 | 1 | 50.0% |
| `src/routes/my_courses.py` | 4 | 4 | 0 | 100.0% |
| `src/routes/reports.py` | 10 | 10 | 0 | 100.0% |
| `src/routes/students.py` | 38 | 32 | 6 | 84.2% |
| `src/services/analysis_service.py` | 12 | 12 | 0 | 100.0% |
| `src/services/attendance_service.py` | 34 | 34 | 0 | 100.0% |
| `src/services/audit_service.py` | 8 | 8 | 0 | 100.0% |
| `src/services/auth_service.py` | 10 | 10 | 0 | 100.0% |
| `src/services/course_service.py` | 44 | 44 | 0 | 100.0% |
| `src/services/esa_service.py` | 40 | 39 | 1 | 97.5% |
| `src/services/marks_service.py` | 44 | 44 | 0 | 100.0% |
| `src/services/report_service.py` | 10 | 10 | 0 | 100.0% |
| `src/services/seed_service.py` | 48 | 48 | 0 | 100.0% |
| `src/validators.py` | 26 | 26 | 0 | 100.0% |

## 5. Full coverage output
```
Name                                 Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------------
src/__init__.py                          0      0      0      0   100%
src/app.py                              64      2      0      0    97%   73, 81
src/config.py                           15      0      0      0   100%
src/extensions.py                        6      0      0      0   100%
src/models/__init__.py                   8      0      0      0   100%
src/models/attendance.py                13      0      0      0   100%
src/models/audit.py                     15      0      0      0   100%
src/models/course.py                    31      0      0      0   100%
src/models/exam.py                      35      0      0      0   100%
src/models/marks.py                     19      0      0      0   100%
src/models/student.py                   57      0      0      0   100%
src/models/user.py                      33      0      0      0   100%
src/rbac.py                             40      0     16      0   100%
src/routes/__init__.py                   0      0      0      0   100%
src/routes/analysis.py                  27      0      0      0   100%
src/routes/attendance.py                55      2      8      2    94%   72, 76
src/routes/audit.py                     16      1      2      1    89%   22
src/routes/auth.py                      32      0      4      0   100%
src/routes/courses.py                   59      0      2      0   100%
src/routes/dashboard.py                 29      0     10      0   100%
src/routes/departments.py              122     15     46     15    82%   56, 79, 89, 97, 109, 113, 125, 135, 157, 161, 168, 171, 174, 186, 199
src/routes/esa.py                       56      0      4      0   100%
src/routes/fees.py                      56      5     14      3    89%   34, 52, 89->102, 104-106
src/routes/health.py                     5      0      0      0   100%
src/routes/marks.py                     37      1      2      1    95%   43
src/routes/my_courses.py                32      0      4      0   100%
src/routes/rbac_routes.py                9      0      0      0   100%
src/routes/reports.py                   47      0     10      0   100%
src/routes/students.py                 117     15     38      6    86%   27, 58, 61, 65, 69, 119, 144-146, 171-173, 190-192
src/services/__init__.py                 0      0      0      0   100%
src/services/analysis_service.py        32      0     12      0   100%
src/services/attendance_service.py     104      0     34      0   100%
src/services/audit_service.py           18      0      8      0   100%
src/services/auth_service.py            43      0     10      0   100%
src/services/course_service.py         114      0     44      0   100%
src/services/esa_service.py            132      0     40      1    99%   73->79
src/services/marks_service.py          121      0     44      0   100%
src/services/report_service.py          37      0     10      0   100%
src/services/seed_service.py           134      0     48      0   100%
src/validators.py                       53      0     26      0   100%
--------------------------------------------------------------------------------
TOTAL                                 1823     41    436     29    97%
```
`Branch` = number of branch outcomes, `BrPart` = decisions where only one side was tested,
`Missing` = line numbers not run and branch jumps (`a->b`) not taken.
