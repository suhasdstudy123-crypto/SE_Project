// Shared ESA badges for the Admin and Student pages (cards #17-#20).

export function StatusPill({ kind, children, title }) {
  return (
    <span className={`srs-status srs-status-${kind}`} title={title}>
      {children}
    </span>
  );
}

// Eligible / Override / Blocked, with the exact reason when blocked (SRS 3.1).
export function EligibilityStatus({ row }) {
  if (row.override) {
    return (
      <>
        <StatusPill kind="override" title={`Override reason: ${row.override.reason}`}>
          Override
        </StatusPill>
        <div className="small text-muted mt-1">{row.override.reason}</div>
      </>
    );
  }
  if (row.eligible) return <StatusPill kind="paid">Eligible</StatusPill>;
  return (
    <>
      <StatusPill kind="unpaid">Not eligible</StatusPill>
      <div className="small text-danger mt-1">{row.reasons.join(" · ")}</div>
    </>
  );
}

export function AttendanceCell({ row }) {
  if (row.held === 0) return <span className="text-muted">No classes yet</span>;
  return (
    <>
      <span className={row.percentage < 75 ? "text-danger fw-bold" : ""}>{row.percentage}%</span>
      <span className="text-muted small ms-1">
        ({row.attended}/{row.held})
      </span>
    </>
  );
}
