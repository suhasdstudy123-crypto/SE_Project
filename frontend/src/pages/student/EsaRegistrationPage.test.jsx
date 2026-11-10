import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../../api/client.js";
import * as esaApi from "../../api/esa.js";
import App from "../../App.jsx";
import AuthProvider from "../../auth/AuthProvider.jsx";
import { apiError, renderPage } from "../admin/testUtils.jsx";
import EsaRegistrationPage from "./EsaRegistrationPage.jsx";

vi.mock("../../api/esa.js");

function course(overrides) {
  return {
    course_id: 10,
    course_code: "UE24AM241A",
    course_name: "Software Engineering",
    credits: 4,
    fees_paid: true,
    held: 20,
    attended: 18,
    percentage: 90,
    eligible: true,
    reasons: [],
    override: null,
    registered: false,
    ...overrides,
  };
}

const COURSES = [
  course(),
  course({
    course_id: 11,
    course_code: "UE24AM242A",
    course_name: "Machine Learning",
    attended: 14,
    percentage: 70,
    eligible: false,
    reasons: ["Attendance 70% < 75%"],
  }),
  course({
    course_id: 12,
    course_code: "UE24AM243A",
    course_name: "DBMS",
    registered: true,
  }),
  course({
    course_id: 13,
    course_code: "UE24AM244A",
    course_name: "Statistics",
    held: 0,
    attended: 0,
    percentage: 0,
    fees_paid: false,
    eligible: true,
    reasons: ["Fees unpaid"],
    override: { reason: "Scholarship pending" },
  }),
];

const open = (courses = COURSES) => ({ window: { is_open: true }, courses });

beforeEach(() => {
  esaApi.getMyEsa.mockResolvedValue(open());
});

afterEach(() => vi.resetAllMocks());

const row = (code) => screen.getByText(code).closest("tr");

async function renderEsaPage() {
  renderPage(<EsaRegistrationPage />);
  await screen.findByText("UE24AM241A");
}

describe("Student ESA Registration page (cards #18, #19)", () => {
  it("lists enrolled courses with eligibility, reasons and the right buttons", async () => {
    await renderEsaPage();

    expect(within(row("UE24AM241A")).getByText("Eligible")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register UE24AM241A" })).toBeEnabled();

    // Card #19: exact reason shown and Register disabled.
    expect(within(row("UE24AM242A")).getByText("Attendance 70% < 75%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register UE24AM242A" })).toBeDisabled();

    expect(within(row("UE24AM243A")).getByText("Registered")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Drop UE24AM243A" })).toBeEnabled();

    expect(within(row("UE24AM244A")).getByText("Override")).toBeInTheDocument();
    expect(within(row("UE24AM244A")).getByText("No classes yet")).toBeInTheDocument();
    expect(within(row("UE24AM244A")).getByText("Unpaid")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register UE24AM244A" })).toBeEnabled();

    expect(screen.queryByText(/registration is closed/)).not.toBeInTheDocument();
  });

  it("TC-ESA-02: registers for an ESA and then drops it", async () => {
    esaApi.registerEsa.mockResolvedValue({ status: "registered" });
    esaApi.dropEsa.mockResolvedValue({ status: "dropped" });
    await renderEsaPage();

    esaApi.getMyEsa.mockResolvedValue(
      open(COURSES.map((c) => (c.course_id === 10 ? { ...c, registered: true } : c))),
    );
    fireEvent.click(screen.getByRole("button", { name: "Register UE24AM241A" }));
    expect(await screen.findByText("Registered for the UE24AM241A ESA")).toBeInTheDocument();
    expect(esaApi.registerEsa).toHaveBeenCalledWith(10);

    const dropButton = await screen.findByRole("button", { name: "Drop UE24AM241A" });
    esaApi.getMyEsa.mockResolvedValue(open());
    fireEvent.click(dropButton);
    expect(await screen.findByText("Dropped the UE24AM241A ESA")).toBeInTheDocument();
    expect(esaApi.dropEsa).toHaveBeenCalledWith(10);
    expect(await screen.findByRole("button", { name: "Register UE24AM241A" })).toBeEnabled();
  });

  it("TC-ESA-01/03: a closed window explains why and disables every button", async () => {
    esaApi.getMyEsa.mockResolvedValue({ window: { is_open: false }, courses: COURSES });
    await renderEsaPage();

    expect(screen.getByText(/ESA registration is closed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register UE24AM241A" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Drop UE24AM243A" })).toBeDisabled();
  });

  it("shows the server's reason if registration is refused", async () => {
    esaApi.registerEsa.mockRejectedValue(
      apiError(403, "Not eligible for the UE24AM241A ESA: Fees unpaid."),
    );
    await renderEsaPage();
    fireEvent.click(screen.getByRole("button", { name: "Register UE24AM241A" }));
    expect(
      await screen.findByText("Not eligible for the UE24AM241A ESA: Fees unpaid."),
    ).toBeInTheDocument();
    await waitFor(() => expect(esaApi.getMyEsa).toHaveBeenCalledTimes(2));
  });

  it("shows an empty state with no enrolled courses", async () => {
    esaApi.getMyEsa.mockResolvedValue(open([]));
    renderPage(<EsaRegistrationPage />);
    expect(await screen.findByText("You are not enrolled in any courses yet.")).toBeInTheDocument();
  });

  it("shows an error if the page cannot load", async () => {
    esaApi.getMyEsa.mockRejectedValue(apiError(404, "No student record is linked to this login."));
    renderPage(<EsaRegistrationPage />);
    expect(
      await screen.findByText("No student record is linked to this login."),
    ).toBeInTheDocument();
  });

  it("is the page behind /student/esa", async () => {
    vi.spyOn(client, "getMe").mockResolvedValue({ id: 3, name: "Student", role: "student" });
    renderPage(
      <MemoryRouter initialEntries={["/student/esa"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "ESA Registration" })).toBeInTheDocument();
  });
});
