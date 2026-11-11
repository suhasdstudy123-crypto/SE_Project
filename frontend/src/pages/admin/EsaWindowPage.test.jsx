import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../../api/client.js";
import * as coursesApi from "../../api/courses.js";
import * as esaApi from "../../api/esa.js";
import App from "../../App.jsx";
import AuthProvider from "../../auth/AuthProvider.jsx";
import EsaWindowPage from "./EsaWindowPage.jsx";
import { apiError, renderPage } from "./testUtils.jsx";

vi.mock("../../api/esa.js");
vi.mock("../../api/courses.js");

const COURSES = [
  { id: 10, code: "UE24AM241A", name: "Software Engineering" },
  { id: 11, code: "UE24AM242A", name: "Machine Learning" },
];

function student(overrides) {
  return {
    student_id: 1,
    srn: "PES1UG24AM001",
    name: "Asha Rao",
    semester: 4,
    fees_paid: true,
    held: 20,
    attended: 18,
    percentage: 90,
    eligible: true,
    reasons: [],
    override: null,
    registered: true,
    ...overrides,
  };
}

const ROWS = [
  student(),
  student({
    student_id: 2,
    srn: "PES1UG24AM002",
    name: "Rahul Nair",
    attended: 14,
    percentage: 70,
    eligible: false,
    reasons: ["Attendance 70% < 75%"],
    registered: false,
  }),
  student({
    student_id: 3,
    srn: "PES1UG24AM003",
    name: "Meera Iyer",
    fees_paid: false,
    eligible: true,
    reasons: ["Fees unpaid"],
    override: { reason: "Fee waiver approved", created_at: "2026-11-01T10:00:00" },
    registered: false,
  }),
];

const OPEN = { is_open: true, opened_at: "2026-11-01T09:00:00", closed_at: null };
const CLOSED = {
  is_open: false,
  opened_at: "2026-11-01T09:00:00",
  closed_at: "2026-11-02T09:00:00",
};

beforeEach(() => {
  esaApi.getEsaWindow.mockResolvedValue(OPEN);
  coursesApi.listCourses.mockResolvedValue(COURSES);
  esaApi.getCourseEligibility.mockResolvedValue({ course: COURSES[0], students: ROWS });
});

afterEach(() => vi.resetAllMocks());

const row = (name) => screen.getByText(name).closest("tr");

async function renderEsaPage() {
  renderPage(<EsaWindowPage />);
  await screen.findByText("Asha Rao");
}

