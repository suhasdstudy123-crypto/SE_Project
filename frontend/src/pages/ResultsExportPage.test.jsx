import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadReport } from "../api/reports.js";
import ResultsExportPage from "./ResultsExportPage.jsx";

vi.mock("../api/reports.js");

afterEach(() => vi.resetAllMocks());

describe("ResultsExportPage (Issue #23)", () => {
  it("TC-RPT-02: Admin can export results as CSV", async () => {
    downloadReport.mockResolvedValue(undefined);

    render(<ResultsExportPage role="admin" />);

    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() => {
      expect(downloadReport).toHaveBeenCalledWith("/admin/reports/results.csv", "results.csv");
    });
  });

  it("TC-RPT-02: Faculty can export results as CSV", async () => {
    downloadReport.mockResolvedValue(undefined);

    render(<ResultsExportPage role="faculty" />);

    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() => {
      expect(downloadReport).toHaveBeenCalledWith("/faculty/reports/results.csv", "results.csv");
    });
  });
});
