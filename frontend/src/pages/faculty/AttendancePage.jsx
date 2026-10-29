import { useEffect, useState } from "react";
import { Alert, Badge, Button, Col, Container, Form, Row, Spinner, Table } from "react-bootstrap";
import * as attendanceApi from "../../api/attendance.js";
import * as coursesApi from "../../api/courses.js";
import { apiErrorMessage } from "../../api/errors.js";
import { todayIso } from "../../utils/dates.js";

// Faculty Mark Attendance page (issues #13, #14): pick course + date, everyone starts as present
// (SAD 4.5, NF-002), untick absentees, Save. Displays attendance % with Shortage warning if < 75%.
export default function AttendancePage() {
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [date, setDate] = useState(todayIso());
  const [students, setStudents] = useState([]);
  const [recorded, setRecorded] = useState(false);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [loadingClass, setLoadingClass] = useState(false);
  const [saving, setSaving] = useState(false);
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
    if (!courseId || !date) return;
    setLoadingClass(true);
    setError("");
    setMessage("");
    attendanceApi
      .getClassAttendance(courseId, date)
      .then((data) => {
        setStudents(data.students);
        setRecorded(data.recorded);
      })
      .catch((err) => {
        setStudents([]);
        setError(apiErrorMessage(err));
      })
      .finally(() => setLoadingClass(false));
  }, [courseId, date]);

  function togglePresent(studentId) {
    setStudents(
      students.map((student) =>
        student.student_id === studentId ? { ...student, present: !student.present } : student,
      ),
    );
  }

  function markAllPresent() {
    setStudents(students.map((student) => ({ ...student, present: true })));
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const records = students.map(({ student_id, present }) => ({ student_id, present }));
      const result = await attendanceApi.saveClassAttendance(courseId, date, records);
      setRecorded(true);
      setMessage(
        result.corrected > 0
          ? `Attendance saved. ${result.corrected} correction(s) recorded in the audit log.`
          : "Attendance saved.",
      );
      const updated = await attendanceApi.getClassAttendance(courseId, date);
      setStudents(updated.students);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not save attendance."));
    } finally {
      setSaving(false);
    }
  }

  const presentCount = students.filter((student) => student.present).length;

  if (loadingCourses) {
    return (
      <Container>
        <Spinner animation="border" role="status" aria-label="Loading courses" />
      </Container>
    );
  }

  return (
    <Container className="pb-5">
      <h1 className="h3 mb-3">Mark Attendance</h1>
      {error && <Alert variant="danger">{error}</Alert>}
      {message && <Alert variant="success">{message}</Alert>}

      {courses.length === 0 ? (
        <p className="text-muted">You are not assigned to any courses yet.</p>
      ) : (
        <>
          <Row className="g-3 mb-3">
            <Col md={6}>
              <Form.Group controlId="attendance-course">
                <Form.Label>Course</Form.Label>
                <Form.Select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.code} – {course.name}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={3}>
              <Form.Group controlId="attendance-date">
                <Form.Label>Date</Form.Label>
                <Form.Control
                  type="date"
                  value={date}
                  max={todayIso()}
                  onChange={(e) => setDate(e.target.value)}
                />
              </Form.Group>
            </Col>
          </Row>

          {loadingClass ? (
            <Spinner animation="border" role="status" aria-label="Loading students" />
          ) : students.length === 0 ? (
            <p className="text-muted">No students are enrolled in this course.</p>
          ) : (
            <>
              <div className="d-flex flex-wrap align-items-center gap-3 mb-2">
                {recorded ? (
                  <Badge bg="warning" text="dark">
                    Already recorded – saving changes will correct it
                  </Badge>
                ) : (
                  <Badge bg="secondary">Not recorded yet – everyone starts as present</Badge>
                )}
                <span>
                  {presentCount} of {students.length} present
                </span>
                <Button size="sm" variant="outline-secondary" onClick={markAllPresent}>
                  All present
                </Button>
              </div>
              <Table striped hover responsive>
                <thead>
                  <tr>
                    <th>SRN</th>
                    <th>Name</th>
                    <th className="text-center">Attendance %</th>
                    <th className="text-center">Present</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((student) => (
                    <tr
                      key={student.student_id}
                      className={student.present ? "" : "table-danger"}
                      onClick={() => togglePresent(student.student_id)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>{student.srn}</td>
                      <td>{student.name}</td>
                      <td className="text-center">
                        <span className={student.shortage ? "text-danger fw-bold" : ""}>
                          {student.percentage != null ? `${student.percentage}%` : "—"}
                        </span>
                        {student.shortage && (
                          <Badge bg="danger" className="ms-2">
                            Shortage
                          </Badge>
                        )}
                      </td>
                      <td className="text-center">
                        <Form.Check
                          type="checkbox"
                          checked={student.present}
                          onChange={() => togglePresent(student.student_id)}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`${student.srn} present`}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving…" : "Save attendance"}
              </Button>
            </>
          )}
        </>
      )}
    </Container>
  );
}
