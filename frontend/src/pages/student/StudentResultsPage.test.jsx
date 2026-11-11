import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import * as marksApi from "../../api/marks.js";
import StudentResultsPage from "./StudentResultsPage.jsx";

// Unit/Component tests for StudentResultsPage (SRS-F-020, Issue #16, TC-MRK-04, TC-MRK-05).

describe("StudentResultsPage", () => {
  it("renders student results table with component marks, grades, and calculated SGPA", async () => {
    vi.spyOn(marksApi, "getStudentResults").mockResolvedValue({
      student: { id: 1, srn: "PES1UG24AM001", name: "Alice" },
      courses: [
        {
          course_id: 10,
          code: "UE24AM301",
          name: "Machine Learning",
          credits: 4,
          isa1: 18,
          isa2: 18,
          assessment: 9,
          esa: 45,
          total: 90,
          grade: "S",
          grade_point: 10,
        },
        {
          course_id: 11,
          code: "UE24AM302",
          name: "Deep Learning",
          credits: 4,
          isa1: 16,
          isa2: 15,
          assessment: 8,
          esa: 38,
          total: 77,
          grade: "B",
          grade_point: 8,
        },
      ],
      sgpa: 9.0,
      total_credits: 8,
      earned_credits: 8,
    });

    render(<StudentResultsPage />);

    expect(await screen.findByRole("heading", { name: "My Results" })).toBeInTheDocument();
    expect(screen.getByTestId("sgpa-value")).toHaveTextContent("9.00");
    expect(screen.getByText("UE24AM301")).toBeInTheDocument();
    expect(screen.getByText("Machine Learning")).toBeInTheDocument();
    expect(screen.getByText("UE24AM302")).toBeInTheDocument();
    expect(screen.getByText("Deep Learning")).toBeInTheDocument();

    // Grades rendered as badges
    expect(screen.getByText("S")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
    // Credits
    expect(screen.getByText("Total Credits")).toBeInTheDocument();
    expect(screen.getByText("Credits Earned")).toBeInTheDocument();
  });

  it("renders empty state message when student has no enrolled courses", async () => {
    vi.spyOn(marksApi, "getStudentResults").mockResolvedValue({
      student: { id: 2, srn: "PES1UG24AM002", name: "Bob" },
      courses: [],
      sgpa: null,
      total_credits: 0,
      earned_credits: 0,
    });

    render(<StudentResultsPage />);

    expect(await screen.findByText("You are not enrolled in any courses yet.")).toBeInTheDocument();
  });

  it("shows error alert when fetching results fails", async () => {
    vi.spyOn(marksApi, "getStudentResults").mockRejectedValue({
      response: { data: { error: "Failed to load student results." } },
    });

    render(<StudentResultsPage />);

    expect(await screen.findByText("Failed to load student results.")).toBeInTheDocument();
  });
});
