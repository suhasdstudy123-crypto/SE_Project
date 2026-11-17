import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getCourseAnalysis } from "../api/analysis.js";
import { listCourses, listMyCourses } from "../api/courses.js";
import CourseAnalysisPage from "./CourseAnalysisPage.jsx";

vi.mock("../api/analysis.js");
vi.mock("../api/courses.js");

const COURSES = [
  { id: 7, code: "UE24AM241A", name: "Software Engineering" },
  { id: 8, code: "UE24AM242A", name: "Machine Learning" },
];

// TC-RPT-01 numbers: totals 30, 40, 60, 80, 90
// grade_distribution keys in the order Flask sends them (sorted alphabetically)
const ANALYSIS = {
  course: { id: 7, code: "UE24AM241A", name: "Software Engineering", credits: 4 },
  students_appeared: 5,
  average: 60,
  highest: 90,
  lowest: 30,
  pass_percentage: 80,
  grade_distribution: { A: 1, B: 0, C: 1, D: 0, E: 1, F: 1, S: 1 },
};

const EMPTY = {
  ...ANALYSIS,
  students_appeared: 0,
  average: null,
  highest: null,
  lowest: null,
  pass_percentage: null,
  grade_distribution: { S: 0, A: 0, B: 0, C: 0, D: 0, E: 0, F: 0 },
};

afterEach(() => vi.resetAllMocks());

describe("CourseAnalysisPage (issue #25, SRS-F-022)", () => {
  it("TC-RPT-01: Faculty sees average, highest, lowest, pass % and grade counts", async () => {
    listMyCourses.mockResolvedValue(COURSES.slice(0, 1));
    getCourseAnalysis.mockResolvedValue(ANALYSIS);
    render(<CourseAnalysisPage role="faculty" />);

    expect(await screen.findByTestId("Average")).toHaveTextContent("60");
    expect(screen.getByTestId("Highest")).toHaveTextContent("90");
    expect(screen.getByTestId("Lowest")).toHaveTextContent("30");
    expect(screen.getByTestId("Pass %")).toHaveTextContent("80%");
    expect(screen.getByTestId("grade-S")).toHaveTextContent("1");
    expect(screen.getByTestId("grade-B")).toHaveTextContent("0");
    expect(listMyCourses).toHaveBeenCalledWith("faculty");
    expect(getCourseAnalysis).toHaveBeenCalledWith("faculty", "7");
  });

  it("lists grades from best to worst (S first, F last) whatever order the API sends", async () => {
    listMyCourses.mockResolvedValue(COURSES.slice(0, 1));
    getCourseAnalysis.mockResolvedValue(ANALYSIS);
    render(<CourseAnalysisPage role="faculty" />);

    await screen.findByTestId("grade-S");
    const grades = screen.getAllByTestId(/^grade-/).map((cell) => cell.dataset.testid);
    expect(grades).toEqual([
      "grade-S",
      "grade-A",
      "grade-B",
      "grade-C",
      "grade-D",
      "grade-E",
      "grade-F",
    ]);
  });

  it("Admin can switch to another course", async () => {
    listCourses.mockResolvedValue(COURSES);
    getCourseAnalysis.mockResolvedValue(ANALYSIS);
    render(<CourseAnalysisPage role="admin" />);

    const select = await screen.findByLabelText("Course");
    await screen.findByTestId("Average");
    fireEvent.change(select, { target: { value: "8" } });

    await waitFor(() => expect(getCourseAnalysis).toHaveBeenLastCalledWith("admin", "8"));
  });

  it("Student sees a 'no results yet' message when nobody has taken the exam", async () => {
    listMyCourses.mockResolvedValue(COURSES.slice(0, 1));
    getCourseAnalysis.mockResolvedValue(EMPTY);
    render(<CourseAnalysisPage role="student" />);

    expect(await screen.findByText("No results yet")).toBeInTheDocument();
    expect(screen.getByTestId("Average")).toHaveTextContent("—");
    expect(listMyCourses).toHaveBeenCalledWith("student");
  });

  it("shows an empty state when there are no courses", async () => {
    listMyCourses.mockResolvedValue([]);
    render(<CourseAnalysisPage role="faculty" />);

    expect(await screen.findByText("No courses yet")).toBeInTheDocument();
    expect(getCourseAnalysis).not.toHaveBeenCalled();
  });

  it("shows the server's error when the analysis cannot load", async () => {
    listMyCourses.mockResolvedValue(COURSES.slice(0, 1));
    getCourseAnalysis.mockRejectedValue({
      response: { data: { error: "You are not assigned to this course." } },
    });
    render(<CourseAnalysisPage role="faculty" />);

    expect(await screen.findByText("You are not assigned to this course.")).toBeInTheDocument();
  });

  it("shows an error when courses cannot load", async () => {
    listCourses.mockRejectedValue({ response: { status: 500, data: {} } });
    render(<CourseAnalysisPage role="admin" />);

    expect(await screen.findByText("Could not load courses.")).toBeInTheDocument();
  });
});
