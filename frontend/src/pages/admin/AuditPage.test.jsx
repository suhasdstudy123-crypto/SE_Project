import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as adminApi from "../../api/admin.js";
import AuditPage from "./AuditPage.jsx";
import { apiError, renderPage } from "./testUtils.jsx";

const SAMPLE_LOGS = [
  {
    id: 1,
    user_id: 2,
    user_email: "faculty@pes.edu",
    action: "marks changed",
    entity: "marks",
    entity_id: "101:1",
    old_value: "15",
    new_value: "18",
    timestamp: "2026-10-15T10:30:00Z",
  },
  {
    id: 2,
    user_id: 1,
    user_email: "admin@pes.edu",
    action: "fee status changed",
    entity: "fee_status",
    entity_id: "1:3",
    old_value: "UNPAID",
    new_value: "PAID",
    timestamp: "2026-10-15T11:00:00Z",
  },
  {
    id: 3,
    user_id: 2,
    user_email: "faculty@pes.edu",
    action: "attendance changed",
    entity: "attendance",
    entity_id: "42",
    old_value: "absent",
    new_value: "present",
    timestamp: "2026-10-15T11:30:00Z",
  },
];

afterEach(() => vi.restoreAllMocks());

describe("AuditPage (Card #6, SRS-F-025)", () => {
  it("renders audit log records with user, action, and changes (SRS-F-025)", async () => {
    vi.spyOn(adminApi, "listAuditLogs").mockResolvedValue(SAMPLE_LOGS);
    renderPage(<AuditPage />);

    expect(await screen.findByText("marks changed")).toBeInTheDocument();
    expect(screen.getByText("fee status changed")).toBeInTheDocument();
    expect(screen.getByText("attendance changed")).toBeInTheDocument();

    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
  });

  it("filters logs by search query", async () => {
    vi.spyOn(adminApi, "listAuditLogs").mockResolvedValue(SAMPLE_LOGS);
    renderPage(<AuditPage />);

    expect(await screen.findByText("marks changed")).toBeInTheDocument();
    const searchInput = screen.getByPlaceholderText(/Search by action/);
    fireEvent.change(searchInput, { target: { value: "fee" } });

    expect(screen.getByText("fee status changed")).toBeInTheDocument();
    expect(screen.queryByText("marks changed")).not.toBeInTheDocument();
  });

  it("filters logs by entity dropdown", async () => {
    vi.spyOn(adminApi, "listAuditLogs").mockResolvedValue(SAMPLE_LOGS);
    renderPage(<AuditPage />);

    expect(await screen.findByText("marks changed")).toBeInTheDocument();
    const entitySelect = screen.getByLabelText("Filter by entity");
    fireEvent.change(entitySelect, { target: { value: "attendance" } });

    expect(screen.getByText("attendance changed")).toBeInTheDocument();
    expect(screen.queryByText("marks changed")).not.toBeInTheDocument();
    expect(screen.queryByText("fee status changed")).not.toBeInTheDocument();
  });

  it("shows an empty state when no logs match", async () => {
    vi.spyOn(adminApi, "listAuditLogs").mockResolvedValue([]);
    renderPage(<AuditPage />);

    expect(await screen.findByText("No audit log entries found")).toBeInTheDocument();
  });

  it("displays server error message when loading fails", async () => {
    vi.spyOn(adminApi, "listAuditLogs").mockRejectedValue(apiError(500, "Database unavailable"));
    renderPage(<AuditPage />);

    expect(await screen.findByText("Database unavailable")).toBeInTheDocument();
  });
});
