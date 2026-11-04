import { useEffect, useState } from "react";
import { Alert, Badge, Button, Col, Container, Form, Row, Spinner, Table } from "react-bootstrap";
import * as coursesApi from "../../api/courses.js";
import { apiErrorMessage } from "../../api/errors.js";
import * as marksApi from "../../api/marks.js";

const LIMITS = {
  isa1: { name: "ISA-1", min: 0, max: 20 },
  isa2: { name: "ISA-2", min: 0, max: 20 },
  assessment: { name: "Assessment", min: 0, max: 10 },
  esa: { name: "ESA", min: 0, max: 50 },
};

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
        setCourses(mine);
        if (mine.length > 0) setCourseId(String(mine[0].id));
      })
      .catch((err) => setError(apiErrorMessage(err)))
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
      .then((data) => setStudents(data.students || []))
      .catch((err) => {
        setStudents([]);
        setError(apiErrorMessage(err, "Could not load marks."));
      })
      .finally(() => setLoadingMarks(false));
  }, [courseId]);

  function handleFieldChange(studentId, field, value) {
    const errorKey = `${studentId}_${field}`;
    let errorText = "";

    if (value !== "" && value !== null && value !== undefined) {
      const num = Number(value);
      const conf = LIMITS[field];
      if (Number.isNaN(num)) {
        errorText = "Must be a number";
      } else if (num < conf.min || num > conf.max) {
        errorText = `Max ${conf.max}`;
      }
    }

    setFieldErrors((prev) => {
      const next = { ...prev };
      if (errorText) next[errorKey] = errorText;
      else delete next[errorKey];
      return next;
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
                  <th style={{ width: "20%" }}>Name</th>
                  <th style={{ width: "12%" }}>ISA-1 (20)</th>
                  <th style={{ width: "12%" }}>ISA-2 (20)</th>
                  <th style={{ width: "12%" }}>Assessment (10)</th>
                  <th style={{ width: "14%" }}>ESA (50)</th>
                  <th style={{ width: "8%" }} className="text-center">
                    Total
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
