import api from "./client.js";

// Faculty and Student Marks API (Issues #15 & #16: SRS-F-019, SRS-F-020).

export async function getCourseMarks(courseId) {
  const response = await api.get(`/faculty/marks/${courseId}`);
  return response.data;
}

export async function saveStudentMarks(courseId, studentId, marksData) {
  const response = await api.put(`/faculty/marks/${courseId}/${studentId}`, marksData);
  return response.data;
}

export async function getStudentResults() {
  const response = await api.get("/student/results");
  return response.data;
}
