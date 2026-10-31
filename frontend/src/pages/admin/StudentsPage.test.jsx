import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as adminApi from "../../api/admin.js";
import StudentsPage from "./StudentsPage.jsx";
import { apiError, DEPARTMENTS, renderPage, STUDENTS } from "./testUtils.jsx";

beforeEach(() => {
  vi.spyOn(adminApi, "listDepartments").mockResolvedValue(DEPARTMENTS);
});
afterEach(() => vi.restoreAllMocks());

function fillForm(values) {
  const dialog = within(screen.getByRole("dialog"));
  Object.entries(values).forEach(([label, value]) => {
    fireEvent.change(dialog.getByLabelText(label), { target: { value } });
  });
  return dialog;
}

describe("Students page (F-005, F-006, TC-STU-02/03/04)", () => {
it("lists students and filters them by search", async () => {
  vi.spyOn(adminApi, "listStudents").mockImplementation(async (filters = {}) => {
    const term = (filters.search || "").toLowerCase();

    return STUDENTS.filter(
      (student) =>
        !term ||
        student.name.toLowerCase().includes(term) ||
        student.srn.toLowerCase().includes(term) ||
        student.email.toLowerCase().includes(term),
    );
  });

  renderPage(<StudentsPage />);

  expect(await screen.findByText("PES1UG24AM001")).toBeInTheDocument();
  expect(screen.getByText("Showing 2 of 2")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Search students"), {
    target: { value: "rahul" },
  });

  await waitFor(() => {
    expect(screen.queryByText("Asha Rao")).not.toBeInTheDocument();
    expect(screen.getByText("Rahul Nair")).toBeInTheDocument();
  });

  fireEvent.change(screen.getByLabelText("Search students"), {
    target: { value: "zzz" },
  });

  await waitFor(() => {
    expect(screen.getByText("No matching students")).toBeInTheDocument();
  });
});

  it("shows an empty state when there are no students", async () => {
    vi.spyOn(adminApi, "listStudents").mockResolvedValue([]);
    renderPage(<StudentsPage />);
    expect(await screen.findByText("No students yet")).toBeInTheDocument();
  });

  it("adds a student with department and section", async () => {
    vi.spyOn(adminApi, "listStudents").mockResolvedValue([]);
    const create = vi.spyOn(adminApi, "createStudent").mockResolvedValue({ id: 3 });
    renderPage(<StudentsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Add student" }));
    const dialog = fillForm({
      SRN: "PES1UG24AM003",
      "Full name": "Meera Iyer",
      Email: "meera@pes.edu",
      Semester: "3",
      Department: "1",
    });
    fireEvent.change(dialog.getByLabelText("Section"), { target: { value: "11" } });
    fireEvent.click(dialog.getByRole("button", { name: "Add student" }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith({
        srn: "PES1UG24AM003",
        name: "Meera Iyer",
        email: "meera@pes.edu",
        semester: 3,
        department_id: 1,
        section_id: 11,
      }),
    );
    expect(await screen.findByText("Meera Iyer added")).toBeInTheDocument();
  });

  it("shows the server's error for a duplicate SRN (TC-STU-03)", async () => {
    vi.spyOn(adminApi, "listStudents").mockResolvedValue(STUDENTS);
    vi.spyOn(adminApi, "createStudent").mockRejectedValue(apiError(400, "SRN already exists."));
    renderPage(<StudentsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Add student" }));
    const dialog = fillForm({
      SRN: "PES1UG24AM001",
      "Full name": "Copy",
      Email: "copy@pes.edu",
      Department: "1",
    });
    fireEvent.change(dialog.getByLabelText("Section"), { target: { value: "10" } });
    fireEvent.click(dialog.getByRole("button", { name: "Add student" }));

    expect(await screen.findByText("SRN already exists.")).toBeInTheDocument();
  });

  it("edits a student", async () => {
    vi.spyOn(adminApi, "listStudents").mockResolvedValue(STUDENTS);
    const update = vi.spyOn(adminApi, "updateStudent").mockResolvedValue(STUDENTS[0]);
    renderPage(<StudentsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Edit Asha Rao" }));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByLabelText("SRN")).toHaveValue("PES1UG24AM001");
    fireEvent.change(dialog.getByLabelText("Full name"), { target: { value: "Asha R" } });
    fireEvent.click(dialog.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(1, expect.objectContaining({ name: "Asha R" })),
    );
    expect(await screen.findByText("Asha R updated")).toBeInTheDocument();
  });

  it("deletes a student after confirmation", async () => {
    vi.spyOn(adminApi, "listStudents").mockResolvedValue(STUDENTS);
    const remove = vi.spyOn(adminApi, "deleteStudent").mockResolvedValue();
    renderPage(<StudentsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Delete Rahul Nair" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete student" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith(2));
    expect(await screen.findByText("Rahul Nair deleted")).toBeInTheDocument();
  });

  it("asks for a department first when none exist", async () => {
    adminApi.listDepartments.mockResolvedValue([]);
    vi.spyOn(adminApi, "listStudents").mockResolvedValue([]);
    renderPage(<StudentsPage />);

    expect(await screen.findByText(/Create a department and a section first/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add student" })).toBeDisabled();
  });
});
