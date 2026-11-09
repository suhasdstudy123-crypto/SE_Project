
import { useState } from "react";
import { Alert, Button, Card, Container, Spinner } from "react-bootstrap";
import { downloadReport } from "../api/reports.js";
import { apiErrorMessage } from "../api/errors.js";

export default function ResultsExportPage({ role }) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function handleExport() {
    setExporting(true);
    setError("");
    setMessage("");

    try {
      const endpoint =
        role === "admin"
          ? "/admin/reports/results.csv"
          : "/faculty/reports/results.csv";

      await downloadReport(endpoint, "results.csv");
      setMessage("Results report downloaded successfully.");
    } catch (err) {
      setError(apiErrorMessage(err, "Could not export results."));
    } finally {
      setExporting(false);
    }
  }

  return (
    <Container fluid className="py-3">
      <h2>Results Report</h2>
      <p className="text-muted">
        Export student assessment results as a CSV file that can be opened in Excel.
      </p>

      {error && <Alert variant="danger">{error}</Alert>}
      {message && <Alert variant="success">{message}</Alert>}

      <Card className="mt-3">
        <Card.Body>
          <h5>Export Results</h5>
          <p className="text-muted">
            {role === "admin"
              ? "Download results for all students and courses."
              : "Download results for courses assigned to you."}
          </p>

          <Button onClick={handleExport} disabled={exporting}>
            {exporting ? (
              <>
                <Spinner size="sm" className="me-2" />
                Exporting…
              </>
            ) : (
              "Export CSV"
            )}
          </Button>
        </Card.Body>
      </Card>
    </Container>
  );
}
