import { useEffect, useState } from "react";
import { Alert, Badge, Button, Col, Container, Form, Row, Spinner, Table } from "react-bootstrap";
import * as coursesApi from "../../api/courses.js";
import { apiErrorMessage } from "../../api/errors.js";
import * as marksApi from "../../api/marks.js";

// Faculty Enter Marks page (SRS-F-019, SRS-F-020, SRS-F-025, issues #15 & #16).
// Limits: ISA-1 (20), ISA-2 (20), Assessment (10), ESA (50). Total max 100.
// Auto-calculates Grade (S/A/B/C/D/E/F) based on PES grading scale.
const LIMITS = {
  isa1: { max: 20, label: "ISA-1" },
  isa2: { max: 20, label: "ISA-2" },
  assessment: { max: 10, label: "Assessment" },
  esa: { max: 50, label: "ESA" },
};

function computeGrade(student) {
  if (student.grade) return student.grade;
  const total = student.total;
  if (total === null || total === undefined) return "—";
  if (total >= 90) return "S";
  if (total >= 80) return "A";
  if (total >= 70) return "B";
  if (total >= 60) return "C";
  if (total >= 50) return "D";
  if (total >= 40) return "E";
  return "F";
}

export default function MarksPage() {
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [students, setStudents] = useState([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [loadingMarks, setLoadingMarks] = useState(false);
  const [savingId, setSavingId] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    coursesApi
      .listMyCourses("faculty")
      .then((mine) => {
        const list = mine || [];
        setCourses(list);
        if (list.length > 0) {
          setCourseId(String(list[0].id));
        }
      })
      .catch((err) => setError(apiErrorMessage(err, "Failed to load courses.")))
      .finally(() => setLoadingCourses(false));
  }, []);

  useEffect(() => {
    if (!courseId) return;
    setLoadingMarks(true);
    setError("");
    setMessage("");
    setFieldErrors({});

    marksApi
      .getCourseMarks(courseId)
      .then((data) => {
        setStudents(data.students || []);
      })
      .catch((err) => setError(apiErrorMessage(err, "Failed to load marks.")))
      .finally(() => setLoadingMarks(false));
  }, [courseId]);

  function handleFieldChange(studentId, field, value) {
    const lim = LIMITS[field];
    const num = Number(value);

    setFieldErrors((prev) => {
      const copy = { ...prev };
      const key = `${studentId}_${field}`;
      if (value !== "" && (Number.isNaN(num) || num < 0 || num > lim.max)) {
        copy[key] = `Max ${lim.max}`;
      } else {
        delete copy[key];
      }
      return copy;
    });

    setStudents((prev) =>
      prev.map((s) => {
        if (s.student_id !== studentId) return s;
        const updated = { ...s, [field]: value === "" ? null : value };
        // calculate live total
        const comps = [updated.isa1, updated.isa2, updated.assessment, updated.esa];
        const validComps = comps
          .filter((c) => c !== null && c !== undefined && c !== "" && !Number.isNaN(Number(c)))
          .map(Number);
        updated.total = validComps.length > 0 ? validComps.reduce((a, b) => a + b, 0) : null;
        updated.grade = null; // Recompute live grade from updated total
        return updated;
      }),
    );
  }

  async function handleSaveRow(student) {
    const studentId = student.student_id;
    // Check if this student has active field errors
    const studentErrorKeys = Object.keys(fieldErrors).filter((k) => k.startsWith(`${studentId}_`));
    if (studentErrorKeys.length > 0) {
      setError("Please fix invalid marks before saving.");
      return;
    }

    setSavingId(studentId);
    setError("");
    setMessage("");

    const payload = {};
    for (const key of Object.keys(LIMITS)) {
      if (student[key] !== null && student[key] !== undefined && student[key] !== "") {
        payload[key] = Number(student[key]);
      } else {
        payload[key] = null;
      }
    }

    try {
      const res = await marksApi.saveStudentMarks(courseId, studentId, payload);
      setMessage(`Marks saved for ${student.srn}.`);
      setStudents((prev) =>
        prev.map((s) => (s.student_id === studentId ? { ...s, ...res.marks } : s)),
      );
    } catch (err) {
      setError(apiErrorMessage(err, "Could not save marks."));
    } finally {
      setSavingId(null);
    }
  }

  if (loadingCourses) {
    return (
      <Container className="py-4">
        <Spinner animation="border" role="status" aria-label="Loading courses" />
      </Container>
    );
  }

  return (
    <Container className="pb-5">
      <h1 className="h3 mb-3">Enter Marks</h1>
      {error && <Alert variant="danger">{error}</Alert>}
      {message && <Alert variant="success">{message}</Alert>}

      {courses.length === 0 ? (
        <p className="text-muted">You are not assigned to any courses yet.</p>
      ) : (
        <>
          <Row className="g-3 mb-4">
            <Col md={6}>
              <Form.Group controlId="marks-course">
                <Form.Label>Course</Form.Label>
                <Form.Select
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value)}
                  aria-label="Select course"
                >
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code} – {c.name}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
          </Row>

          {loadingMarks ? (
            <Spinner animation="border" role="status" aria-label="Loading marks" />
          ) : students.length === 0 ? (
            <p className="text-muted">No students are enrolled in this course.</p>
          ) : (
            <Table striped hover responsive className="align-middle">
              <thead>
                <tr>
                  <th style={{ width: "16%" }}>SRN</th>
                  <th style={{ width: "18%" }}>Name</th>
                  <th style={{ width: "11%" }}>ISA-1 (20)</th>
                  <th style={{ width: "11%" }}>ISA-2 (20)</th>
                  <th style={{ width: "11%" }}>Assessment (10)</th>
                  <th style={{ width: "13%" }}>ESA (50)</th>
                  <th style={{ width: "7%" }} className="text-center">
                    Total
                  </th>
                  <th style={{ width: "7%" }} className="text-center">
                    Grade
                  </th>
                  <th style={{ width: "6%" }} className="text-center">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {students.map((student) => {
                  const sid = student.student_id;
                  const hasRowError = Object.keys(fieldErrors).some((k) => k.startsWith(`${sid}_`));
                  return (
                    <tr key={sid}>
                      <td className="fw-semibold">{student.srn}</td>
                      <td>{student.name}</td>
                      <td>
                        <Form.Control
                          type="number"
                          step="0.5"
                          min="0"
                          max="20"
                          size="sm"
                          value={student.isa1 ?? ""}
                          isInvalid={!!fieldErrors[`${sid}_isa1`]}
                          onChange={(e) => handleFieldChange(sid, "isa1", e.target.value)}
                          aria-label={`${student.srn} ISA-1`}
                        />
                        <Form.Control.Feedback type="invalid">
                          {fieldErrors[`${sid}_isa1`]}
                        </Form.Control.Feedback>
                      </td>
                      <td>
                        <Form.Control
                          type="number"
                          step="0.5"
                          min="0"
                          max="20"
                          size="sm"
                          value={student.isa2 ?? ""}
                          isInvalid={!!fieldErrors[`${sid}_isa2`]}
                          onChange={(e) => handleFieldChange(sid, "isa2", e.target.value)}
                          aria-label={`${student.srn} ISA-2`}
                        />
                        <Form.Control.Feedback type="invalid">
                          {fieldErrors[`${sid}_isa2`]}
                        </Form.Control.Feedback>
                      </td>
                      <td>
                        <Form.Control
                          type="number"
                          step="0.5"
                          min="0"
                          max="10"
                          size="sm"
                          value={student.assessment ?? ""}
                          isInvalid={!!fieldErrors[`${sid}_assessment`]}
                          onChange={(e) => handleFieldChange(sid, "assessment", e.target.value)}
                          aria-label={`${student.srn} Assessment`}
                        />
                        <Form.Control.Feedback type="invalid">
                          {fieldErrors[`${sid}_assessment`]}
                        </Form.Control.Feedback>
                      </td>
                      <td>
                        {student.is_esa_registered ? (
                          <>
                            <Form.Control
                              type="number"
                              step="0.5"
                              min="0"
                              max="50"
                              size="sm"
                              value={student.esa ?? ""}
                              isInvalid={!!fieldErrors[`${sid}_esa`]}
                              onChange={(e) => handleFieldChange(sid, "esa", e.target.value)}
                              aria-label={`${student.srn} ESA`}
                            />
                            <Form.Control.Feedback type="invalid">
                              {fieldErrors[`${sid}_esa`]}
                            </Form.Control.Feedback>
                          </>
                        ) : (
                          <Badge bg="secondary" title="Student is not registered for ESA">
                            Not Registered
                          </Badge>
                        )}
                      </td>
                      <td className="text-center fw-bold">
                        {student.total !== null && student.total !== undefined
                          ? student.total
                          : "—"}
                      </td>
                      <td className="text-center fw-bold text-primary">{computeGrade(student)}</td>
                      <td className="text-center">
                        <Button
                          size="sm"
                          variant="outline-primary"
                          disabled={savingId === sid || hasRowError}
                          onClick={() => handleSaveRow(student)}
                          aria-label={`Save marks for ${student.srn}`}
                        >
                          {savingId === sid ? "Saving…" : "Save"}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          )}
        </>
      )}
    </Container>
  );
}
