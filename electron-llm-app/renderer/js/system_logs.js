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
  fromDate: "",
  toDate: "",
  rangePreset: "7d",
  page: 1,
  pageSize: 25,
  filtered: [],
  truncated: false,
};

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

function toDateInputValue(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function applyPresetRange(preset) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const from = new Date(today);
  if (preset === "today") {
    // keep today
  } else if (preset === "30d") {
    from.setDate(from.getDate() - 29);
  } else {
    from.setDate(from.getDate() - 6);
  }
  state.fromDate = toDateInputValue(from);
  state.toDate = toDateInputValue(today);
}

function parseLogTime(v) {
  if (!v) return null;
  const parsed = new Date(String(v).replace(" ", "T"));
  if (Number.isNaN(parsed.valueOf())) return null;
  return parsed;
}

function startOfDay(dateStr) {
  if (!dateStr) return null;
  const d = new Date(`${dateStr}T00:00:00`);
  return Number.isNaN(d.valueOf()) ? null : d;
}

function endOfDay(dateStr) {
  if (!dateStr) return null;
  const d = new Date(`${dateStr}T23:59:59`);
  return Number.isNaN(d.valueOf()) ? null : d;
}

function isDateInRange(dt, from, to) {
  if (!dt) return false;
  if (from && dt < from) return false;
  if (to && dt > to) return false;
  return true;
}

function renderSummary() {
  const root = document.getElementById("logsSummary");
  if (!root) return;
  const rows = state.filtered || [];
  const uniqueIps = new Set(rows.map((x) => x.ip_address || "")).size;
  const firewallLabel = (() => {
    const status = String(state.firewall?.status || "unknown").toLowerCase();
    if (status === "open") return "열림";
    if (status === "closed") return "닫힘";
    return "확인불가";
  })();
  root.innerHTML = `
    <div class="logs-chip"><span class="label">필터 결과</span><span class="value">${rows.length}</span></div>
    <div class="logs-chip"><span class="label">총 로그 수</span><span class="value">${Number(state.total || 0)}</span></div>
    <div class="logs-chip"><span class="label">고유 IP</span><span class="value">${uniqueIps}</span></div>
    <div class="logs-chip"><span class="label">방화벽 상태</span><span class="value">${firewallLabel}</span></div>
  `;
}

function applyFilters() {
  const q = state.search.toLowerCase();
  const from = startOfDay(state.fromDate);
  const to = endOfDay(state.toDate);
  state.filtered = (state.logs || []).filter((row) => {
    const methodOk = state.method === "all" || String(row.method || "").toUpperCase() === state.method;
    if (!methodOk) return false;
    const dt = parseLogTime(row.created_at);
    if (!isDateInRange(dt, from, to)) return false;
    if (!q) return true;
    const hay = `${row.ip_address || ""} ${row.path || ""} ${row.user_agent || ""} ${row.referer || ""}`.toLowerCase();
    return hay.includes(q);
  });
  const maxPage = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  if (state.page > maxPage) state.page = maxPage;
}

function pagedRows() {
  const start = (state.page - 1) * state.pageSize;
  return state.filtered.slice(start, start + state.pageSize);
}

function renderTable() {
  const tbody = document.getElementById("logsTableBody");
  if (!tbody) return;
  const rows = pagedRows();
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">표시할 로그가 없습니다.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows
    .map((log) => `
      <tr class="logs-row-clickable" data-log-id="${log.id}">
        <td>${escapeHtml(log.created_at || "-")}</td>
        <td><code>${escapeHtml(log.ip_address || "-")}</code></td>
        <td><span class="logs-method ${methodClass(log.method)}">${escapeHtml(log.method || "-")}</span></td>
        <td class="logs-path">${escapeHtml(log.path || "-")}</td>
        <td class="logs-ua">${escapeHtml(log.user_agent || "-")}</td>
      </tr>
    `)
    .join("");
}

function buildTopList(items, keyName) {
  if (!items.length) return `<div class="muted">데이터 없음</div>`;
  return items
    .map((x) => `
      <div class="logs-kv">
        <code>${escapeHtml(x[keyName] || "-")}</code>
        <strong>${x.count}</strong>
      </div>
    `)
    .join("");
}

