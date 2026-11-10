import axios from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";
import api from "./client.js";
import * as esaApi from "./esa.js";

afterEach(() => vi.restoreAllMocks());

// Record each request instead of sending it, and answer with `data`.
function fakeAdapter(data) {
  const sent = [];
  vi.spyOn(axios, "get").mockResolvedValue({ data: { csrf_token: "tok" } });
  api.defaults.adapter = async (config) => {
    sent.push({
      method: config.method,
      url: config.url,
      body: config.data ? JSON.parse(config.data) : undefined,
    });
    return { status: 200, data };
  };
  return sent;
}

describe("ESA API calls match the Flask routes (SAD 4.3.2)", () => {
  it.each([
    [() => esaApi.getEsaWindow(), "get", "/admin/esa-window", undefined],
    [() => esaApi.setEsaWindow(false), "put", "/admin/esa-window", { open: false }],
    [() => esaApi.getCourseEligibility(4), "get", "/admin/esa-eligibility/4", undefined],
    [
      () => esaApi.createOverride(1, 4, "Medical"),
      "post",
      "/admin/eligibility-override",
      { student_id: 1, course_id: 4, reason: "Medical" },
    ],
    [() => esaApi.getMyEsa(), "get", "/student/esa", undefined],
    [() => esaApi.registerEsa(4), "post", "/esa/register", { course_id: 4 }],
    [() => esaApi.dropEsa(4), "post", "/esa/drop", { course_id: 4 }],
  ])("%#: %s", async (call, method, url, body) => {
    const sent = fakeAdapter({ window: {}, override: {} });
    await call();
    expect(sent[0]).toEqual({ method, url, body });
  });
});
