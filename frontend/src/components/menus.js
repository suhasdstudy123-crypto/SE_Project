// Sidebar menu for each role. Pages not built yet show a "coming soon" note.
export const MENU_ITEMS_BY_ROLE = {
  admin: [
    { label: "Dashboard", path: "/admin", icon: "home" },
    { label: "Departments & Sections", path: "/admin/departments", icon: "building" },
    { label: "Students", path: "/admin/students", icon: "users" },
    { label: "Courses & Enrollment", path: "/admin/courses", icon: "book" },
    { label: "Fee Status", path: "/admin/fees", icon: "wallet" },
    { label: "ESA Window", path: "/admin/esa", icon: "calendar" },
    { label: "Audit Log", path: "/admin/audit", icon: "log" },
    { label: "Results", path: "/admin/results", icon: "chart" },
  ],
  faculty: [
    { label: "Dashboard", path: "/faculty", icon: "home" },
    { label: "My Courses", path: "/faculty/courses", icon: "book" },
    { label: "Mark Attendance", path: "/faculty/attendance", icon: "clipboard" },
    { label: "Enter Marks", path: "/faculty/marks", icon: "edit" },
    { label: "Course Analysis", path: "/faculty/reports", icon: "chart" },
    { label: "Results", path: "/faculty/results", icon: "chart" },
  ],
  student: [
    { label: "Dashboard", path: "/student", icon: "home" },
    { label: "My Courses", path: "/student/courses", icon: "book" },
    { label: "My Attendance", path: "/student/attendance", icon: "clipboard" },
    { label: "ESA Registration", path: "/student/esa", icon: "calendar" },
    { label: "My Results", path: "/student/results", icon: "chart" },
  ],
};

export const ROLE_LABELS = { admin: "Admin", faculty: "Faculty", student: "Student" };
