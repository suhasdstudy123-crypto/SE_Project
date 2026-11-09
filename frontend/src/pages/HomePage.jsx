import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Card, Col, Row, Spinner } from "react-bootstrap";
import api from "../api/client.js";
import { useAuth } from "../auth/authContext.js";
import Icon from "../components/Icon.jsx";
import { MENU_ITEMS_BY_ROLE } from "../components/menus.js";
import PageHeader from "../components/PageHeader.jsx";

const TITLES = {
  admin: "Admin dashboard",
  faculty: "Faculty dashboard",
  student: "Student dashboard",
};

const ADMIN_CARDS = [
  { key: "total_students", label: "Total students", icon: "users" },
  { key: "total_courses", label: "Total courses", icon: "book" },
  { key: "fee_defaulters", label: "Fee defaulters", icon: "wallet" },
  {
    key: "attendance_shortages",
    label: "Students below 75% attendance",
    icon: "clipboard",
  },
];

const FACULTY_CARDS = [
  { key: "total_students", label: "Enrolled students", icon: "users" },
  { key: "total_courses", label: "My courses", icon: "book" },
  {
    key: "attendance_shortages",
    label: "Students below 75% attendance",
    icon: "clipboard",
  },
];

function SummaryCards({ summary, role }) {
  const cards = role === "admin" ? ADMIN_CARDS : FACULTY_CARDS;

  return (
    <Row className="g-3 mb-4">
      {cards.map((card) => (
        <Col key={card.key} xs={12} sm={6} xl={3}>
          <Card className="srs-panel h-100">
            <Card.Body className="d-flex align-items-center gap-3">
              <Icon name={card.icon} size={28} />
              <div>
                <div className="text-muted small">{card.label}</div>
                <div className="fs-3 fw-bold" data-testid={card.key}>
                  {summary[card.key] ?? 0}
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      ))}
    </Row>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const shortcuts = (MENU_ITEMS_BY_ROLE[user.role] || []).slice(1);

  useEffect(() => {
    if (user.role === "student") {
      setSummary(null);
      return;
    }

    let active = true;
    const endpoint = user.role === "admin" ? "/admin/dashboard" : "/faculty/dashboard";

    setLoading(true);
    setError("");

    api
      .get(endpoint)
      .then((response) => {
        if (active) setSummary(response.data);
      })
      .catch((err) => {
        if (active) {
          setError(err.response?.data?.error || "Could not load dashboard summary.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [user.role]);

  return (
    <>
      <PageHeader title={TITLES[user.role]} description={`Welcome back, ${user.name}.`} />

      {user.role !== "student" && (
        <section aria-label="Dashboard summary">
          {loading && (
            <div className="mb-3" role="status">
              <Spinner animation="border" size="sm" />
              <span className="ms-2">Loading dashboard summary...</span>
            </div>
          )}

          {error && <Alert variant="danger">{error}</Alert>}

          {!loading && !error && summary && <SummaryCards summary={summary} role={user.role} />}
        </section>
      )}

      <div className="srs-shortcuts">
        {shortcuts.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className="srs-panel p-3 d-flex align-items-center gap-3 text-decoration-none text-reset"
          >
            <Icon name={item.icon} size={22} />
            <span className="fw-semibold">{item.label}</span>
          </Link>
        ))}
      </div>
    </>
  );
}
