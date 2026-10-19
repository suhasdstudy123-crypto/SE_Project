import api from "./client.js";

// Departments & sections (card #8)
export async function listDepartments() {
  return (await api.get("/departments")).data.departments;
}
export async function createDepartment(name) {
  return (await api.post("/departments", { name })).data.department;
}
export async function deleteDepartment(id) {
  await api.delete(`/departments/${id}`);
}
export async function createSection(departmentId, name) {
  return (await api.post(`/departments/${departmentId}/sections`, { name })).data.section;
}
export async function deleteSection(id) {
  await api.delete(`/departments/sections/${id}`);
}

// Students (card #9)
export async function listStudents() {
  return (await api.get("/admin/students")).data.students;
}
export async function createStudent(student) {
  return (await api.post("/admin/students", student)).data.student;
}
export async function updateStudent(id, student) {
  return (await api.put(`/admin/students/${id}`, student)).data.student;
}
export async function deleteStudent(id) {
  await api.delete(`/admin/students/${id}`);
}

// Fee status (card #10)
export async function listFees(semester) {
  return (await api.get("/admin/fees", { params: { semester } })).data.fees;
}
export async function setFee(studentId, semester, status) {
  return (await api.put(`/admin/fees/${studentId}`, { semester, status })).data.fee;
}

// Audit log (card #6)
export async function listAuditLogs(params) {
  return (await api.get("/admin/audit-log", { params })).data.audit_log;
}
