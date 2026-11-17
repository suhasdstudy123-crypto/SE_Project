// Sprint 2 end-to-end system flows (Test Plan: system tests), run in a real browser
// against a fresh install (README setup, MySQL/MariaDB, `python scripts/seed.py`).
// Each flow checks its own result and saves a screenshot.
//
// Run (backend on :5000 and `npm run dev` on :5173 already started, fresh seed data):
//   npm install playwright && npx playwright install chromium
//   node docs/testing/sprint2_evidence/e2e_sprint2.js docs/testing/sprint2_evidence
const fs = require("fs");
const { chromium } = require("playwright");
const B = "http://localhost:5173";
const OUT = process.argv[2];
const results = [];

async function login(browser, email) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, acceptDownloads: true });
  const page = await ctx.newPage();
  await page.goto(`${B}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("Password@123");
  await page.getByRole("button", { name: /log in/i }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  return { ctx, page };
}
async function open(page, path) {
  await page.goto(B + path);
  await page.waitForLoadState("networkidle");
}
function check(cond, msg) {
  if (!cond) throw new Error(msg);
}
async function flow(id, name, fn) {
  try {
    const observed = await fn();
    results.push({ id, name, status: "PASS", observed });
    console.log(`PASS ${id} ${name} :: ${observed}`);
  } catch (e) {
    results.push({ id, name, status: "FAIL", observed: String(e.message).split("\n")[0] });
    console.log(`FAIL ${id} ${name} :: ${e.message.split("\n")[0]}`);
  }
}
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png` });
const rowText = (page, re) => page.getByRole("row", { name: re }).first().innerText();