function renderInsights() {
  const rows = state.filtered || [];
  const ipMap = new Map();
  const pathMap = new Map();
  const methodMap = new Map();
  for (const row of rows) {
    const ip = row.ip_address || "-";
    const path = row.path || "-";
    const method = String(row.method || "").toUpperCase();
    ipMap.set(ip, (ipMap.get(ip) || 0) + 1);
    pathMap.set(path, (pathMap.get(path) || 0) + 1);
    methodMap.set(method, (methodMap.get(method) || 0) + 1);
  }
  const topIps = [...ipMap.entries()].map(([ip_address, count]) => ({ ip_address, count })).sort((a, b) => b.count - a.count).slice(0, 5);
  const topPaths = [...pathMap.entries()].map(([path, count]) => ({ path, count })).sort((a, b) => b.count - a.count).slice(0, 5);

  const topIpsRoot = document.getElementById("logsTopIps");
  const topPathsRoot = document.getElementById("logsTopPaths");
  if (topIpsRoot) topIpsRoot.innerHTML = buildTopList(topIps, "ip_address");
  if (topPathsRoot) topPathsRoot.innerHTML = buildTopList(topPaths, "path");

  const anomaliesRoot = document.getElementById("logsAnomalies");
  if (!anomaliesRoot) return;

  const anomalies = [];
  if (topIps[0] && topIps[0].count >= 20) {
    anomalies.push({ level: "warn", message: `단일 IP (${topIps[0].ip_address}) 요청이 ${topIps[0].count}건으로 높습니다.` });
  }
  const mutatingCount = (methodMap.get("DELETE") || 0) + (methodMap.get("PATCH") || 0);
  if (mutatingCount >= 10) {
    anomalies.push({ level: "warn", message: `변경성 메서드(DELETE/PATCH) 요청이 ${mutatingCount}건입니다.` });
  }
  if (state.truncated) {
    anomalies.push({ level: "info", message: "로그가 많아 최근 일부만 분석했습니다. 더 정밀한 분석은 서버 필터 API 확장을 권장합니다." });
  }

  if (!anomalies.length) {
    anomaliesRoot.innerHTML = "";
    return;
  }
  anomaliesRoot.innerHTML = anomalies
    .map((a) => `<div class="logs-alert ${a.level === "info" ? "info" : ""}">${escapeHtml(a.message)}</div>`)
    .join("");
}

function renderPagination() {
  const info = document.getElementById("logsPageInfo");
  const prev = document.getElementById("logsPrevBtn");
  const next = document.getElementById("logsNextBtn");
  const totalPages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  if (info) info.textContent = `${state.page} / ${totalPages}`;
  if (prev) prev.disabled = state.page <= 1;
  if (next) next.disabled = state.page >= totalPages;
}

function getLogById(logId) {
  return (state.logs || []).find((x) => Number(x.id) === Number(logId)) || null;
}

