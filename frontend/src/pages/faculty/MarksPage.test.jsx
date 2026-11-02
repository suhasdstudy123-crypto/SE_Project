import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as coursesApi from "../../api/courses.js";
import * as marksApi from "../../api/marks.js";
import MarksPage from "./MarksPage.jsx";

vi.mock("../../api/courses.js");
vi.mock("../../api/marks.js");

const mockCourses = [
  { id: 101, code: "UE24AM241A", name: "Software Engineering" },
  { id: 102, code: "UE24AM242A", name: "Machine Learning" },
];

const mockRoster = [
  {
    student_id: 1,
    srn: "PES1UG24AM001",
    name: "Student One",
    is_esa_registered: true,
    isa1: 18.0,
    isa2: 17.0,
    assessment: 9.0,
    esa: 45.0,
    total: 89.0,
  },
  {
    student_id: 2,
    srn: "PES1UG24AM002",
    name: "Student Two",
    is_esa_registered: false,
    isa1: 15.0,
    isa2: 14.0,
    assessment: 8.0,
    esa: null,
    total: 37.0,
  },
];

beforeEach(() => {
  coursesApi.listMyCourses.mockResolvedValue(mockCourses);
  marksApi.getCourseMarks.mockResolvedValue({
    course: mockCourses[0],
    students: mockRoster,
  });
});

afterEach(() => vi.resetAllMocks());

describe("Faculty Enter Marks Page (Issue #15: SRS-F-019)", () => {
  it("renders course dropdown and student marks table", async () => {
    render(<MarksPage />);

    expect(await screen.findByText("Enter Marks")).toBeInTheDocument();
    expect(screen.getByText("UE24AM241A – Software Engineering")).toBeInTheDocument();

    expect(await screen.findByText("PES1UG24AM001")).toBeInTheDocument();
    expect(screen.getByText("Student One")).toBeInTheDocument();
    expect(screen.getByDisplayValue("18")).toBeInTheDocument();
    expect(screen.getByDisplayValue("17")).toBeInTheDocument();
    expect(screen.getByDisplayValue("9")).toBeInTheDocument();
    expect(screen.getByDisplayValue("45")).toBeInTheDocument();
    expect(screen.getByText("89")).toBeInTheDocument();

    // Student 2 is NOT registered for ESA
    expect(screen.getByText("PES1UG24AM002")).toBeInTheDocument();
    expect(screen.getByText("Not Registered")).toBeInTheDocument();
  });

  it("shows inline validation error and disables Save button on exceeding max limit", async () => {
    render(<MarksPage />);
    await screen.findByText("PES1UG24AM001");

    const isa1Input = screen.getByLabelText("PES1UG24AM001 ISA-1");
    fireEvent.change(isa1Input, { target: { value: "25" } });

    expect(await screen.findByText("Max 20")).toBeInTheDocument();
    const saveBtn = screen.getByRole("button", { name: "Save marks for PES1UG24AM001" });
    expect(saveBtn).toBeDisabled();
  });

  it("saves marks and displays success confirmation", async () => {
    marksApi.saveStudentMarks.mockResolvedValue({
      marks: {
        student_id: 1,
        course_id: 101,
        isa1: 19.0,
        isa2: 17.0,
        assessment: 9.0,
        esa: 45.0,
        total: 90.0,
      },
    });

    render(<MarksPage />);
    await screen.findByText("PES1UG24AM001");

    const isa1Input = screen.getByLabelText("PES1UG24AM001 ISA-1");
    fireEvent.change(isa1Input, { target: { value: "19" } });

    const saveBtn = screen.getByRole("button", { name: "Save marks for PES1UG24AM001" });
    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    expect(marksApi.saveStudentMarks).toHaveBeenCalledWith(
      "101",
      1,
      expect.objectContaining({ isa1: 19, isa2: 17, assessment: 9, esa: 45 }),
    );
    expect(await screen.findByText("Marks saved for PES1UG24AM001.")).toBeInTheDocument();
  });

  it("shows server error when saving fails", async () => {
    marksApi.saveStudentMarks.mockRejectedValue({
      response: {
        status: 400,
        data: { error: "Cannot enter ESA marks for unregistered student." },
      },
    });

    render(<MarksPage />);
    await screen.findByText("PES1UG24AM001");

    const saveBtn = screen.getByRole("button", { name: "Save marks for PES1UG24AM001" });
    fireEvent.click(saveBtn);

    expect(
      await screen.findByText("Cannot enter ESA marks for unregistered student."),
    ).toBeInTheDocument();
  });

  it("switches course when dropdown selection changes", async () => {
    render(<MarksPage />);
    await screen.findByText("PES1UG24AM001");

    marksApi.getCourseMarks.mockResolvedValueOnce({
      course: mockCourses[1],
      students: [],
    });

    const select = screen.getByLabelText("Select course");
    fireEvent.change(select, { target: { value: "102" } });

    await waitFor(() => {
      expect(marksApi.getCourseMarks).toHaveBeenCalledWith("102");
    });
    expect(await screen.findByText("No students are enrolled in this course.")).toBeInTheDocument();
  });

  it("handles empty courses list", async () => {
    coursesApi.listMyCourses.mockResolvedValue([]);
    render(<MarksPage />);

    expect(await screen.findByText("You are not assigned to any courses yet.")).toBeInTheDocument();
  });
});
