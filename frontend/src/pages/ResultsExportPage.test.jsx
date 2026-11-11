import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { listCourses, listMyCourses } from "../api/courses.js";
import { downloadReport } from "../api/reports.js";
import ResultsExportPage from "./ResultsExportPage.jsx";

vi.mock("../api/reports.js");
vi.mock("../api/courses.js");

const COURSES = [
  { id: 7, code: "UE24AM241A", name: "Software Engineering" },
  { id: 8, code: "UE24AM242A", name: "Machine Learning" },
];

afterEach(() => vi.resetAllMocks());

describe("ResultsExportPage (issue #23, SRS-F-023)", () => {
  it("Admin exports the attendance report of the chosen course", async () => {
    listCourses.mockResolvedValue(COURSES);
    downloadReport.mockResolvedValue(undefined);
    render(<ResultsExportPage role="admin" />);

    const select = await screen.findByLabelText("Course");
    await screen.findByRole("option", { name: "UE24AM242A - Machine Learning" });
    fireEvent.change(select, { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Export attendance CSV" }));

    await waitFor(() =>
      expect(downloadReport).toHaveBeenCalledWith(
        "/admin/reports/attendance.csv?course_id=8",
        "attendance_UE24AM242A.csv",
      ),
    );
    expect(await screen.findByText("Report downloaded.")).toBeInTheDocument();
  });

  it("Faculty exports results for their own courses", async () => {
    listMyCourses.mockResolvedValue(COURSES.slice(0, 1));
    downloadReport.mockResolvedValue(undefined);
    render(<ResultsExportPage role="faculty" />);

    await screen.findByRole("option", { name: "UE24AM241A - Software Engineering" });
    expect(listMyCourses).toHaveBeenCalledWith("faculty");
    fireEvent.click(screen.getByRole("button", { name: "Export results CSV" }));

    await waitFor(() =>
      expect(downloadReport).toHaveBeenCalledWith("/faculty/reports/results.csv", "results.csv"),
    );
  });

  it("shows the server's error when an export fails", async () => {
    listCourses.mockResolvedValue(COURSES);
    downloadReport.mockRejectedValue({ response: { data: { error: "Course not found." } } });
    render(<ResultsExportPage role="admin" />);

    await screen.findByRole("option", { name: "UE24AM241A - Software Engineering" });
    fireEvent.click(screen.getByRole("button", { name: "Export attendance CSV" }));

    expect(await screen.findByText("Course not found.")).toBeInTheDocument();
  });
});
