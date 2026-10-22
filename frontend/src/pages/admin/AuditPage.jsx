import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Badge, Form, Spinner, Table } from "react-bootstrap";
import { listAuditLogs } from "../../api/admin.js";
import EmptyState from "../../components/EmptyState.jsx";
import PageHeader from "../../components/PageHeader.jsx";

const ENTITIES = [
  { value: "", label: "All entities" },
  { value: "marks", label: "Marks" },
  { value: "attendance", label: "Attendance" },
  { value: "fee_status", label: "Fee Status" },
  { value: "exam_eligibility", label: "Exam Eligibility" },
];

function formatTimestamp(isoString) {
  if (!isoString) return "-";
  try {
    const d = new Date(isoString);
    return d.toLocaleString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export default function AuditPage() {
  const [logs, setLogs] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [entityFilter, setEntityFilter] = useState("");

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const data = await listAuditLogs();
      setLogs(data);
    } catch (err) {
      setLoadError(err?.response?.data?.error || "Could not load audit log entries.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredLogs = useMemo(() => {
    if (!logs) return [];
    const term = search.trim().toLowerCase();
    return logs.filter((log) => {
      const matchesEntity = !entityFilter || log.entity === entityFilter;
      const matchesSearch =
        !term ||
        log.action?.toLowerCase().includes(term) ||
        log.entity?.toLowerCase().includes(term) ||
        log.entity_id?.toLowerCase().includes(term) ||
        log.user_email?.toLowerCase().includes(term) ||
        log.old_value?.toLowerCase().includes(term) ||
        log.new_value?.toLowerCase().includes(term);
      return matchesEntity && matchesSearch;
    });
  }, [logs, search, entityFilter]);

  return (
    <>
      <PageHeader
        title="Audit Log"
        description="Immutable audit trail of changes made to marks, attendance, fee status and eligibility overrides."
      />

      {loadError && <Alert variant="danger">{loadError}</Alert>}

      <section className="srs-panel">
        <div className="srs-toolbar">
          <Form.Control
            type="search"
            placeholder="Search by action, user, old/new value..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search audit log"
          />
          <Form.Select
            value={entityFilter}
            onChange={(e) => setEntityFilter(e.target.value)}
            aria-label="Filter by entity"
          >
            {ENTITIES.map((ent) => (
              <option key={ent.value} value={ent.value}>
                {ent.label}
              </option>
            ))}
          </Form.Select>
        </div>

        {logs === null ? (
          <div className="text-center py-5">
            <Spinner animation="border" role="status" aria-label="Loading audit logs" />
          </div>
        ) : filteredLogs.length === 0 ? (
          <EmptyState
            icon="log"
            title="No audit log entries found"
            description={
              logs.length === 0
                ? "Changes to marks, attendance, fees and overrides will be recorded here."
                : "No log records match your search or filter."
            }
          />
        ) : (
          <div className="table-responsive">
            <Table hover className="srs-table mb-0 align-middle">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Target ID</th>
                  <th>Old Value</th>
                  <th>New Value</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="text-muted small">{formatTimestamp(log.timestamp)}</td>
                    <td>
                      <span className="fw-medium">{log.user_email || `User #${log.user_id}`}</span>
                    </td>
                    <td>
                      <Badge bg="secondary" className="text-uppercase">
                        {log.action}
                      </Badge>
                    </td>
                    <td className="text-capitalize">{log.entity?.replace("_", " ")}</td>
                    <td className="font-monospace small">{log.entity_id}</td>
                    <td>
                      {log.old_value !== null ? (
                        <span className="text-muted">{log.old_value}</span>
                      ) : (
                        <span className="text-muted fst-italic">None</span>
                      )}
                    </td>
                    <td>
                      <span className="fw-semibold text-primary">{log.new_value || "-"}</span>
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
