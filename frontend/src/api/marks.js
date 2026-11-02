import api from "./client.js";

// Faculty Marks API (Issue #15: SRS-F-019).

export async function getCourseMarks(courseId) {
  const response = await api.get(`/faculty/marks/${courseId}`);
  return response.data;
}

export async function saveStudentMarks(courseId, studentId, marksData) {
  const response = await api.put(`/faculty/marks/${courseId}/${studentId}`, marksData);
  return response.data;
}
