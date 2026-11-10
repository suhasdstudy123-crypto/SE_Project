import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Form, Modal, Spinner, Table } from "react-bootstrap";
import * as coursesApi from "../../api/courses.js";
import * as esaApi from "../../api/esa.js";
import EmptyState from "../../components/EmptyState.jsx";
import { AttendanceCell, EligibilityStatus, StatusPill } from "../../components/EsaStatus.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import { apiErrorMessage, useToast } from "../../components/toast.js";

// The API sends UTC times without a zone; show them in the user's local time.
function formatTime(iso) {
  return iso ? new Date(`${iso}Z`).toLocaleString() : null;
}

// Admin ESA Window page: open/close registration (card #17), see each course's
// eligibility (card #19) and override it with a reason (card #20).
export default function EsaWindowPage() {
  const toast = useToast();
  const [windowState, setWindowState] = useState(null);
  const [switching, setSwitching] = useState(false);
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  const [overrideRow, setOverrideRow] = useState(null);
  const [reason, setReason] = useState("");
  const [overrideError, setOverrideError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([esaApi.getEsaWindow(), coursesApi.listCourses()])
      .then(([state, list]) => {
        setWindowState(state);
        setCourses(list);
        if (list.length > 0) setCourseId(String(list[0].id));
        else setRows([]);
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, []);

  const loadRows = useCallback(async () => {
    if (!courseId) return;
    try {
      setRows((await esaApi.getCourseEligibility(courseId)).students);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }, [courseId]);

  useEffect(() => {
    setRows(null);
    loadRows();
  }, [loadRows]);

  async function toggleWindow() {
    setSwitching(true);
    try {
      const state = await esaApi.setEsaWindow(!windowState.is_open);
      setWindowState(state);
      toast(state.is_open ? "ESA registration is now open" : "ESA registration is now closed");
    } catch (err) {
      toast(apiErrorMessage(err), "danger");
    } finally {
      setSwitching(false);
    }
  }

  function openOverride(row) {
    setOverrideRow(row);
    setReason("");
    setOverrideError("");
  }

  async function saveOverride(event) {
    event.preventDefault();
    setSaving(true);
    setOverrideError("");
    try {
      await esaApi.createOverride(overrideRow.student_id, Number(courseId), reason);
      toast(`${overrideRow.name} is now eligible (override recorded)`);
      setOverrideRow(null);
      await loadRows();
    } catch (err) {
      setOverrideError(apiErrorMessage(err, "Could not save the override."));
    } finally {
      setSaving(false);
    }
  }

  const isOpen = windowState?.is_open;
  const course = courses.find((c) => String(c.id) === courseId);

  return (
    <>
      <PageHeader
        title="ESA Window"
        description="Students can register for or drop an ESA only while registration is open. They need paid fees and at least 75% attendance, unless you override."
        action={
          windowState && (
            <Button
              className={isOpen ? "" : "btn-srs"}
              variant={isOpen ? "outline-danger" : undefined}
              onClick={toggleWindow}
              disabled={switching}
            >
              {isOpen ? "Close registration" : "Open registration"}
            </Button>
          )
        }
      />

      {error && <Alert variant="danger">{error}</Alert>}

      {windowState && (
        <section className="srs-panel p-3 mb-4 d-flex flex-wrap align-items-center gap-3">
          <span>
            Registration is{" "}
            <StatusPill kind={isOpen ? "paid" : "unpaid"}>{isOpen ? "Open" : "Closed"}</StatusPill>
          </span>
          <span className="text-muted small">
            {isOpen
              ? windowState.opened_at && `Opened ${formatTime(windowState.opened_at)}`
              : windowState.closed_at && `Closed ${formatTime(windowState.closed_at)}`}
          </span>
        </section>
      )}

      <section className="srs-panel">
        <div className="srs-toolbar">
          <Form.Select
            value={courseId}
            onChange={(e) => setCourseId(e.target.value)}
            aria-label="Course"
            disabled={courses.length === 0}
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} – {c.name}
              </option>
            ))}
          </Form.Select>
        </div>

        {rows === null && !error && (
          <div className="text-center py-5">
            <Spinner animation="border" role="status" aria-label="Loading eligibility" />
          </div>
        )}
        {rows && courses.length === 0 && (
          <EmptyState title="No courses yet">Add courses and enroll students first.</EmptyState>
        )}
        {rows && courses.length > 0 && rows.length === 0 && (
          <EmptyState title="Nobody is enrolled">
            Enroll students in this course on the Courses page.
          </EmptyState>
        )}
        {rows && rows.length > 0 && (
          <div className="table-responsive">
            <Table hover className="srs-table">
              <thead>
                <tr>
                  <th>SRN</th>
                  <th>Name</th>
                  <th>Fees (sem)</th>
                  <th>Attendance</th>
                  <th>Eligibility</th>
                  <th>ESA</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.student_id}>
                    <td className="srs-srn">{row.srn}</td>
                    <td>{row.name}</td>
                    <td>
                      <StatusPill kind={row.fees_paid ? "paid" : "unpaid"}>
                        {row.fees_paid ? "Paid" : "Unpaid"}
                      </StatusPill>
                      <span className="text-muted small ms-1">({row.semester})</span>
                    </td>
                    <td>
                      <AttendanceCell row={row} />
                    </td>
                    <td>
                      <EligibilityStatus row={row} />
                    </td>
                    <td>
                      {row.registered ? (
                        <StatusPill kind="paid">Registered</StatusPill>
                      ) : (
                        <StatusPill kind="none">Not registered</StatusPill>
                      )}
                    </td>
                    <td className="text-end">
                      {!row.eligible && (
                        <Button
                          size="sm"
                          variant="outline-primary"
                          onClick={() => openOverride(row)}
                          aria-label={`Override ${row.srn}`}
                        >
                          Override
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

      <Modal show={overrideRow !== null} onHide={() => setOverrideRow(null)} centered>
        <Form onSubmit={saveOverride}>
          <Modal.Header closeButton>
            <Modal.Title as="h2" className="h5">
              Override eligibility
            </Modal.Title>
          </Modal.Header>
          <Modal.Body>
            {overrideError && <Alert variant="danger">{overrideError}</Alert>}
            <p>
              Allow <strong>{overrideRow?.name}</strong> ({overrideRow?.srn}) to register for the{" "}
              <strong>{course?.code}</strong> ESA.
            </p>
            {overrideRow && overrideRow.reasons.length > 0 && (
              <p className="text-danger small">Blocked by: {overrideRow.reasons.join(" · ")}</p>
            )}
            <Form.Group controlId="override-reason">
              <Form.Label>Reason (required)</Form.Label>
              <Form.Control
                as="textarea"
                rows={3}
                maxLength={255}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Medical certificate submitted"
                required
              />
              <Form.Text>The override and its reason are recorded in the audit log.</Form.Text>
            </Form.Group>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="outline-secondary" onClick={() => setOverrideRow(null)}>
              Cancel
            </Button>
            <Button type="submit" className="btn-srs" disabled={saving || !reason.trim()}>
              {saving ? "Saving…" : "Save override"}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </>
  );
}
