import api from "./client.js";

// ESA window, registration, eligibility and overrides (cards #17-#20).

export async function getEsaWindow() {
  return (await api.get("/admin/esa-window")).data.window;
}

export async function setEsaWindow(open) {
  return (await api.put("/admin/esa-window", { open })).data.window;
}

export async function getCourseEligibility(courseId) {
  return (await api.get(`/admin/esa-eligibility/${courseId}`)).data;
}

export async function createOverride(studentId, courseId, reason) {
  const body = { student_id: studentId, course_id: courseId, reason };
  return (await api.post("/admin/eligibility-override", body)).data.override;
}

export async function getMyEsa() {
  return (await api.get("/student/esa")).data;
}

export async function registerEsa(courseId) {
  return (await api.post("/esa/register", { course_id: courseId })).data;
}

export async function dropEsa(courseId) {
  return (await api.post("/esa/drop", { course_id: courseId })).data;
}