function openDetailModal(log) {
  const modal = document.getElementById("logsDetailModal");
  const body = document.getElementById("logsDetailBody");
  if (!modal || !body || !log) return;
  body.innerHTML = `
    <div class="logs-detail-row"><div class="k">시간</div><div class="v">${escapeHtml(log.created_at || "-")}</div></div>
    <div class="logs-detail-row"><div class="k">IP</div><div class="v"><code>${escapeHtml(log.ip_address || "-")}</code></div></div>
    <div class="logs-detail-row"><div class="k">메서드</div><div class="v">${escapeHtml(log.method || "-")}</div></div>
    <div class="logs-detail-row"><div class="k">경로</div><div class="v"><code>${escapeHtml(log.path || "-")}</code></div></div>
    <div class="logs-detail-row"><div class="k">Referer</div><div class="v">${escapeHtml(log.referer || "-")}</div></div>
    <div class="logs-detail-row"><div class="k">User Agent</div><div class="v">${escapeHtml(log.user_agent || "-")}</div></div>
  `;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeDetailModal() {
  const modal = document.getElementById("logsDetailModal");
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function toCsvValue(v) {
  const s = String(v ?? "");
  if (s.includes(",") || s.includes("\"") || s.includes("\n")) {
    return `"${s.replaceAll("\"", "\"\"")}"`;
  }
  return s;
}

function exportCsv() {
  const rows = state.filtered || [];
  if (!rows.length) {
    window.showAlert?.("내보낼 로그가 없습니다.");
    return;
  }
  const header = ["created_at", "ip_address", "method", "path", "referer", "user_agent"];
  const lines = [header.join(",")];
  for (const row of rows) {
    lines.push(
      [
        toCsvValue(row.created_at),
        toCsvValue(row.ip_address),
        toCsvValue(row.method),
        toCsvValue(row.path),
        toCsvValue(row.referer),
        toCsvValue(row.user_agent),
      ].join(",")
    );
  }
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  const now = new Date();
  const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
  a.href = URL.createObjectURL(blob);
  a.download = `system_logs_${stamp}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function syncDateInputs() {
  const fromEl = document.getElementById("logsFromDate");
  const toEl = document.getElementById("logsToDate");
  if (fromEl) fromEl.value = state.fromDate;
  if (toEl) toEl.value = state.toDate;
}

function rerenderAll() {
  applyFilters();
  renderSummary();
  renderInsights();
  renderTable();
  renderPagination();
}

function bindEvents() {
  const refreshBtn = document.getElementById("logsRefreshBtn");
  const exportBtn = document.getElementById("logsExportBtn");
  const searchInput = document.getElementById("logsSearchInput");
  const methodFilter = document.getElementById("logsMethodFilter");
  const rangePreset = document.getElementById("logsRangePreset");
  const fromDate = document.getElementById("logsFromDate");
  const toDate = document.getElementById("logsToDate");
  const applyRangeBtn = document.getElementById("logsApplyRangeBtn");
  const prevBtn = document.getElementById("logsPrevBtn");
  const nextBtn = document.getElementById("logsNextBtn");
  const tableBody = document.getElementById("logsTableBody");
  const modal = document.getElementById("logsDetailModal");
  const closeBtn = document.getElementById("logsModalCloseBtn");

  refreshBtn?.addEventListener("click", async () => {
    await loadData();
    rerenderAll();
    window.showAlert?.("시스템 로그를 새로고침했습니다.");
  });

  exportBtn?.addEventListener("click", exportCsv);

  searchInput?.addEventListener("input", () => {
    state.search = (searchInput.value || "").trim();
    state.page = 1;
    rerenderAll();
  });

  methodFilter?.addEventListener("change", () => {
    state.method = methodFilter.value || "all";
    state.page = 1;
    rerenderAll();
  });

  rangePreset?.addEventListener("change", () => {
    state.rangePreset = rangePreset.value || "7d";
    if (state.rangePreset !== "custom") {
      applyPresetRange(state.rangePreset);
      syncDateInputs();
      state.page = 1;
      rerenderAll();
    }
  });

  applyRangeBtn?.addEventListener("click", () => {
    state.fromDate = (fromDate?.value || "").trim();
    state.toDate = (toDate?.value || "").trim();
    state.rangePreset = "custom";
    if (rangePreset) rangePreset.value = "custom";
    state.page = 1;
    rerenderAll();
  });

  prevBtn?.addEventListener("click", () => {
    if (state.page <= 1) return;
    state.page -= 1;
    renderTable();
    renderPagination();
  });

  nextBtn?.addEventListener("click", () => {
    const maxPage = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
    if (state.page >= maxPage) return;
    state.page += 1;
    renderTable();
    renderPagination();
  });

  tableBody?.addEventListener("click", (e) => {
    const tr = e.target?.closest?.("tr[data-log-id]");
    if (!tr) return;
    const log = getLogById(tr.dataset.logId);
    if (log) openDetailModal(log);
  });

  modal?.addEventListener("click", (e) => {
    const target = e.target;
    if (target && target.getAttribute && target.getAttribute("data-close") === "1") {
      closeDetailModal();
    }
  });
  closeBtn?.addEventListener("click", closeDetailModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetailModal();
  });
}

async function loadData() {
  const batchSize = 200;
  const maxRows = 2000;
  let offset = 0;
  let total = 0;
  let firewall = null;
  const rows = [];

  while (offset < maxRows) {
    const data = await window.api?.getSystemLogsData?.(batchSize, offset);
    if (!firewall) firewall = data?.firewall || null;
    const chunk = Array.isArray(data?.logs?.logs) ? data.logs.logs : [];
    total = Number(data?.logs?.total || total || 0);
    rows.push(...chunk);
    if (!chunk.length) break;
    offset += chunk.length;
    if (offset >= total) break;
  }

  state.firewall = firewall;
  state.logs = rows;
  state.total = total || rows.length;
  state.truncated = state.total > rows.length;
}

document.addEventListener("DOMContentLoaded", async () => {
  applyPresetRange(state.rangePreset);
  syncDateInputs();
  bindEvents();
  try {
    await loadData();
    rerenderAll();
  } catch (_e) {
    const tbody = document.getElementById("logsTableBody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="muted">로그를 불러오지 못했습니다.</td></tr>`;
  }
});
