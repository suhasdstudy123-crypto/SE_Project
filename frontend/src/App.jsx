import ResultsExportPage from "./pages/ResultsExportPage.jsx";
import { Container, Spinner } from "react-bootstrap";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout.jsx";
import RequireRole from "./components/RequireRole.jsx";
import { HOME_BY_ROLE, useAuth } from "./auth/authContext.js";
import ComingSoonPage from "./pages/ComingSoonPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import MyCoursesPage from "./pages/MyCoursesPage.jsx";
import AuditPage from "./pages/admin/AuditPage.jsx";
import CoursesPage from "./pages/admin/CoursesPage.jsx";
import DepartmentsPage from "./pages/admin/DepartmentsPage.jsx";
import EsaWindowPage from "./pages/admin/EsaWindowPage.jsx";
import FeesPage from "./pages/admin/FeesPage.jsx";
import StudentsPage from "./pages/admin/StudentsPage.jsx";
import AttendancePage from "./pages/faculty/AttendancePage.jsx";
import MarksPage from "./pages/faculty/MarksPage.jsx";
import EsaRegistrationPage from "./pages/student/EsaRegistrationPage.jsx";
import StudentAttendancePage from "./pages/student/StudentAttendancePage.jsx";
import StudentResultsPage from "./pages/student/StudentResultsPage.jsx";

// Pages for each role. Add your card's page here (replace its ComingSoonPage).
const PAGES_BY_ROLE = {
  admin: [
    ["departments", <DepartmentsPage key="departments" />],
    ["students", <StudentsPage key="students" />],
    ["fees", <FeesPage key="fees" />],
    ["courses", <CoursesPage key="courses" />],
    ["esa", <EsaWindowPage key="esa" />],
    ["audit", <AuditPage key="audit" />],
    ["results", <ResultsExportPage key="results" role="admin" />],
  ],
  faculty: [
    ["courses", <MyCoursesPage key="courses" />],
    ["attendance", <AttendancePage key="attendance" />],
    ["marks", <MarksPage key="marks" />],
    ["reports", <ComingSoonPage key="reports" title="Course Analysis" card={25} />],
    ["results", <ResultsExportPage key="results" role="faculty" />],
  ],
  student: [
    ["courses", <MyCoursesPage key="courses" />],
    ["attendance", <StudentAttendancePage key="attendance" />],
    ["esa", <EsaRegistrationPage key="esa" />],
    ["results", <StudentResultsPage key="results" />],
  ],
};

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <Container className="py-5 text-center">
        <Spinner animation="border" role="status" aria-label="Loading" />
      </Container>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {Object.entries(HOME_BY_ROLE).map(([role, path]) => (
        <Route
          key={role}
          path={path}
          element={
            <RequireRole role={role}>
              <AppLayout />
            </RequireRole>
          }
        >
          <Route index element={<HomePage />} />
          {PAGES_BY_ROLE[role].map(([subPath, element]) => (
            <Route key={subPath} path={subPath} element={element} />
          ))}
          <Route path="*" element={<Navigate to={path} replace />} />
        </Route>
      ))}
      <Route
        path="*"
        element={<Navigate to={user ? HOME_BY_ROLE[user.role] : "/login"} replace />}
      />
    </Routes>
  );
}
