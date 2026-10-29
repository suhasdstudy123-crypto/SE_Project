import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as attendanceApi from "../../api/attendance.js";
import * as coursesApi from "../../api/courses.js";
import { todayIso } from "../../utils/dates.js";
import AttendancePage from "./AttendancePage.jsx";

vi.mock("../../api/attendance.js");
vi.mock("../../api/courses.js");

const courses = [
  { id: 10, code: "UE24AM241A", name: "Software Engineering" },
  { id: 11, code: "UE24AM243A", name: "DBMS" },
];
const roster = [
  {
    student_id: 1,
    srn: "PES1UG24AM001",
    name: "Student 01",
    present: true,
    percentage: 90.0,
    shortage: false,
  },
  {
    student_id: 2,
    srn: "PES1UG24AM002",
    name: "Student 02",
    present: true,
    percentage: 75.0,
    shortage: false,
  },
  {
    student_id: 3,
    srn: "PES1UG24AM003",
    name: "Student 03",
    present: true,
    percentage: 70.0,
    shortage: true,
  },
];

beforeEach(() => {
  coursesApi.listMyCourses.mockResolvedValue(courses);
  attendanceApi.getClassAttendance.mockResolvedValue({ recorded: false, students: roster });
});

afterEach(() => vi.resetAllMocks());

async function renderPage() {
  render(<AttendancePage />);
  await screen.findByText("PES1UG24AM001");
}

describe("Faculty Mark Attendance page (issues #13, #14)", () => {
  it("lists every enrolled student as present by default for today", async () => {
    await renderPage();
    expect(coursesApi.listMyCourses).toHaveBeenCalledWith("faculty");
    expect(attendanceApi.getClassAttendance).toHaveBeenCalledWith("10", todayIso());
    expect(screen.getByText("3 of 3 present")).toBeInTheDocument();
    expect(screen.getByText(/Not recorded yet/)).toBeInTheDocument();
    for (const box of screen.getAllByRole("checkbox")) expect(box).toBeChecked();
  });

  it("TC-ATT-03: displays attendance % and red Shortage badge when below 75%", async () => {
    await renderPage();
    expect(screen.getByText("Attendance %")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();

    // Shortage badge should be shown for Student 3 (70%)
    const shortageBadges = screen.getAllByText("Shortage");
    expect(shortageBadges.length).toBe(1);
    expect(shortageBadges[0]).toHaveClass("badge");
  });

  it("TC-ATT-01: unticking an absentee and saving sends every student's status", async () => {
    attendanceApi.saveClassAttendance.mockResolvedValue({ saved: 3, corrected: 0 });
    await renderPage();

    fireEvent.click(screen.getByLabelText("PES1UG24AM002 present"));
    expect(screen.getByText("2 of 3 present")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save attendance" }));

    expect(await screen.findByText("Attendance saved.")).toBeInTheDocument();
    expect(attendanceApi.saveClassAttendance).toHaveBeenCalledWith("10", todayIso(), [
      { student_id: 1, present: true },
      { student_id: 2, present: false },
      { student_id: 3, present: true },
    ]);
    expect(screen.getByText(/Already recorded/)).toBeInTheDocument();
  });

  it("clicking a row toggles it, and 'All present' resets everyone", async () => {
    await renderPage();
    fireEvent.click(screen.getByText("Student 01"));
    fireEvent.click(screen.getByText("Student 03"));
    expect(screen.getByText("1 of 3 present")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All present" }));
    expect(screen.getByText("3 of 3 present")).toBeInTheDocument();
  });

  it("TC-ATT-02: opening a past date shows saved values and reports corrections", async () => {
    attendanceApi.getClassAttendance.mockImplementation(async (_courseId, date) =>
      date === "2026-10-12"
        ? {
            recorded: true,
            students: roster.map((row) => ({ ...row, present: row.student_id !== 1 })),
          }
        : { recorded: false, students: roster },
    );
    attendanceApi.saveClassAttendance.mockResolvedValue({ saved: 3, corrected: 1 });
    await renderPage();

    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-10-12" } });
    expect(await screen.findByText(/Already recorded/)).toBeInTheDocument();
    expect(screen.getByLabelText("PES1UG24AM001 present")).not.toBeChecked();

    fireEvent.click(screen.getByLabelText("PES1UG24AM001 present"));
    fireEvent.click(screen.getByRole("button", { name: "Save attendance" }));

    expect(
      await screen.findByText("Attendance saved. 1 correction(s) recorded in the audit log."),
    ).toBeInTheDocument();
    expect(attendanceApi.saveClassAttendance).toHaveBeenCalledWith(
      "10",
      "2026-10-12",
      expect.arrayContaining([{ student_id: 1, present: true }]),
    );
  });

  it("loads the roster of another course when it is picked", async () => {
    await renderPage();
    fireEvent.change(screen.getByLabelText("Course"), { target: { value: "11" } });
    await waitFor(() =>
      expect(attendanceApi.getClassAttendance).toHaveBeenLastCalledWith("11", todayIso()),
    );
  });

  it("shows the server's message when saving is refused", async () => {
    attendanceApi.saveClassAttendance.mockRejectedValue({
      response: {
        status: 403,
        data: { error: "Only the faculty assigned to this course can mark attendance." },
      },
    });
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Save attendance" }));
    expect(
      await screen.findByText("Only the faculty assigned to this course can mark attendance."),
    ).toBeInTheDocument();
  });

  it("shows the server's message when the roster cannot be loaded", async () => {
    attendanceApi.getClassAttendance.mockRejectedValue({
      response: { status: 400, data: { error: "Attendance cannot be marked for a future date." } },
    });
    render(<AttendancePage />);
    expect(
      await screen.findByText("Attendance cannot be marked for a future date."),
    ).toBeInTheDocument();
  });

  it("explains when the faculty member has no courses", async () => {
    coursesApi.listMyCourses.mockResolvedValue([]);
    render(<AttendancePage />);
    expect(await screen.findByText("You are not assigned to any courses yet.")).toBeInTheDocument();
    expect(attendanceApi.getClassAttendance).not.toHaveBeenCalled();
  });

  it("explains when nobody is enrolled in the course", async () => {
    attendanceApi.getClassAttendance.mockResolvedValue({ recorded: false, students: [] });
    render(<AttendancePage />);
    expect(await screen.findByText("No students are enrolled in this course.")).toBeInTheDocument();
  });

  it("todayIso returns the local date as YYYY-MM-DD", () => {
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
