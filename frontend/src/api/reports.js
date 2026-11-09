
import api from "./client";

// Download a CSV report using the authenticated API client.
export async function downloadReport(endpoint, filename) {
  const response = await api.get(endpoint, {
    responseType: "blob",
  });

  const url = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;

  document.body.appendChild(link);
  link.click();

  link.remove();
  window.URL.revokeObjectURL(url);
}
