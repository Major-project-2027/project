/**
 * Phase 8 Dashboard -- API service layer.
 *
 * Every call in this file hits an *existing* Phase 2-8 backend endpoint.
 * No prediction/scoring logic lives here -- this module only fetches and
 * shapes JSON for the pages/components to render.
 */
const DEFAULT_BASE_URL = "";
const SETTINGS_KEY = "dashboard.settings.v1";

export function getSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return defaultSettings();
    return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch (err) {
    return defaultSettings();
  }
}

export function saveSettings(partial) {
  const merged = { ...getSettings(), ...partial };
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(merged));
  return merged;
}

function defaultSettings() {
  return {
    apiBaseUrl: DEFAULT_BASE_URL,
    theme: "dark",
    camera: "default",
    confidenceThreshold: 0.5,
    alertThreshold: 0.5,
    backend: "rule_based",
    loggingEnabled: true,
  };
}

function apiBase() {
  return getSettings().apiBaseUrl || DEFAULT_BASE_URL;
}

async function request(path, options = {}) {
  const url = `${apiBase()}${path}`;
  let response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkError) {
    throw new ApiError(`Could not reach ${url}: ${networkError.message}`, 0);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {
      /* response had no JSON body */
    }
    throw new ApiError(`${response.status} ${detail}`, response.status);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/csv")) return response.text();
  return response.json();
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function get(path) {
  return request(path, { method: "GET" });
}

function post(path, body) {
  return request(path, { method: "POST", body: JSON.stringify(body) });
}

// -- Phase 8 dashboard endpoints --------------------------------------------------
export const api = {
  getSummary: (range = "today") => get(`/dashboard/summary?range=${encodeURIComponent(range)}`),
  getTimeline: (metric, range = "today") =>
    get(`/dashboard/timeline/${encodeURIComponent(metric)}?range=${encodeURIComponent(range)}`),
  getStudents: ({ search = "", sortBy = "student_id", status = "" } = {}) => {
    const params = new URLSearchParams({ sort_by: sortBy });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    return get(`/dashboard/students?${params.toString()}`);
  },
  getAlerts: (range = "today", flag = "") => {
    const params = new URLSearchParams({ range });
    if (flag) params.set("flag", flag);
    return get(`/dashboard/alerts?${params.toString()}`);
  },
  getReport: (period, studentId = "") => {
    const params = studentId ? `?student_id=${encodeURIComponent(studentId)}` : "";
    return get(`/dashboard/reports/${encodeURIComponent(period)}${params}`);
  },
  exportCsvUrl: (range = "all") => `${apiBase()}/dashboard/reports/export/csv?range=${encodeURIComponent(range)}`,
  getConfig: () => get("/dashboard/config"),
  getHealth: () => get("/dashboard/health"),
  postEvent: (event) => post("/dashboard/events", event),

  // -- Phase 2-7 endpoints the dashboard reuses directly (read-only) ------------
  getCognitiveHealth: () => get("/cognitive/health"),
  getEngagementHealth: () => get("/engagement/health"),
};
