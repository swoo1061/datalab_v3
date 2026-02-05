window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";

window.globalSearchIndex = window.globalSearchIndex || { pages: [] };
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "시스템 로그", page: "system_logs" });
}

const state = {
  logs: [],
  total: 0,
  firewall: null,
  search: "",
  method: "all",
};

async function buildHeaders() {
  const headers = {};
  const key = await window.session?.getKey?.();
  if (key) headers["X-Sessionid"] = key;
  return headers;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function methodClass(method) {
  const m = String(method || "").toLowerCase();
  if (m === "post") return "post";
  if (m === "patch") return "patch";
  if (m === "delete") return "delete";
  return "";
}

async function fetchFirewallStatus() {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/dashboard/api/firewall-status/`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("firewall_fetch_failed");
  return res.json();
}

async function fetchAccessLogs(limit = 200, offset = 0) {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/dashboard/api/access-logs/?limit=${limit}&offset=${offset}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("logs_fetch_failed");
  return res.json();
}

function renderSummary() {
  const root = document.getElementById("logsSummary");
  if (!root) return;
  const rows = state.logs || [];
  const uniqueIps = new Set(rows.map((x) => x.ip_address || "")).size;
  const firewallLabel = (() => {
    const status = String(state.firewall?.status || "unknown").toLowerCase();
    if (status === "open") return "열림";
    if (status === "closed") return "닫힘";
    return "확인불가";
  })();
  root.innerHTML = `
    <div class="logs-chip"><span class="label">조회 로그</span><span class="value">${rows.length}</span></div>
    <div class="logs-chip"><span class="label">총 로그 수</span><span class="value">${Number(state.total || 0)}</span></div>
    <div class="logs-chip"><span class="label">고유 IP</span><span class="value">${uniqueIps}</span></div>
    <div class="logs-chip"><span class="label">방화벽 상태</span><span class="value">${firewallLabel}</span></div>
  `;
}

function filteredRows() {
  const q = state.search.toLowerCase();
  return (state.logs || []).filter((row) => {
    const methodOk = state.method === "all" || String(row.method || "").toUpperCase() === state.method;
    if (!methodOk) return false;
    if (!q) return true;
    const hay = `${row.ip_address || ""} ${row.path || ""} ${row.user_agent || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function renderTable() {
  const tbody = document.getElementById("logsTableBody");
  if (!tbody) return;
  const rows = filteredRows();
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">표시할 로그가 없습니다.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows
    .map((log) => `
      <tr>
        <td>${escapeHtml(log.created_at || "-")}</td>
        <td><code>${escapeHtml(log.ip_address || "-")}</code></td>
        <td><span class="logs-method ${methodClass(log.method)}">${escapeHtml(log.method || "-")}</span></td>
        <td class="logs-path">${escapeHtml(log.path || "-")}</td>
        <td class="logs-ua">${escapeHtml(log.user_agent || "-")}</td>
      </tr>
    `)
    .join("");
}

function bindEvents() {
  const refreshBtn = document.getElementById("logsRefreshBtn");
  const searchInput = document.getElementById("logsSearchInput");
  const methodFilter = document.getElementById("logsMethodFilter");

  refreshBtn?.addEventListener("click", async () => {
    await loadData();
    renderSummary();
    renderTable();
    window.showAlert?.("시스템 로그를 새로고침했습니다.");
  });

  searchInput?.addEventListener("input", () => {
    state.search = (searchInput.value || "").trim();
    renderTable();
  });

  methodFilter?.addEventListener("change", () => {
    state.method = methodFilter.value || "all";
    renderTable();
  });
}

async function loadData() {
  const [firewall, logs] = await Promise.all([
    fetchFirewallStatus().catch(() => null),
    fetchAccessLogs(200, 0).catch(() => null),
  ]);
  state.firewall = firewall;
  state.logs = Array.isArray(logs?.logs) ? logs.logs : [];
  state.total = Number(logs?.total || state.logs.length || 0);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  try {
    await loadData();
    renderSummary();
    renderTable();
  } catch (_e) {
    const tbody = document.getElementById("logsTableBody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="muted">로그를 불러오지 못했습니다.</td></tr>`;
  }
});