(async () => {
  const browser = await chromium.launch();

  await flow("E2E-20", "Dashboards show live counts (TC-RPT-03)", async () => {
    const { ctx, page } = await login(browser, "admin@pes.edu");
    await page.getByText("Total students").waitFor();
    const text = await page.locator("main").innerText();
    check(/Total students\s+30/.test(text), "admin total students is not 30");
    check(/Fee defaulters\s+1/.test(text), "fee defaulters is not 1");
    check(/below 75% attendance\s+1/.test(text), "shortage count is not 1");
    await shot(page, "e2e20_admin_dashboard");
    await ctx.close();
    return "Admin dashboard: 30 students, 5 courses, 1 fee defaulter (Student 30), 1 shortage (Student 03) — matches seed data";
  });

  await flow("E2E-21", "Search and filter students (TC-STU-05)", async () => {
    const { ctx, page } = await login(browser, "admin@pes.edu");
    await open(page, "/admin/students");
    await page.getByLabel("Search students").fill("PES1UG24CS030");
    await page.getByText("Showing 1 of").waitFor();
    await page.getByLabel("Search students").fill("");
    await page.getByLabel("Filter by department").selectOption({ label: "CSE" });
    await page.getByText("Showing 10 of").waitFor();
    await shot(page, "e2e21_search_filter");
    await ctx.close();
    return "Search by SRN → 1 student; department CSE → 10 of 30 students";
  });

  await flow("E2E-22", "ESA blocked by shortage, Admin override, student registers (TC-ESA-05, TC-ESA-07, TC-ESA-02)", async () => {
    let s = await login(browser, "student03@pes.edu");
    await open(s.page, "/student/esa");
    const before = await rowText(s.page, /UE24AM241A/);
    check(/Not eligible/.test(before) && /70%/.test(before), "Student 03 should be blocked at 70%");
    check(await s.page.getByRole("row", { name: /UE24AM241A/ }).getByRole("button", { name: "Register" }).isDisabled(), "Register should be disabled");
    await s.ctx.close();

    const a = await login(browser, "admin@pes.edu");
    await open(a.page, "/admin/esa");
    await a.page.getByRole("button", { name: "Override PES1UG24AM003" }).click();
    await a.page.getByLabel(/reason/i).fill("Medical certificate submitted");
    await a.page.locator(".modal-footer button[type=submit]").click();
    await a.page.getByText("Medical certificate submitted").first().waitFor();
    await open(a.page, "/admin/audit");
    const audit = await a.page.locator("main").innerText();
    check(/override/i.test(audit), "no override row in audit log");
    await shot(a.page, "e2e22_audit_override");
    await a.ctx.close();

    s = await login(browser, "student03@pes.edu");
    await open(s.page, "/student/esa");
    await s.page.getByRole("row", { name: /UE24AM241A/ }).getByRole("button", { name: "Register" }).click();
    await s.page.getByRole("row", { name: /UE24AM241A/ }).getByText("Registered", { exact: true }).waitFor();
    await shot(s.page, "e2e22_student03_registered");
    await s.ctx.close();
    return "Blocked (70% < 75%, Register disabled) → Admin override with reason → audit row written → Student 03 registered";
  });

  await flow("E2E-23", "Closed ESA window blocks registration (TC-ESA-03)", async () => {
    const a = await login(browser, "admin@pes.edu");
    await open(a.page, "/admin/esa");
    await a.page.getByRole("button", { name: "Close registration" }).click();
    await a.page.getByRole("button", { name: "Open registration" }).waitFor();
    const s = await login(browser, "student02@pes.edu");
    await open(s.page, "/student/esa");
    await s.page.getByText("ESA registration is closed").waitFor();
    const disabled = await s.page.getByRole("row", { name: /UE24AM241A/ }).getByRole("button", { name: "Register" }).isDisabled();
    await shot(s.page, "e2e23_window_closed");
    await a.page.getByRole("button", { name: "Open registration" }).click();
    await a.page.getByRole("button", { name: "Close registration" }).waitFor();
    await s.ctx.close();
    await a.ctx.close();
    check(disabled, "Register should be disabled when the window is closed");
    return "Admin closes window → student sees 'registration is closed', Register disabled → window reopened";
  });

  await flow("E2E-16", "Complete academic workflow: attendance → ESA → marks → results → analysis (deferred from Sprint 1)", async () => {
    let s = await login(browser, "student01@pes.edu");
    await open(s.page, "/student/attendance");
    check(/90%/.test(await rowText(s.page, /UE24AM241A/)), "Student 01 attendance should be 90%");
    await open(s.page, "/student/esa");
    await s.page.getByRole("row", { name: /UE24AM241A/ }).getByRole("button", { name: "Register" }).click();
    await s.page.getByRole("row", { name: /UE24AM241A/ }).getByText("Registered", { exact: true }).waitFor();
    await s.ctx.close();

    const f = await login(browser, "faculty1@pes.edu");
    await open(f.page, "/faculty/marks");
    await f.page.getByLabel("PES1UG24AM001 ISA-1").fill("18");
    await f.page.getByLabel("PES1UG24AM001 ISA-2").fill("19");
    await f.page.getByLabel("PES1UG24AM001 Assessment").fill("9");
    await f.page.getByLabel("PES1UG24AM001 ESA").fill("45");
    await f.page.getByRole("row", { name: /PES1UG24AM001/ }).getByRole("button", { name: "Save" }).click();
    await f.page.waitForTimeout(800);
    await open(f.page, "/faculty/marks");
    const row = await rowText(f.page, /PES1UG24AM001/);
    check(/91/.test(row) && /\bS\b/.test(row), `faculty row should show 91 / S, got: ${row}`);
    await open(f.page, "/faculty/reports");
    await f.page.getByTestId("Students appeared").filter({ hasText: "1" }).waitFor();
    await shot(f.page, "e2e16_course_analysis");
    await f.ctx.close();

    s = await login(browser, "student01@pes.edu");
    await open(s.page, "/student/results");
    const res = await rowText(s.page, /UE24AM241A/);
    check(/91/.test(res) && /\bS\b/.test(res) && /10/.test(res), `results row wrong: ${res}`);
    await shot(s.page, "e2e16_student_results");
    await s.ctx.close();
    return "90% attendance → registered for ESA → faculty saved 18/19/9/45 = 91 → grade S → student sees S, grade point 10 → analysis shows 1 student appeared";
  });

  await flow("E2E-24", "CSV export downloads a correct file (TC-RPT-02)", async () => {
    const { ctx, page } = await login(browser, "admin@pes.edu");
    await open(page, "/admin/results");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export attendance CSV" }).click(),
    ]);
    const file = `${OUT}/attendance_export.csv`;
    await download.saveAs(file);
    const lines = fs.readFileSync(file, "utf8").replace(/^﻿/, "").trim().split(/\r?\n/);
    check(lines[0].startsWith("SRN,Name,Course,Classes Attended,Classes Held,Attendance %,Status"), "wrong header");
    check(lines.length === 21, `expected header + 20 rows, got ${lines.length}`);
    const s3 = lines.find((l) => l.startsWith("PES1UG24AM003"));
    check(/,14,20,70\.0,Shortage$/.test(s3), `Student 03 row wrong: ${s3}`);
    await ctx.close();
    return `${download.suggestedFilename()}: header + 20 rows; Student 03 = 14/20, 70.0%, Shortage`;
  });

  await flow("E2E-25", "Role isolation on Sprint 2 pages (TC-SEC-02, TC-MRK-06)", async () => {
    const s = await login(browser, "student01@pes.edu");
    await open(s.page, "/admin/esa");
    const url1 = s.page.url();
    await open(s.page, "/faculty/marks");
    const url2 = s.page.url();
    const api = await s.page.evaluate(async () => (await fetch("/api/faculty/marks/1")).status);
    await s.ctx.close();
    check(!url1.includes("/admin") && !url2.includes("/faculty"), "student reached another role's page");
    check(api === 403, `API should be 403, got ${api}`);
    return "Student opening /admin/esa and /faculty/marks is sent back to the student area; GET /api/faculty/marks/1 → 403";
  });

  fs.writeFileSync(`${OUT}/e2e_results.json`, JSON.stringify(results, null, 1));
  await browser.close();
  console.log(`${results.filter((r) => r.status === "PASS").length}/${results.length} flows passed`);
})();
