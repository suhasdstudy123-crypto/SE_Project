import { useEffect, useState } from "react";
import { Alert, Card, Col, Form, ProgressBar, Row, Spinner, Table } from "react-bootstrap";
import { getCourseAnalysis } from "../api/analysis.js";
import { listCourses, listMyCourses } from "../api/courses.js";
import { apiErrorMessage } from "../api/errors.js";
import EmptyState from "../components/EmptyState.jsx";
import PageHeader from "../components/PageHeader.jsx";

// Result analysis per course (SRS-F-022, issue #25, TC-RPT-01).
// Admin: any course. Faculty: courses they teach. Student: courses they are enrolled in.
// Best grade first. The API sends the counts as a JSON object, whose key order is not
// guaranteed (Flask sorts keys alphabetically: A, B, ..., F, S), so the page sets the order.
const GRADE_ORDER = ["S", "A", "B", "C", "D", "E", "F"];

const DESCRIPTIONS = {
  admin: "Class results for any course.",
  faculty: "How your class did in each course you teach.",
  student: "How your class did in each of your courses. Only totals are shown, never names.",
};

function show(value, suffix = "") {
  return value === null || value === undefined ? "—" : `${value}${suffix}`;
}

export default function CourseAnalysisPage({ role }) {
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = role === "admin" ? listCourses() : listMyCourses(role);
    load
      .then((list) => {
        setCourses(list);
        if (list.length > 0) {
          setCourseId(String(list[0].id));
        }
      })
      .catch((err) => setError(apiErrorMessage(err, "Could not load courses.")))
      .finally(() => setLoadingCourses(false));
  }, [role]);

  useEffect(() => {
    if (!courseId) {
      return undefined;
    }
    let active = true;
    setLoading(true);
    setError("");
    getCourseAnalysis(role, courseId)
      .then((data) => {
        if (active) setAnalysis(data);
      })
      .catch((err) => {
        if (active) {
          setAnalysis(null);
          setError(apiErrorMessage(err, "Could not load the analysis."));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [role, courseId]);

  const appeared = analysis?.students_appeared || 0;
  const stats = analysis
    ? [
        ["Students appeared", show(analysis.students_appeared)],
        ["Average", show(analysis.average)],
        ["Highest", show(analysis.highest)],
        ["Lowest", show(analysis.lowest)],
        ["Pass %", show(analysis.pass_percentage, "%")],
      ]
    : [];

  return (
    <>
      <PageHeader
        title={role === "faculty" ? "Course Analysis" : "Result Analysis"}
        description={DESCRIPTIONS[role]}
      />

      {error && <Alert variant="danger">{error}</Alert>}

      {loadingCourses && <Spinner animation="border" size="sm" aria-label="Loading courses" />}

      {!loadingCourses && courses.length === 0 && !error && (
        <EmptyState title="No courses yet">There are no courses to analyse.</EmptyState>
      )}

      {courses.length > 0 && (
        <Form.Group className="mb-3" controlId="analysis-course" style={{ maxWidth: 420 }}>
          <Form.Label>Course</Form.Label>
          <Form.Select value={courseId} onChange={(event) => setCourseId(event.target.value)}>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.code} - {course.name}
              </option>
            ))}
          </Form.Select>
        </Form.Group>
      )}

      {loading && <Spinner animation="border" size="sm" aria-label="Loading analysis" />}

      {!loading && analysis && (
        <>
          <Row className="g-3 mb-4">
            {stats.map(([label, value]) => (
              <Col key={label} xs={6} md={4} xl>
                <Card className="srs-panel h-100 text-center">
                  <Card.Body>
                    <div className="text-muted small">{label}</div>
                    <div className="fs-3 fw-bold" data-testid={label}>
                      {value}
                    </div>
                  </Card.Body>
                </Card>
              </Col>
            ))}
          </Row>

          {appeared === 0 ? (
            <EmptyState title="No results yet">
              Students appear here once all four marks (ISA-1, ISA-2, Assessment and ESA) are
              entered.
            </EmptyState>
          ) : (
            <Card className="srs-panel">
              <Card.Body>
                <h2 className="h5">Grade distribution</h2>
                <Table size="sm" className="mb-0 align-middle">
                  <thead>
                    <tr>
                      <th style={{ width: 80 }}>Grade</th>
                      <th style={{ width: 100 }}>Students</th>
                      <th>Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {GRADE_ORDER.map((grade) => [
                      grade,
                      analysis.grade_distribution[grade] || 0,
                    ]).map(([grade, count]) => (
                      <tr key={grade}>
                        <td>{grade}</td>
                        <td data-testid={`grade-${grade}`}>{count}</td>
                        <td>
                          <ProgressBar
                            now={(count * 100) / appeared}
                            variant={grade === "F" ? "danger" : "primary"}
                            aria-label={`Grade ${grade}: ${count} of ${appeared}`}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          )}
        </>
      )}
    </>
  );
}
