import api from "./client.js";

// Result analysis per course (SRS-F-022, issue #25).
// role is "admin", "faculty" or "student"; each has its own URL.
export async function getCourseAnalysis(role, courseId) {
  const response = await api.get(`/${role}/analysis/${courseId}`);
  return response.data;
}
