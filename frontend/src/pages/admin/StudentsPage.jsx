import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Col, Form, Modal, Row, Spinner, Table } from "react-bootstrap";
import * as adminApi from "../../api/admin.js";
import ConfirmDialog from "../../components/ConfirmDialog.jsx";
import EmptyState from "../../components/EmptyState.jsx";
import Icon from "../../components/Icon.jsx";
import PageHeader from "../../components/PageHeader.jsx";
import { apiErrorMessage, useToast } from "../../components/toast.js";

const EMPTY_FORM = {
  srn: "",
  name: "",
  email: "",
  semester: "1",
  department_id: "",
  section_id: "",
};
const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8];

function StudentForm({ show, student, departments, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!show) return;
    setError("");
    setForm(
      student
        ? {
            srn: student.srn,
            name: student.name,
            email: student.email,
            semester: String(student.semester),
            department_id: String(student.department_id ?? ""),
            section_id: String(student.section_id ?? ""),
          }
        : EMPTY_FORM,
    );
  }, [show, student]);

  const sections = departments.find((d) => String(d.id) === form.department_id)?.sections || [];

  function update(field, value) {
    setForm((f) => ({
      ...f,
      [field]: value,
      ...(field === "department_id" ? { section_id: "" } : {}),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSaving(true);
    const payload = {
      srn: form.srn.trim(),
      name: form.name.trim(),
      email: form.email.trim(),
      semester: Number(form.semester),
      department_id: Number(form.department_id),
      section_id: Number(form.section_id),
    };
    try {
      if (student) {
        await adminApi.updateStudent(student.id, payload);
        toast(`${payload.name} updated`);
      } else {
        await adminApi.createStudent(payload);
        toast(`${payload.name} added`);
      }
      onSaved();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal show={show} onHide={onClose} centered size="lg">
      <Form onSubmit={handleSubmit}>
        <Modal.Header closeButton>
          <Modal.Title as="h2" className="h5">
            {student ? `Edit ${student.name}` : "Add student"}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && <Alert variant="danger">{error}</Alert>}
          <Row className="g-3">
            <Col md={5}>
              <Form.Group controlId="student-srn">
                <Form.Label>SRN</Form.Label>
                <Form.Control
                  value={form.srn}
                  onChange={(e) => update("srn", e.target.value)}
                  placeholder="PES1UG24AM001"
                  required
                />
              </Form.Group>
            </Col>
            <Col md={7}>
              <Form.Group controlId="student-name">
                <Form.Label>Full name</Form.Label>
                <Form.Control
                  value={form.name}
                  onChange={(e) => update("name", e.target.value)}
                  required
                />
              </Form.Group>
            </Col>
            <Col md={8}>
              <Form.Group controlId="student-email">
                <Form.Label>Email</Form.Label>
                <Form.Control
                  type="email"
                  value={form.email}
                  onChange={(e) => update("email", e.target.value)}
                  required
                />
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group controlId="student-semester">
                <Form.Label>Semester</Form.Label>
                <Form.Select
                  value={form.semester}
                  onChange={(e) => update("semester", e.target.value)}
                >
                  {SEMESTERS.map((s) => (
                    <option key={s} value={s}>
                      Semester {s}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group controlId="student-department">
                <Form.Label>Department</Form.Label>
                <Form.Select
                  value={form.department_id}
                  onChange={(e) => update("department_id", e.target.value)}
                  required
                >
                  <option value="">Choose a department</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group controlId="student-section">
                <Form.Label>Section</Form.Label>
                <Form.Select
                  value={form.section_id}
                  onChange={(e) => update("section_id", e.target.value)}
                  required
                  disabled={!form.department_id}
                >
                  <option value="">
                    {form.department_id ? "Choose a section" : "Pick a department first"}
                  </option>
                  {sections.map((s) => (
                    <option key={s.id} value={s.id}>
                      Section {s.name}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" className="btn-srs" disabled={saving}>
            {student ? "Save changes" : "Add student"}
          </Button>
        </Modal.Footer>
      </Form>
    </Modal>
  );
}

export default function StudentsPage() {
  const toast = useToast();
  const [students, setStudents] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [sectionFilter, setSectionFilter] = useState("");
  const [semesterFilter, setSemesterFilter] = useState("");
  const [editing, setEditing] = useState(null); // null = closed, {} = new, student = edit
  const [toDelete, setToDelete] = useState(null);

  const load = useCallback(async () => {
    try {
      const filters = {
        search: search.trim(),
        department_id: departmentFilter,
        section_id: sectionFilter,
        semester: semesterFilter,
      };

      Object.keys(filters).forEach((key) => {
        if (!filters[key]) delete filters[key];
      });

      const [studentList, departmentList] = await Promise.all([
        adminApi.listStudents(filters),
        adminApi.listDepartments(),
      ]);

      setStudents(studentList);
      setDepartments(departmentList);
      setLoadError("");
    } catch (error) {
      setLoadError(apiErrorMessage(error));
    }
  }, [search, departmentFilter, sectionFilter, semesterFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const visible = students || [];

  async function handleDelete() {
    const student = toDelete;
    setToDelete(null);
    try {
      await adminApi.deleteStudent(student.id);
      toast(`${student.name} deleted`);
      load();
    } catch (error) {
      toast(apiErrorMessage(error), "danger");
    }
  }

  const noDepartments = departments.length === 0;

  return (
    <>
      <PageHeader
        title="Students"
        description="Add students, keep their details correct, and place them in a section."
        action={
          <Button
            className="btn-srs btn-icon"
            onClick={() => setEditing({})}
            disabled={!students || noDepartments}
          >
            <Icon name="plus" />
            Add student
          </Button>
        }
      />

      {loadError && <Alert variant="danger">{loadError}</Alert>}
      {students && noDepartments && (
        <Alert variant="warning">
          Create a department and a section first, then you can add students.
        </Alert>
      )}

      <section className="srs-panel">
        <div className="srs-toolbar">
          <Form.Control
            type="search"
            placeholder="Search by name, SRN or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search students"
          />
          <Form.Select
            value={departmentFilter}
            onChange={(e) => {
              setDepartmentFilter(e.target.value);
              setSectionFilter("");
            }}
            aria-label="Filter by department"
          >
            <option value="">All departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Form.Select>

          <Form.Select
            value={sectionFilter}
            onChange={(e) => setSectionFilter(e.target.value)}
            aria-label="Filter by section"
          >
            <option value="">All sections</option>
            {departments
              .filter((d) => !departmentFilter || String(d.id) === departmentFilter)
              .flatMap((d) => d.sections || [])
              .map((section) => (
                <option key={section.id} value={section.id}>
                  {section.name}
                </option>
              ))}
          </Form.Select>

          <Form.Select
            value={semesterFilter}
            onChange={(e) => setSemesterFilter(e.target.value)}
            aria-label="Filter by semester"
          >
            <option value="">All semesters</option>
            {SEMESTERS.map((semester) => (
              <option key={semester} value={semester}>
                Semester {semester}
              </option>
            ))}
          </Form.Select>
          {students && (
            <span className="ms-auto align-self-center text-body-secondary small">
              Showing {visible.length} of {students.length}
            </span>
          )}
        </div>

        {!students && !loadError && (
          <div className="text-center py-5">
            <Spinner animation="border" role="status" aria-label="Loading students" />
          </div>
        )}
        {students &&
          students.length === 0 &&
          !search.trim() &&
          !departmentFilter &&
          !sectionFilter &&
          !semesterFilter && (
            <EmptyState title="No students yet">
              Use Add student to create the first record.
            </EmptyState>
          )}

        {students &&
          visible.length === 0 &&
          (search.trim() || departmentFilter || sectionFilter || semesterFilter) && (
            <EmptyState title="No matching students">
              Try a different name, SRN or department.
            </EmptyState>
          )}
        {visible.length > 0 && (
          <div className="table-responsive">
            <Table hover className="srs-table">
              <thead>
                <tr>
                  <th>SRN</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Department</th>
                  <th>Section</th>
                  <th>Sem</th>
                  <th className="text-end">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((s) => (
                  <tr key={s.id}>
                    <td className="srs-srn">{s.srn}</td>
                    <td>{s.name}</td>
                    <td className="text-body-secondary">{s.email}</td>
                    <td>{s.department_name}</td>
                    <td>{s.section_name}</td>
                    <td>{s.semester}</td>
                    <td className="text-end text-nowrap">
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        className="me-2"
                        onClick={() => setEditing(s)}
                        aria-label={`Edit ${s.name}`}
                      >
                        <Icon name="edit" size={16} />
                      </Button>
                      <Button
                        variant="outline-danger"
                        size="sm"
                        onClick={() => setToDelete(s)}
                        aria-label={`Delete ${s.name}`}
                      >
                        <Icon name="trash" size={16} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </section>

      <StudentForm
        show={editing !== null}
        student={editing && editing.id ? editing : null}
        departments={departments}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          load();
        }}
      />

      <ConfirmDialog
        show={Boolean(toDelete)}
        title="Delete student?"
        body={
          toDelete &&
          `${toDelete.name} (${toDelete.srn}) and all their attendance, fee and marks records will be deleted.`
        }
        confirmLabel="Delete student"
        onConfirm={handleDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  );
}
