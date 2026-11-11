import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Spinner, Table } from "react-bootstrap";
import * as esaApi from "../../api/esa.js";
import EmptyState from "../../components/EmptyState.jsx";
import { AttendanceCell, EligibilityStatus, StatusPill } from "../../components/EsaStatus.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import { apiErrorMessage, useToast } from "../../components/toast.js";

// Student ESA Registration page: register for or drop each enrolled course's ESA (card #18).
// Ineligible courses show the exact reason and Register is disabled (card #19).
export default function EsaRegistrationPage() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      setData(await esaApi.getMyEsa());
      setError("");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(course, action) {
    setBusyId(course.course_id);
    try {
      if (action === "register") {
        await esaApi.registerEsa(course.course_id);
        toast(`Registered for the ${course.course_code} ESA`);
      } else {
        await esaApi.dropEsa(course.course_id);
        toast(`Dropped the ${course.course_code} ESA`);
      }
    } catch (err) {
      toast(apiErrorMessage(err), "danger");
    } finally {
      setBusyId(null);
      await load();
    }
  }

  const isOpen = data?.window.is_open;

  return (
    <>
      <PageHeader
        title="ESA Registration"
        description="Register for the end-semester exam (ESA) of each course. You need paid fees and at least 75% attendance in the course."
      />

      {error && <Alert variant="danger">{error}</Alert>}
      {data && !isOpen && (
        <Alert variant="warning">
          ESA registration is closed. You can register or drop only while the exam cell has it open.
        </Alert>
      )}

      <section className="srs-panel">
        {!data && !error && (
          <div className="text-center py-5">
            <Spinner animation="border" role="status" aria-label="Loading ESA registration" />
          </div>
        )}
        {data && data.courses.length === 0 && (
          <EmptyState title="No courses yet">You are not enrolled in any courses yet.</EmptyState>
        )}
        {data && data.courses.length > 0 && (
          <div className="table-responsive">
            <Table hover className="srs-table">
              <thead>
                <tr>
                  <th>Course</th>
                  <th>Attendance</th>
                  <th>Fees</th>
                  <th>Eligibility</th>
                  <th>ESA</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {data.courses.map((course) => (
                  <tr key={course.course_id}>
                    <td>
                      <div className="srs-srn">{course.course_code}</div>
                      <div className="small text-muted">{course.course_name}</div>
                    </td>
                    <td>
                      <AttendanceCell row={course} />
                    </td>
                    <td>
                      <StatusPill kind={course.fees_paid ? "paid" : "unpaid"}>
                        {course.fees_paid ? "Paid" : "Unpaid"}
                      </StatusPill>
                    </td>
                    <td>
                      <EligibilityStatus row={course} />
                    </td>
                    <td>
                      {course.registered ? (
                        <StatusPill kind="paid">Registered</StatusPill>
                      ) : (
                        <StatusPill kind="none">Not registered</StatusPill>
                      )}
                    </td>
                    <td className="text-end">
                      {course.registered ? (
                        <Button
                          size="sm"
                          variant="outline-danger"
                          disabled={!isOpen || busyId === course.course_id}
                          onClick={() => act(course, "drop")}
                          aria-label={`Drop ${course.course_code}`}
                        >
                          Drop
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          className="btn-srs"
                          disabled={!isOpen || !course.eligible || busyId === course.course_id}
                          onClick={() => act(course, "register")}
                          aria-label={`Register ${course.course_code}`}
                        >
                          Register
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </section>
    </>
  );
}
