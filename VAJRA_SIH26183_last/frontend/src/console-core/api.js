// VAJRA API client - React edition.
// Same exported function names/shapes as the old vanilla-JS api.js, so
// every ported view file (dashboard/trace/notices/etc.) works unchanged.
// Simplified: no offline-fixture "cached mode" branching - the console
// always talks to the real FastAPI backend now (matches "everything on
// the live site should be real" from earlier in the project).

const BASE = ""; // same-origin in production (FastAPI serves the built app); Vite proxies /api in dev

let _mode = "unknown"; // "live" | "offline"
let _token = null; // access token - memory only, never persisted (XSS-hardening)
let _refreshToken = sessionStorage.getItem("vajra_refresh") || null;
let _officer = JSON.parse(sessionStorage.getItem("vajra_officer") || "null");
let _lastResponseMs = null;
let _lastSyncAt = null;
let _refreshTimer = null;

export function getMode() { return _mode; }
export function getOfficer() { return _officer; }
export function getToken() { return _token; }
export function isAuthed() { return !!_refreshToken; } // can attempt silent restore even before _token is re-issued
export function getApiHealth() { return { responseMs: _lastResponseMs, lastSyncAt: _lastSyncAt, mode: _mode }; }

function _scheduleProactiveRefresh(expiresInSeconds) {
  if (_refreshTimer) clearTimeout(_refreshTimer);
  // Refresh 60s before expiry (or immediately if the token is short-lived) - // keeps a long-open console session from ever hitting a reactive 401.
  const delay = Math.max(5, (expiresInSeconds || 900) - 60) * 1000;
  _refreshTimer = setTimeout(() => { _tryRefresh(); }, delay);
}

export function setSession(token, officer, refreshToken = null, expiresIn = 900) {
  _token = token; _officer = officer;
  sessionStorage.setItem("vajra_officer", JSON.stringify(officer));
  if (refreshToken) { _refreshToken = refreshToken; sessionStorage.setItem("vajra_refresh", refreshToken); }
  _scheduleProactiveRefresh(expiresIn);
}
export function clearSession() {
  _token = null; _officer = null; _refreshToken = null;
  sessionStorage.removeItem("vajra_officer");
  sessionStorage.removeItem("vajra_refresh");
  if (_refreshTimer) clearTimeout(_refreshTimer);
}

let _refreshInFlight = null;
async function _tryRefresh() {
  if (!_refreshToken) return false;
  if (!_refreshInFlight) {
    _refreshInFlight = fetch(BASE + "/api/auth/refresh", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: _refreshToken }),
    }).then((r) => (r.ok ? r.json() : null)).catch(() => null).finally(() => { _refreshInFlight = null; });
  }
  const data = await _refreshInFlight;
  if (data && data.access_token) {
    _token = data.access_token;
    _scheduleProactiveRefresh(data.expires_in);
    return true;
  }
  clearSession();
  return false;
}

/** Attempts to restore a session on page load using the refresh token
 * left in sessionStorage - the access token itself is memory-only and
 * doesn't survive a reload, by design. */
export async function restoreSession() {
  if (!_refreshToken) return null;
  const ok = await _tryRefresh();
  return ok ? _officer : null;
}

async function _fetchJSON(path, opts = {}, _retried = false) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 8000);
  const started = performance.now();
  try {
    const res = await fetch(BASE + path, {
      ...opts,
      headers: { "Content-Type": "application/json", ..._token ? { Authorization: `Bearer ${_token}` } : {}, ...(opts.headers || {}) },
      signal: controller.signal,
    });
    clearTimeout(t);
    _lastResponseMs = Math.round(performance.now() - started);
    _lastSyncAt = new Date().toISOString();
    _mode = "live";
    if (res.status === 401 && !_retried && !path.startsWith("/api/auth/")) {
      const refreshed = await _tryRefresh();
      if (refreshed) return _fetchJSON(path, opts, true);
    }
    let body = null;
    try { body = await res.json(); } catch { /* no body */ }
    if (!res.ok) {
      const err = new Error((body && body.error && (body.error.error || body.error)) || (body && body.detail) || `HTTP ${res.status}`);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  } catch (e) {
    clearTimeout(t);
    if (e.name === "AbortError" || e instanceof TypeError) _mode = "offline";
    throw e;
  }
}

