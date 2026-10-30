import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as attendanceApi from "../../api/attendance.js";
import StudentAttendancePage from "./StudentAttendancePage.jsx";

vi.mock("../../api/attendance.js");

const mockAttendance = [
  {
    course_id: 1,
    course_code: "UE24AM241A",
    course_name: "Software Engineering",
    credits: 4,
    held: 20,
    attended: 18,
    percentage: 90.0,
    shortage: false,
  },
  {
    course_id: 2,
    course_code: "UE24AM242A",
    course_name: "Machine Learning",
    credits: 4,
    held: 20,
    attended: 15,
    percentage: 75.0,
    shortage: false,
  },
  {
    course_id: 3,
    course_code: "UE24AM243A",
    course_name: "DBMS",
    credits: 4,
    held: 20,
    attended: 14,
    percentage: 70.0,
    shortage: true,
  },
];

beforeEach(() => {
  attendanceApi.getStudentAttendance.mockResolvedValue({ attendance: mockAttendance });
});

afterEach(() => vi.resetAllMocks());

describe("Student My Attendance page (issue #14, TC-ATT-04)", () => {
  it("renders attendance table with % and red Shortage badge when below 75%", async () => {
    render(<StudentAttendancePage />);
    expect(await screen.findByText("My Attendance")).toBeInTheDocument();

    expect(screen.getByText("UE24AM241A")).toBeInTheDocument();
    expect(screen.getByText("Software Engineering")).toBeInTheDocument();
    expect(screen.getByText("18 / 20")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();

    expect(screen.getByText("UE24AM242A")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();

    expect(screen.getByText("UE24AM243A")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();

    // 70% should have Shortage badge
    const shortageBadges = screen.getAllByText("Shortage");
    expect(shortageBadges.length).toBe(1);
    expect(shortageBadges[0]).toHaveClass("badge");

    // 90% and 75% should have OK badge
    const okBadges = screen.getAllByText("OK");
    expect(okBadges.length).toBe(2);
  });

  it("shows helpful message when student is not enrolled in any courses", async () => {
    attendanceApi.getStudentAttendance.mockResolvedValue({ attendance: [] });
    render(<StudentAttendancePage />);
    expect(await screen.findByText("You are not enrolled in any courses yet.")).toBeInTheDocument();
  });

  it("displays error message if attendance fails to load", async () => {
    attendanceApi.getStudentAttendance.mockRejectedValue({
      response: { status: 500, data: { error: "Failed to load attendance." } },
    });
    render(<StudentAttendancePage />);
    expect(await screen.findByText("Failed to load attendance.")).toBeInTheDocument();
  });
});
