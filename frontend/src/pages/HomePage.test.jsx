import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import api from "../api/client.js";
import { AuthContext } from "../auth/authContext.js";
import HomePage from "./HomePage.jsx";

const users = {
  admin: { id: 1, name: "Admin User", role: "admin" },
  faculty: { id: 2, name: "Faculty User", role: "faculty" },
  student: { id: 3, name: "Student User", role: "student" },
};

function renderAs(role) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={{ user: users[role] }}>
        <HomePage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("Dashboard summary (TC-RPT-03)", () => {
  it("shows Admin dashboard summary cards", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: {
        total_students: 120,
        total_courses: 15,
        fee_defaulters: 12,
        attendance_shortages: 8,
      },
    });

    renderAs("admin");

    expect(await screen.findByTestId("total_students")).toHaveTextContent("120");
    expect(screen.getByTestId("total_courses")).toHaveTextContent("15");
    expect(screen.getByTestId("fee_defaulters")).toHaveTextContent("12");
    expect(screen.getByTestId("attendance_shortages")).toHaveTextContent("8");

    expect(api.get).toHaveBeenCalledWith("/admin/dashboard");
  });

  it("shows Faculty dashboard summary cards", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: {
        total_students: 30,
        total_courses: 3,
        attendance_shortages: 5,
      },
    });

    renderAs("faculty");

    expect(await screen.findByTestId("total_students")).toHaveTextContent("30");
    expect(screen.getByTestId("total_courses")).toHaveTextContent("3");
    expect(screen.getByTestId("attendance_shortages")).toHaveTextContent("5");

    expect(api.get).toHaveBeenCalledWith("/faculty/dashboard");
    expect(screen.queryByTestId("fee_defaulters")).not.toBeInTheDocument();
  });

  it("does not fetch dashboard data for Students", () => {
    const getSpy = vi.spyOn(api, "get");

    renderAs("student");

    expect(screen.getByText("Welcome back, Student User.")).toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Dashboard summary")).not.toBeInTheDocument();
  });

  it("shows loading state while fetching dashboard data", () => {
    vi.spyOn(api, "get").mockReturnValue(new Promise(() => {}));

    renderAs("admin");

    expect(screen.getByRole("status")).toHaveTextContent("Loading dashboard summary...");
  });

  it("shows an error if dashboard data cannot be loaded", async () => {
    vi.spyOn(api, "get").mockRejectedValue({
      response: {
        data: { error: "Dashboard unavailable." },
      },
    });

    renderAs("admin");

    expect(await screen.findByText("Dashboard unavailable.")).toBeInTheDocument();
  });
});
