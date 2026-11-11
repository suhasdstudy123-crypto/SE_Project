import { useEffect, useState } from "react";
import { Alert, Button, Card, Container, Form, Spinner } from "react-bootstrap";
import { listCourses, listMyCourses } from "../api/courses.js";
import { apiErrorMessage } from "../api/errors.js";
import { downloadReport } from "../api/reports.js";

// CSV reports for Admin and Faculty (SRS-F-023, issue #23).
// Admin sees every course; Faculty sees only the courses they teach.
export default function ResultsExportPage({ role }) {
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [exporting, setExporting] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const load = role === "admin" ? listCourses() : listMyCourses("faculty");
    load
      .then((list) => {
        setCourses(list);
        if (list.length > 0) {
          setCourseId(String(list[0].id));
        }
      })
      .catch((err) => setError(apiErrorMessage(err, "Could not load courses.")));
  }, [role]);

  async function exportReport(kind, endpoint, filename) {
    setExporting(kind);
    setError("");
    setMessage("");
    try {
      await downloadReport(endpoint, filename);
      setMessage("Report downloaded.");
    } catch (err) {
      setError(apiErrorMessage(err, "Could not export the report."));
    } finally {
      setExporting("");
    }
  }

  function exportAttendance() {
    const course = courses.find((c) => String(c.id) === courseId);
    exportReport(
      "attendance",
      `/${role}/reports/attendance.csv?course_id=${encodeURIComponent(courseId)}`,
      `attendance_${course ? course.code : courseId}.csv`,
    );
  }

  function exportResults() {
    exportReport("results", `/${role}/reports/results.csv`, "results.csv");
  }

  function buttonLabel(kind) {
    if (exporting !== kind) {
      return "Export CSV";
    }
    return (
      <>
        <Spinner size="sm" className="me-2" />
        Exporting…
      </>
    );
  }

  return (
    <Container fluid className="py-3">
      <h2>CSV Reports</h2>
      <p className="text-muted">Download reports as CSV files that open in Excel.</p>

      {error && <Alert variant="danger">{error}</Alert>}
      {message && <Alert variant="success">{message}</Alert>}

      <Card className="mt-3">
        <Card.Body>
          <h5>Attendance report</h5>
          <p className="text-muted">
            One row per enrolled student: classes attended, classes held, attendance % and shortage
            status.
          </p>
          <Form.Group className="mb-3" controlId="report-course" style={{ maxWidth: 400 }}>
            <Form.Label>Course</Form.Label>
            <Form.Select value={courseId} onChange={(event) => setCourseId(event.target.value)}>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.code} - {course.name}
                </option>
              ))}
            </Form.Select>
          </Form.Group>
          <Button
            onClick={exportAttendance}
            disabled={!courseId || exporting !== ""}
            aria-label="Export attendance CSV"
          >
            {buttonLabel("attendance")}
          </Button>
        </Card.Body>
      </Card>

      <Card className="mt-3">
        <Card.Body>
          <h5>Results report</h5>
          <p className="text-muted">
            {role === "admin"
              ? "Marks, total and grade for all students and courses."
              : "Marks, total and grade for the courses you teach."}
          </p>
          <Button
            onClick={exportResults}
            disabled={exporting !== ""}
            aria-label="Export results CSV"
          >
            {buttonLabel("results")}
          </Button>
        </Card.Body>
      </Card>
    </Container>
  );
}
