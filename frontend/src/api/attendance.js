import api from "./client.js";

// Marking and correcting attendance (issue #13) and percentage/shortage (issue #14).

export async function getClassAttendance(courseId, date) {
  const response = await api.get(`/faculty/attendance/${courseId}`, { params: { date } });
  return response.data;
}

export async function saveClassAttendance(courseId, date, records) {
  const response = await api.put(`/faculty/attendance/${courseId}`, { date, records });
  return response.data;
}

export async function getStudentAttendance() {
  const response = await api.get("/student/attendance");
  return response.data;
}

export async function getStudentCourseAttendance(courseId) {
  const response = await api.get(`/student/attendance/${courseId}`);
  return response.data;
}