/** Pings the backend once at boot; sets live/offline banner state. */
export async function detectMode() {
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 2500);
    const res = await fetch(BASE + "/api/health", { signal: controller.signal });
    clearTimeout(t);
    _mode = res.ok ? "live" : "offline";
  } catch {
    _mode = "offline";
  }
  return _mode;
}

// ---------------------------------------------------------------- auth ----
export async function login(officerCode, password) {
  const data = await _fetchJSON("/api/auth/login", { method: "POST", body: JSON.stringify({ officer_code: officerCode, password }) });
  setSession(data.access_token, data.officer, data.refresh_token, data.expires_in);
  return data.officer;
}

export async function register({ name, officer_code, jurisdiction, password }) {
  const data = await _fetchJSON("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, officer_code, jurisdiction, password }),
  });
  setSession(data.access_token, data.officer, data.refresh_token, data.expires_in);
  return data.officer;
}

export async function logout() {
  try { await _fetchJSON("/api/auth/logout", { method: "POST" }); } catch { /* best-effort */ }
  clearSession();
}

// ----------------------------------------------------- citizen reporter ----
// Deliberately independent of the officer session above: a reporter's
// token must never leak into _token/officer session state (it has no
// case-list/trace visibility), so these two calls carry their own
// Authorization header rather than going through setSession().
export async function registerReporter({ name, contact, password }) {
  const data = await _fetchJSON("/api/auth/register-reporter", {
    method: "POST",
    body: JSON.stringify({ name, contact, password }),
  });
  return data; // { access_token, refresh_token, expires_in, reporter }
}

export async function submitPublicReport(reporterToken, { suspect_wallet, chain, typology, incident_timestamp }) {
  return _fetchJSON("/api/public/report", {
    method: "POST",
    headers: { Authorization: `Bearer ${reporterToken}` },
    body: JSON.stringify({ suspect_wallet, chain, typology, incident_timestamp }),
  });
}

// No auth at all - the reference number itself is the access control,
// same as a courier tracking number. See docstring on the backend route.
export async function trackPublicReport(ncrpRef) {
  return _fetchJSON(`/api/public/report/${encodeURIComponent(ncrpRef.trim().toUpperCase())}/status`);
}

// ------------------------------------------------- officer-side triage ----
export async function listUnassignedCases() {
  return (await _fetchJSON("/api/cases/unassigned")).cases;
}

export async function claimCase(caseId) {
  return _fetchJSON(`/api/cases/${caseId}/claim`, { method: "POST" });
}

// ---------------------------------------------------------------- cases ----
export async function listCases() {
  return (await _fetchJSON("/api/cases")).cases;
}

export async function createCase({ suspect_wallet, chain, typology }) {
  return _fetchJSON("/api/cases", {
    method: "POST",
    body: JSON.stringify({ suspect_wallet, chain, typology }),
  });
}

/**
 * Batch case intake from a CSV file - POST /api/cases/batch (multipart).
 * Deliberately bypasses _fetchJSON: that helper always sends
 * Content-Type: application/json, which would corrupt a multipart body
 * (the browser must set its own boundary-bearing Content-Type for
 * FormData). Everything else - auth header, 401 surfacing, error shape - * mirrors _fetchJSON's behavior so callers don't need two error-handling
 * paths.
 */
