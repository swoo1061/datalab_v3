window.globalSearchIndex = window.globalSearchIndex || { pages: [] };
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "감사 로그", page: "audit_logs" });
}

const state = {
  rows: [],
  total: 0,
  page: 1,
  pageSize: 30,
  q: "",
  eventType: "",
  from: "",
  to: "",
  eventTypes: [],
};

const PERMISSION_KEY_LABELS = {
  attendance_requests_access: "근태 정정요청 접근",
  web_dashboard_access: "웹 대시보드 접근",
  vacation_admin_access: "휴가 관리 접근",
  employee_management_access: "직원 관리 접근",
  system_monitor_access: "서버 관리 접근",
};

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function permissionLabel(key) {
  return PERMISSION_KEY_LABELS[String(key || "")] || String(key || "-");
}

function boolLabel(value) {
  if (value === true) return "허용";
  if (value === false) return "차단";
  return String(value ?? "-");
}

function eventTypeLabel(row) {
  return row?.event_type_label || row?.event_type || "-";
}

function targetLabel(row) {
  const name = String(row?.target_name || "").trim();
  if (name) return name;
  const type = row?.target_type_label || row?.target_type || "-";
  const id = row?.target_id || "-";
  return `${type} #${id}`;
}

function toDateInputValue(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function summarizeChange(row) {
  const before = row?.before || {};
  const after = row?.after || {};
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  if (!keys.size) return "-";
  const parts = [];
  keys.forEach((k) => {
    if (before[k] === after[k]) return;
    const label = permissionLabel(k);
    parts.push(`${label}: ${boolLabel(before[k])} -> ${boolLabel(after[k])}`);
  });
  return parts.length ? parts.join(", ") : "-";
}

function renderTable() {
  const tbody = document.getElementById("auditTableBody");
  if (!tbody) return;
  if (!state.rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">표시할 로그가 없습니다.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.rows
    .map((row) => `
      <tr class="audit-row" data-id="${row.id}">
        <td>${escapeHtml(row.created_at || "-")}</td>
        <td>${escapeHtml(eventTypeLabel(row))}</td>
        <td>${escapeHtml(row.actor_name || row.actor_username || "system")}</td>
        <td>${escapeHtml(targetLabel(row))}</td>
        <td class="audit-summary">${escapeHtml(summarizeChange(row))}</td>
      </tr>
    `)
    .join("");
}

function renderPagination() {
  const info = document.getElementById("auditPageInfo");
  const prev = document.getElementById("auditPrevBtn");
  const next = document.getElementById("auditNextBtn");
  const pages = Math.max(1, Math.ceil((Number(state.total) || 0) / state.pageSize));
  if (info) info.textContent = `${state.page} / ${pages}`;
  if (prev) prev.disabled = state.page <= 1;
  if (next) next.disabled = state.page >= pages;
}

function renderEventTypeOptions() {
  const select = document.getElementById("auditEventType");
  if (!select) return;
  const selected = state.eventType;
  const options = ['<option value="">전체 이벤트</option>'];
  (state.eventTypes || []).forEach((x) => {
    const key = String(x?.key || "");
    const label = String(x?.label || key || "-");
    options.push(`<option value="${escapeHtml(key)}"${selected === key ? " selected" : ""}>${escapeHtml(label)}</option>`);
  });
  select.innerHTML = options.join("");
}

function openDetailModal(row) {
  const modal = document.getElementById("auditDetailModal");
  const body = document.getElementById("auditDetailBody");
  if (!modal || !body || !row) return;
  body.innerHTML = `
    <div class="audit-detail-row"><div class="k">시간</div><div class="v">${escapeHtml(row.created_at || "-")}</div></div>
    <div class="audit-detail-row"><div class="k">이벤트</div><div class="v">${escapeHtml(eventTypeLabel(row))}</div></div>
    <div class="audit-detail-row"><div class="k">작업자</div><div class="v">${escapeHtml(row.actor_name || row.actor_username || "system")}</div></div>
    <div class="audit-detail-row"><div class="k">대상</div><div class="v">${escapeHtml(targetLabel(row))}</div></div>
    <div class="audit-detail-row"><div class="k">Before</div><div class="v"><pre>${escapeHtml(JSON.stringify(row.before || {}, null, 2))}</pre></div></div>
    <div class="audit-detail-row"><div class="k">After</div><div class="v"><pre>${escapeHtml(JSON.stringify(row.after || {}, null, 2))}</pre></div></div>
    <div class="audit-detail-row"><div class="k">Metadata</div><div class="v"><pre>${escapeHtml(JSON.stringify(row.metadata || {}, null, 2))}</pre></div></div>
  `;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeDetailModal() {
  const modal = document.getElementById("auditDetailModal");
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

async function loadData() {
  const offset = (state.page - 1) * state.pageSize;
  const data = await window.api?.getAuditEvents?.({
    limit: state.pageSize,
    offset,
    q: state.q,
    event_type: state.eventType,
    from: state.from,
    to: state.to,
  });
  state.rows = Array.isArray(data?.results) ? data.results : [];
  state.total = Number(data?.total || state.rows.length || 0);
  state.eventTypes = Array.isArray(data?.event_types) ? data.event_types : [];
}

function bindEvents() {
  const refreshBtn = document.getElementById("auditRefreshBtn");
  const searchInput = document.getElementById("auditSearchInput");
  const eventType = document.getElementById("auditEventType");
  const fromDate = document.getElementById("auditFromDate");
  const toDate = document.getElementById("auditToDate");
  const applyBtn = document.getElementById("auditApplyBtn");
  const prevBtn = document.getElementById("auditPrevBtn");
  const nextBtn = document.getElementById("auditNextBtn");
  const tableBody = document.getElementById("auditTableBody");
  const modal = document.getElementById("auditDetailModal");
  const closeBtn = document.getElementById("auditModalCloseBtn");

  refreshBtn?.addEventListener("click", async () => {
    await loadData();
    renderTable();
    renderPagination();
    renderEventTypeOptions();
    window.showAlert?.("감사 로그를 새로고침했습니다.");
  });

  searchInput?.addEventListener("input", () => {
    state.q = (searchInput.value || "").trim();
  });

  eventType?.addEventListener("change", () => {
    state.eventType = eventType.value || "";
  });

  applyBtn?.addEventListener("click", async () => {
    state.from = (fromDate?.value || "").trim();
    state.to = (toDate?.value || "").trim();
    state.page = 1;
    await loadData();
    renderTable();
    renderPagination();
    renderEventTypeOptions();
  });

  prevBtn?.addEventListener("click", async () => {
    if (state.page <= 1) return;
    state.page -= 1;
    await loadData();
    renderTable();
    renderPagination();
  });

  nextBtn?.addEventListener("click", async () => {
    const pages = Math.max(1, Math.ceil((Number(state.total) || 0) / state.pageSize));
    if (state.page >= pages) return;
    state.page += 1;
    await loadData();
    renderTable();
    renderPagination();
  });

  tableBody?.addEventListener("click", (e) => {
    const tr = e.target?.closest?.("tr[data-id]");
    if (!tr) return;
    const row = state.rows.find((x) => Number(x.id) === Number(tr.dataset.id));
    if (row) openDetailModal(row);
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

document.addEventListener("DOMContentLoaded", async () => {
  const today = new Date();
  const from = new Date(today);
  from.setDate(from.getDate() - 6);
  state.from = toDateInputValue(from);
  state.to = toDateInputValue(today);
  const fromEl = document.getElementById("auditFromDate");
  const toEl = document.getElementById("auditToDate");
  if (fromEl) fromEl.value = state.from;
  if (toEl) toEl.value = state.to;

  bindEvents();
  try {
    await loadData();
    renderEventTypeOptions();
    renderTable();
    renderPagination();
  } catch (_e) {
    const tbody = document.getElementById("auditTableBody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="muted">감사 로그를 불러오지 못했습니다.</td></tr>`;
  }
});
