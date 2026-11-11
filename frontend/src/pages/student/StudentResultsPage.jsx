import { useEffect, useState } from "react";
import { Alert, Badge, Card, Col, Container, Row, Spinner, Table } from "react-bootstrap";
import { apiErrorMessage } from "../../api/errors.js";
import * as marksApi from "../../api/marks.js";

// Student My Results page (SRS-F-020, Issue #16).
// Displays marks breakdown, letter grade, grade points, and semester SGPA.

function gradeBadgeVariant(grade) {
  switch (grade) {
    case "S":
    case "A":
      return "success";
    case "B":
    case "C":
      return "primary";
    case "D":
    case "E":
      return "warning";
    case "F":
      return "danger";
    default:
      return "secondary";
  }
}

export default function StudentResultsPage() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    marksApi
      .getStudentResults()
      .then((data) => setResults(data))
      .catch((err) => setError(apiErrorMessage(err, "Failed to load results.")))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Container className="py-4">
        <Spinner animation="border" role="status" aria-label="Loading results" />
      </Container>
    );
  }

  const courses = results?.courses || [];
  const sgpa = results?.sgpa;
  const totalCredits = results?.total_credits || 0;
  const earnedCredits = results?.earned_credits || 0;

  return (
    <Container className="pb-5">
      <h1 className="h3 mb-3">My Results</h1>
      {error && <Alert variant="danger">{error}</Alert>}

      {courses.length === 0 ? (
        <p className="text-muted">You are not enrolled in any courses yet.</p>
      ) : (
        <>
          <Row className="g-3 mb-4">
            <Col sm={6} md={4}>
              <Card className="text-center shadow-sm">
                <Card.Body>
                  <Card.Subtitle className="mb-2 text-muted">Semester SGPA</Card.Subtitle>
                  <Card.Title
                    className="display-6 fw-bold text-primary mb-0"
                    data-testid="sgpa-value"
                  >
                    {sgpa !== null && sgpa !== undefined ? Number(sgpa).toFixed(2) : "—"}
                  </Card.Title>
                </Card.Body>
              </Card>
            </Col>
            <Col sm={6} md={4}>
              <Card className="text-center shadow-sm">
                <Card.Body>
                  <Card.Subtitle className="mb-2 text-muted">Total Credits</Card.Subtitle>
                  <Card.Title className="display-6 fw-bold text-secondary mb-0">
                    {totalCredits}
                  </Card.Title>
                </Card.Body>
              </Card>
            </Col>
            <Col sm={6} md={4}>
              <Card className="text-center shadow-sm">
                <Card.Body>
                  <Card.Subtitle className="mb-2 text-muted">Credits Earned</Card.Subtitle>
                  <Card.Title className="display-6 fw-bold text-success mb-0">
                    {earnedCredits}
                  </Card.Title>
                </Card.Body>
              </Card>
            </Col>
          </Row>

          <Table striped hover responsive className="align-middle">
            <thead>
              <tr>
                <th style={{ width: "14%" }}>Course Code</th>
                <th style={{ width: "20%" }}>Course Name</th>
                <th style={{ width: "8%" }} className="text-center">
                  Credits
                </th>
                <th style={{ width: "9%" }} className="text-center">
                  ISA-1 (20)
                </th>
                <th style={{ width: "9%" }} className="text-center">
                  ISA-2 (20)
                </th>
                <th style={{ width: "10%" }} className="text-center">
                  Assessment (10)
                </th>
                <th style={{ width: "10%" }} className="text-center">
                  ESA (50)
                </th>
                <th style={{ width: "8%" }} className="text-center">
                  Total
                </th>
                <th style={{ width: "6%" }} className="text-center">
                  Grade
                </th>
                <th style={{ width: "6%" }} className="text-center">
                  Grade Point
                </th>
              </tr>
            </thead>
            <tbody>
              {courses.map((c) => (
                <tr key={c.course_id}>
                  <td className="fw-semibold">{c.code}</td>
                  <td>{c.name}</td>
                  <td className="text-center">{c.credits}</td>
                  <td className="text-center">{c.isa1 !== null ? c.isa1 : "—"}</td>
                  <td className="text-center">{c.isa2 !== null ? c.isa2 : "—"}</td>
                  <td className="text-center">{c.assessment !== null ? c.assessment : "—"}</td>
                  <td className="text-center">{c.esa !== null ? c.esa : "—"}</td>
                  <td className="text-center fw-bold">{c.total !== null ? c.total : "—"}</td>
                  <td className="text-center">
                    {c.grade ? (
                      <Badge bg={gradeBadgeVariant(c.grade)} className="fs-6 px-2 py-1">
                        {c.grade}
                      </Badge>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="text-center fw-semibold">
                    {c.grade_point !== null && c.grade_point !== undefined ? c.grade_point : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
    </Container>
  );
}