export async function createCasesBatch(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(BASE + "/api/cases/batch", {
    method: "POST",
    headers: _token ? { Authorization: `Bearer ${_token}` } : {},
    body: form,
  });
  let body = null;
  try { body = await res.json(); } catch { /* no body */ }
  if (!res.ok) {
    const err = new Error((body && body.detail) || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

export async function getStats() {
  return _fetchJSON("/api/stats");
}

export async function getPriorityQueue(limit = 5) {
  return (await _fetchJSON(`/api/cases/priority-queue?limit=${limit}`)).queue;
}

// ------------------------------------------------------------ officers/reassignment ----
export async function listOfficers() {
  return (await _fetchJSON("/api/officers")).officers;
}
export async function reassignCase(caseId, officerCode) {
  return _fetchJSON(`/api/cases/${encodeURIComponent(caseId)}/reassign`, {
    method: "POST",
    body: JSON.stringify({ officer_code: officerCode }),
  });
}

// ------------------------------------------------------------ threat intelligence ----
export async function getKnownEntities() {
  return _fetchJSON("/api/known-entities");
}

export async function getExchangeRiskBoard() {
  return (await _fetchJSON("/api/exchanges/risk-board")).exchanges;
}

export async function getSyndicates(scope) {
  return _fetchJSON(`/api/syndicates${scope ? `?scope=${encodeURIComponent(scope)}` : ""}`);
}

export async function getGeoDistribution(scope) {
  return _fetchJSON(`/api/cases/geo-distribution${scope ? `?scope=${encodeURIComponent(scope)}` : ""}`);
}

export async function getModelBenchmark() {
  return _fetchJSON("/api/model/benchmark");
}

export async function getCaseNetworkGraph() {
  return _fetchJSON("/api/cases/network");
}

export async function getCaseLinks(caseId) {
  return (await _fetchJSON(`/api/cases/${encodeURIComponent(caseId)}/network`)).linked_cases;
}

// ------------------------------------------------------------- real-time alerts ----
export function subscribeAlerts({ onAlert }) {
  if (_token) {
    const es = new EventSource(`${BASE}/api/alerts/stream?token=${encodeURIComponent(_token)}`);
    es.addEventListener("high_risk_case", (ev) => onAlert("high_risk_case", JSON.parse(ev.data)));
    es.addEventListener("exchange_match", (ev) => onAlert("exchange_match", JSON.parse(ev.data)));
    es.onerror = () => { /* browser EventSource auto-reconnects; nothing to do */ };
    return { cancel: () => es.close() };
  }
  return { cancel: () => {} };
}

export async function getCaseReport(caseId) {
  try {
    return await _fetchJSON(`/api/cases/${caseId}/report`);
  } catch (e) {
    if (e.status === 404) return null;
    throw e;
  }
}

/** Runs a trace with live SSE progress. onStage(stage, detail) fires per
 * pipeline stage; onResult(report) fires once with the final report. */
export function runTrace(caseId, { onStage, onError, onResult }) {
  const es = new EventSource(`${BASE}/api/trace/${caseId}/stream?token=${encodeURIComponent(_token || "")}`);
  es.addEventListener("stage", (ev) => onStage(JSON.parse(ev.data)));
  es.addEventListener("result", (ev) => { onResult(JSON.parse(ev.data)); es.close(); });
  es.addEventListener("error", (ev) => {
    es.close();
    let msg = "Trace failed - check the backend logs.";
    try { msg = JSON.parse(ev.data).error || msg; } catch { /* not a data-bearing error event */ }
    onError && onError(msg);
  });
  return { cancel: () => es.close() };
}

// ---------------------------------------------------------------- notices ----
export async function listNotices() {
  return (await _fetchJSON("/api/notices")).notices;
}
export async function draftNotice(caseId, noticeType) {
  return _fetchJSON("/api/notices", { method: "POST", body: JSON.stringify({ case_id: caseId, notice_type: noticeType }) });
}
export async function approveNotice(id) {
  return _fetchJSON(`/api/notices/${id}/approve`, { method: "POST" });
}
export async function sendNotice(id) {
  return _fetchJSON(`/api/notices/${id}/send`, { method: "POST" });
}

// ---------------------------------------------------------------- vault ----
export async function listVault() {
  return (await _fetchJSON("/api/vault")).reports;
}
export function vaultDownloadUrl(id) {
  return `${BASE}/api/vault/${id}/download?token=${encodeURIComponent(_token || "")}`;
}

// ---------------------------------------------------------------- audit ----
export async function listAudit(filters = {}) {
  const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
  const qs = params.toString();
  return (await _fetchJSON(`/api/audit-log${qs ? `?${qs}` : ""}`)).entries;
}

// ------------------------------------------------------------ evidence ----
export function evidencePdfUrl(caseId) {
  return `${BASE}/api/cases/${caseId}/evidence.pdf`;
}
export async function downloadEvidencePdf(caseId, filename) {
  const res = await fetch(evidencePdfUrl(caseId), {
    headers: _token ? { Authorization: `Bearer ${_token}` } : {},
  });
  if (!res.ok) throw new Error(`Evidence PDF unavailable (HTTP ${res.status}).`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename || "vajra-evidence.pdf";
  a.click();
}

// ------------------------------------------------------------ system ----
export async function getSystemStatus() {
  return _fetchJSON("/api/system/status");
}