describe("Admin ESA Window page (cards #17, #19, #20)", () => {
  it("shows the window state and each student's eligibility", async () => {
    await renderEsaPage();

    expect(screen.getByText("Open", { selector: ".srs-status" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close registration" })).toBeInTheDocument();
    expect(esaApi.getCourseEligibility).toHaveBeenCalledWith("10");

    expect(within(row("Asha Rao")).getByText("Eligible")).toBeInTheDocument();
    expect(within(row("Asha Rao")).getByText("Registered")).toBeInTheDocument();
    expect(within(row("Rahul Nair")).getByText("Not eligible")).toBeInTheDocument();
    expect(within(row("Rahul Nair")).getByText("Attendance 70% < 75%")).toBeInTheDocument();
    expect(within(row("Rahul Nair")).getByText("70%")).toHaveClass("text-danger");
    expect(within(row("Meera Iyer")).getByText("Override")).toHaveClass("srs-status-override");
    expect(within(row("Meera Iyer")).getByText("Fee waiver approved")).toBeInTheDocument();

    // Override button only for students who are not eligible.
    expect(screen.getByRole("button", { name: "Override PES1UG24AM002" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Override PES1UG24AM001" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Override PES1UG24AM003" })).toBeNull();
  });

  it("TC-ESA-01: Admin closes and reopens the window", async () => {
    esaApi.setEsaWindow.mockResolvedValueOnce(CLOSED).mockResolvedValueOnce(OPEN);
    await renderEsaPage();

    fireEvent.click(screen.getByRole("button", { name: "Close registration" }));
    expect(await screen.findByText("ESA registration is now closed")).toBeInTheDocument();
    expect(esaApi.setEsaWindow).toHaveBeenCalledWith(false);
    expect(screen.getByText("Closed", { selector: ".srs-status" })).toBeInTheDocument();
    expect(screen.getByText(/^Closed \d/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open registration" }));
    expect(await screen.findByText("ESA registration is now open")).toBeInTheDocument();
    expect(esaApi.setEsaWindow).toHaveBeenLastCalledWith(true);
  });

  it("shows an error toast if the window cannot be switched", async () => {
    esaApi.setEsaWindow.mockRejectedValue(apiError(403, "Forbidden"));
    await renderEsaPage();
    fireEvent.click(screen.getByRole("button", { name: "Close registration" }));
    expect(await screen.findByText("Forbidden")).toBeInTheDocument();
  });

  it("loads another course's students when it is picked", async () => {
    await renderEsaPage();
    fireEvent.change(screen.getByLabelText("Course"), { target: { value: "11" } });
    await waitFor(() => expect(esaApi.getCourseEligibility).toHaveBeenLastCalledWith("11"));
  });

  it("TC-ESA-07: override needs a reason, then makes the student eligible", async () => {
    esaApi.createOverride.mockResolvedValue({ id: 5 });
    await renderEsaPage();

    fireEvent.click(screen.getByRole("button", { name: "Override PES1UG24AM002" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Blocked by: Attendance 70% < 75%/)).toBeInTheDocument();
    const save = within(dialog).getByRole("button", { name: "Save override" });
    expect(save).toBeDisabled();

    esaApi.getCourseEligibility.mockResolvedValue({
      course: COURSES[0],
      students: ROWS.map((r) =>
        r.student_id === 2
          ? { ...r, eligible: true, override: { reason: "Medical certificate" } }
          : r,
      ),
    });
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), {
      target: { value: "Medical certificate" },
    });
    fireEvent.click(save);

    expect(await screen.findByText("Rahul Nair is now eligible (override recorded)")).toBeVisible();
    expect(esaApi.createOverride).toHaveBeenCalledWith(2, 10, "Medical certificate");
    await waitFor(() =>
      expect(within(row("Rahul Nair")).getByText("Medical certificate")).toBeInTheDocument(),
    );
  });

  it("keeps the dialog open with the API error if the override fails", async () => {
    esaApi.createOverride.mockRejectedValue(apiError(400, "A reason is required."));
    await renderEsaPage();

    fireEvent.click(screen.getByRole("button", { name: "Override PES1UG24AM002" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), {
      target: { value: "x" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save override" }));
    expect(await within(dialog).findByText("A reason is required.")).toBeInTheDocument();
  });

  it("shows empty states for no courses and no enrolled students", async () => {
    coursesApi.listCourses.mockResolvedValue([]);
    renderPage(<EsaWindowPage />);
    expect(await screen.findByText("No courses yet")).toBeInTheDocument();
  });

  it("shows an empty state when nobody is enrolled", async () => {
    esaApi.getCourseEligibility.mockResolvedValue({ course: COURSES[0], students: [] });
    renderPage(<EsaWindowPage />);
    expect(await screen.findByText("Nobody is enrolled")).toBeInTheDocument();
  });

  it("shows an error when loading fails", async () => {
    esaApi.getEsaWindow.mockRejectedValue(new Error("Network Error"));
    renderPage(<EsaWindowPage />);
    expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument();
  });

  it("is the page behind /admin/esa", async () => {
    vi.spyOn(client, "getMe").mockResolvedValue({ id: 1, name: "Admin", role: "admin" });
    renderPage(
      <MemoryRouter initialEntries={["/admin/esa"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "ESA Window" })).toBeInTheDocument();
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
  });
});
