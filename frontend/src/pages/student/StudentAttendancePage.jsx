import { useEffect, useState } from "react";
import { Alert, Badge, Container, Spinner, Table } from "react-bootstrap";
import * as attendanceApi from "../../api/attendance.js";
import { apiErrorMessage } from "../../api/errors.js";

// Student My Attendance page (SRS-F-013, SRS-F-014, SRS-F-021, issue #14).
// Displays attendance percentage for each enrolled course with a red Shortage badge if < 75%.
export default function StudentAttendancePage() {
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    attendanceApi
      .getStudentAttendance()
      .then((data) => setAttendance(data.attendance || []))
      .catch((err) => setError(apiErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Container className="py-4">
        <Spinner animation="border" role="status" aria-label="Loading attendance" />
      </Container>
    );
  }

  return (
    <Container className="pb-5">
      <h1 className="h3 mb-3">My Attendance</h1>
      {error && <Alert variant="danger">{error}</Alert>}

      {attendance.length === 0 ? (
        <p className="text-muted">You are not enrolled in any courses yet.</p>
      ) : (
        <Table striped hover responsive>
          <thead>
            <tr>
              <th>Course Code</th>
              <th>Course Name</th>
              <th className="text-center">Credits</th>
              <th className="text-center">Classes Attended</th>
              <th className="text-center">Attendance %</th>
              <th className="text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {attendance.map((course) => (
              <tr key={course.course_id}>
                <td>{course.course_code}</td>
                <td>{course.course_name}</td>
                <td className="text-center">{course.credits}</td>
                <td className="text-center">
                  {course.attended} / {course.held}
                </td>
                <td className="text-center">
                  <span className={course.shortage ? "text-danger fw-bold" : ""}>
                    {course.percentage != null ? `${course.percentage}%` : "—"}
                  </span>
                </td>
                <td className="text-center">
                  {course.shortage ? (
                    <Badge bg="danger">Shortage</Badge>
                  ) : (
                    <Badge bg="success">OK</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Container>
  );
}
