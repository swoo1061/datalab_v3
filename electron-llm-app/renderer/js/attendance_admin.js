window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";

window.globalSearchIndex = window.globalSearchIndex || { pages: [] };
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "직원 출퇴근 관리", page: "attendance_admin" });
}

const state = {
  tab: "monthly",
  month: "",
  q: "",
  status: "all",
  selectedUserId: null,
  rows: [],
  users: [],
  summary: { worked_days: 0, total_minutes: 0 },
  users_count: 0,
  corrections: [],
};

async function buildHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
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

function roleLabel(role) {
  const map = { admin: "ADMIN", ceo: "CEO", leader: "LEADER", manager: "MANAGER" };
  const key = String(role || "").toLowerCase();
  return map[key] || (key ? key.toUpperCase() : "-");
}

function statusLabel(status) {
  if (status === "working") return "근무중";
  if (status === "completed") return "퇴근";
  if (status === "pending") return "대기";
  if (status === "approved") return "승인";
  if (status === "rejected") return "반려";
  if (status === "vacation_annual") return "연차";
  if (status === "vacation_half_am") return "오전반차";
  if (status === "vacation_half_pm") return "오후반차";
  return "-";
}

function isVacationStatus(status) {
  return String(status || "").startsWith("vacation_");
}

function vacationTypeLabel(type) {
  if (type === "annual") return "연차";
  if (type === "half_am") return "오전반차";
  if (type === "half_pm") return "오후반차";
  return "";
}

function vacationTypeClass(type) {
  return type ? `vacation_${type}` : "";
}

function formatDateTime(raw) {
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(raw) {
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatMinutes(total) {
  const mins = Number(total) || 0;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}시간 ${m}분`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function escapeCsv(value) {
  const s = String(value ?? "");
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replaceAll('"', '""')}"`;
  }
  return s;
}

function exportCsv() {
  const month = state.month || "month";
  const rows = state.tab === "monthly" ? state.rows : state.corrections;
  if (!rows.length) {
    window.showAlert?.("다운로드할 데이터가 없습니다.");
    return;
  }
  const header = state.tab === "monthly"
    ? ["날짜", "직원", "직급", "출근", "퇴근", "근무시간(분)", "상태"]
    : ["상태", "대상일", "직원", "현재 출근", "현재 퇴근", "요청 출근", "요청 퇴근", "사유"];
  const body = state.tab === "monthly"
    ? rows.map((r) => [
        r.work_date || "",
        r.user_name || "",
        roleLabel(r.role),
        isVacationStatus(r.status) ? statusLabel(r.status) : formatDateTime(r.check_in_at),
        isVacationStatus(r.status) ? statusLabel(r.status) : formatDateTime(r.check_out_at),
        Number(r.worked_minutes || 0),
        r.vacation_type ? vacationTypeLabel(r.vacation_type) : statusLabel(r.status),
      ])
    : rows.map((r) => [
        statusLabel(r.status),
        r.work_date || "",
        r.user_name || "",
        formatDateTime(r.current_check_in_at),
        formatDateTime(r.current_check_out_at),
        formatDateTime(r.requested_check_in_at),
        formatDateTime(r.requested_check_out_at),
        r.reason || "",
      ]);
  const csv = [header, ...body].map((line) => line.map(escapeCsv).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, `attendance_${state.tab}_${month}.csv`);
}

function exportExcel() {
  const XLSX = window.XLSX;
  if (!XLSX) {
    window.showAlert?.("엑셀 모듈을 찾을 수 없습니다.");
    return;
  }

  const month = state.month || "month";
  const rows = state.tab === "monthly" ? state.rows : state.corrections;
  if (!rows.length) {
    window.showAlert?.("다운로드할 데이터가 없습니다.");
    return;
  }
  const header = state.tab === "monthly"
    ? ["날짜", "직원", "직급", "출근", "퇴근", "근무시간(분)", "상태"]
    : ["상태", "대상일", "직원", "현재 출근", "현재 퇴근", "요청 출근", "요청 퇴근", "사유"];
  const body = state.tab === "monthly"
    ? rows.map((r) => [
        r.work_date || "",
        r.user_name || "",
        roleLabel(r.role),
        isVacationStatus(r.status) ? statusLabel(r.status) : formatDateTime(r.check_in_at),
        isVacationStatus(r.status) ? statusLabel(r.status) : formatDateTime(r.check_out_at),
        Number(r.worked_minutes || 0),
        r.vacation_type ? vacationTypeLabel(r.vacation_type) : statusLabel(r.status),
      ])
    : rows.map((r) => [
        statusLabel(r.status),
        r.work_date || "",
        r.user_name || "",
        formatDateTime(r.current_check_in_at),
        formatDateTime(r.current_check_out_at),
        formatDateTime(r.requested_check_in_at),
        formatDateTime(r.requested_check_out_at),
        r.reason || "",
      ]);
  const ws = XLSX.utils.aoa_to_sheet([header, ...body]);
  ws["!cols"] = header.map(() => ({ wch: 18 }));
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, state.tab === "monthly" ? "월별기록" : "정정요청");
  XLSX.writeFile(wb, `attendance_${state.tab}_${month}.xlsx`, { compression: true });
}

function buildUserTotals(rows) {
  const map = new Map();
  (rows || []).forEach((row) => {
    const uid = Number(row?.user_id || 0);
    if (!uid) return;
    if (!map.has(uid)) map.set(uid, { days: 0, minutes: 0 });
    const cur = map.get(uid);
    if (row?.check_in_at) cur.days += 1;
    cur.minutes += Number(row?.worked_minutes || 0);
  });
  return map;
}

function monthRange(monthKey) {
  const [y, m] = String(monthKey || "").split("-").map(Number);
  if (!y || !m) return [];
  const last = new Date(y, m, 0).getDate();
  const days = [];
  for (let d = 1; d <= last; d += 1) {
    const date = new Date(y, m - 1, d);
    days.push({
      key: `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
      day: d,
      weekday: date.getDay(),
    });
  }
  return days;
}

async function fetchMonthlyRows() {
  const headers = await buildHeaders();
  const params = new URLSearchParams({
    month: state.month,
    status: state.status,
  });
  if (state.q) params.set("q", state.q);
  const res = await fetch(`${window.API_BASE}/api/data/attendance/admin/records/?${params.toString()}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("attendance_admin_fetch_failed");
  return res.json();
}

async function fetchCorrections() {
  const headers = await buildHeaders();
  const params = new URLSearchParams({
    month: state.month,
    status: "pending",
  });
  if (state.q) params.set("q", state.q);
  const res = await fetch(`${window.API_BASE}/api/data/attendance/admin/corrections/?${params.toString()}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("attendance_corrections_fetch_failed");
  return res.json();
}

async function patchCorrection(correctionId, action, reviewNote) {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/attendance/admin/corrections/${correctionId}/`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ action, review_note: reviewNote || "" }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = String(data?.message || "attendance_correction_patch_failed");
    throw new Error(msg);
  }
  return data;
}

function renderSummary() {
  const root = document.getElementById("attendanceSummary");
  if (!root) return;
  if (state.tab === "monthly") {
    const totalsByUser = buildUserTotals(state.rows);
    const selectedUser = state.users.find((u) => Number(u.user_id) === Number(state.selectedUserId));
    const selectedTotals = selectedUser ? totalsByUser.get(Number(selectedUser.user_id || 0)) : null;
    root.innerHTML = `
      <div class="attendance-chip"><span class="label">직원 수</span><span class="value">${Number(state.users_count || 0)}명</span></div>
      <div class="attendance-chip"><span class="label">총 근무일</span><span class="value">${selectedUser ? `${Number(selectedTotals?.days || 0)}일` : "-"}</span></div>
      <div class="attendance-chip">
        <span class="label">총 근무시간</span>
        <span class="value">${selectedUser ? formatMinutes(selectedTotals?.minutes || 0) : "-"}</span>
      </div>
    `;
    root.style.gridTemplateColumns = "repeat(3, minmax(0, 1fr))";
    return;
  }
  const pending = (state.corrections || []).filter((x) => x.status === "pending").length;
  root.innerHTML = `
    <div class="attendance-chip"><span class="label">정정요청 건수</span><span class="value">${state.corrections.length}</span></div>
    <div class="attendance-chip"><span class="label">대기</span><span class="value">${pending}</span></div>
    <div class="attendance-chip"><span class="label">조회 월</span><span class="value">${escapeHtml(state.month)}</span></div>
    <div class="attendance-chip">
      <span class="label">필터</span>
      <span class="value">${escapeHtml(state.q || "전체")}</span>
    </div>
  `;
  root.style.gridTemplateColumns = "repeat(4, minmax(0, 1fr))";
}

function renderTabs() {
  document.querySelectorAll(".attendance-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === state.tab);
  });
  document.getElementById("monthlyPanel")?.classList.toggle("hidden", state.tab !== "monthly");
  document.getElementById("correctionsPanel")?.classList.toggle("hidden", state.tab !== "corrections");
  renderSummary();
}

function renderMonthlyMatrix() {
  const head = document.getElementById("attendanceMatrixHead");
  const body = document.getElementById("attendanceMatrixBody");
  if (!head || !body) return;

  const days = monthRange(state.month);
  const grouped = new Map();
  state.rows.forEach((row) => {
    const key = `${row.user_id}::${row.work_date}`;
    grouped.set(key, row);
  });

  head.innerHTML = `
    <tr>
      <th>직원</th>
      ${days
        .map((d) => {
          const weekend = d.weekday === 0 || d.weekday === 6 ? "weekend" : "";
          const wMap = ["일", "월", "화", "수", "목", "금", "토"];
          return `<th><div class="day-head ${weekend}"><span class="weekday">${wMap[d.weekday]}</span><span class="daynum">${d.day}</span></div></th>`;
        })
        .join("")}
    </tr>
  `;

  if (!state.users.length) {
    body.innerHTML = `<tr><td class="muted">표시할 직원이 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = state.users
    .map((u) => {
      const cells = days
        .map((d) => {
          const row = grouped.get(`${u.user_id}::${d.key}`);
          if (!row) return `<td><span class="cell-empty">-</span></td>`;
          if (isVacationStatus(row.status)) {
            const label = statusLabel(row.status);
            return `
              <td>
                <span class="status-dot ${escapeHtml(row.status || "")}">${escapeHtml(label)}</span>
              </td>
            `;
          }
          if (row.vacation_type) {
            const label = vacationTypeLabel(row.vacation_type);
            const cls = vacationTypeClass(row.vacation_type);
            return `
              <td>
                <span class="cell-time ${row.check_in_at ? "" : "muted"}">${escapeHtml(formatTime(row.check_in_at))}</span>
                <span class="cell-time ${row.check_out_at ? "" : "muted"}">${escapeHtml(formatTime(row.check_out_at))}</span>
                <span class="status-dot ${escapeHtml(cls)}">${escapeHtml(label)}</span>
              </td>
            `;
          }
          return `
            <td>
              <span class="cell-time ${row.check_in_at ? "" : "muted"}">${escapeHtml(formatTime(row.check_in_at))}</span>
              <span class="cell-time ${row.check_out_at ? "" : "muted"}">${escapeHtml(formatTime(row.check_out_at))}</span>
              <span class="status-dot ${escapeHtml(row.status || "")}">${escapeHtml(statusLabel(row.status))}</span>
            </td>
          `;
        })
        .join("");
      return `
        <tr>
          <td class="user-cell ${Number(state.selectedUserId) === Number(u.user_id) ? "selected" : ""}" data-user-id="${u.user_id}">
            <div class="name">${escapeHtml(u.user_name || "-")}</div>
            <div class="meta">${escapeHtml(roleLabel(u.role))}</div>
          </td>
          ${cells}
        </tr>
      `;
    })
    .join("");
}

function renderCorrections() {
  const tbody = document.getElementById("attendanceCorrectionsBody");
  if (!tbody) return;
  if (!state.corrections.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="muted">정정요청이 없습니다.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.corrections
    .map((row) => `
      <tr data-id="${row.id}">
        <td><span class="status-badge ${escapeHtml(row.status || "")}">${escapeHtml(statusLabel(row.status))}</span></td>
        <td>${escapeHtml(row.work_date || "-")}</td>
        <td>${escapeHtml(row.user_name || "-")}</td>
        <td class="correction-times">${escapeHtml(formatDateTime(row.current_check_in_at))}<br />${escapeHtml(formatDateTime(row.current_check_out_at))}</td>
        <td class="correction-times">${escapeHtml(formatDateTime(row.requested_check_in_at))}<br />${escapeHtml(formatDateTime(row.requested_check_out_at))}</td>
        <td class="correction-reason">${escapeHtml(row.reason || "-")}</td>
        <td>
          <div class="correction-actions">
            <button type="button" class="btn-xs approve" data-action="approve">승인</button>
            <button type="button" class="btn-xs reject" data-action="reject">반려</button>
          </div>
        </td>
      </tr>
    `)
    .join("");
}

async function refreshData() {
  const [monthly, corrections] = await Promise.all([fetchMonthlyRows(), fetchCorrections()]);
  state.rows = monthly?.results || [];
  state.users = (monthly?.users || []).slice().sort((a, b) =>
    String(a?.user_name || "").localeCompare(String(b?.user_name || ""), "ko")
  );
  state.summary = monthly?.summary || { worked_days: 0, total_minutes: 0 };
  state.users_count = monthly?.users_count || 0;
  state.corrections = (corrections?.results || []).slice().sort((a, b) =>
    String(a?.user_name || "").localeCompare(String(b?.user_name || ""), "ko")
  );
  if (state.selectedUserId && !state.users.some((u) => Number(u.user_id) === Number(state.selectedUserId))) {
    state.selectedUserId = null;
  }
  renderSummary();
  renderMonthlyMatrix();
  renderCorrections();
}

function bindEvents() {
  const monthInput = document.getElementById("attendanceMonthInput");
  const searchInput = document.getElementById("attendanceSearchInput");
  const statusFilter = document.getElementById("attendanceStatusFilter");
  const refreshBtn = document.getElementById("attendanceRefreshBtn");
  const correctionsBody = document.getElementById("attendanceCorrectionsBody");
  const matrixBody = document.getElementById("attendanceMatrixBody");
  const csvBtn = document.getElementById("attendanceCsvBtn");
  const excelBtn = document.getElementById("attendanceExcelBtn");

  document.querySelectorAll(".attendance-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.tab || "monthly";
      renderTabs();
    });
  });

  monthInput?.addEventListener("change", async () => {
    state.month = monthInput.value || state.month;
    await refreshData();
  });

  searchInput?.addEventListener("input", async () => {
    state.q = (searchInput.value || "").trim();
    await refreshData();
  });

  statusFilter?.addEventListener("change", async () => {
    state.status = statusFilter.value || "all";
    await refreshData();
  });

  refreshBtn?.addEventListener("click", async () => {
    await refreshData();
    window.showAlert?.("출퇴근 데이터를 새로고침했습니다.");
  });

  csvBtn?.addEventListener("click", exportCsv);
  excelBtn?.addEventListener("click", exportExcel);

  matrixBody?.addEventListener("click", (e) => {
    const userCell = e.target?.closest?.(".user-cell[data-user-id]");
    if (!userCell) return;
    const uid = Number(userCell.dataset.userId || 0);
    if (!uid) return;
    state.selectedUserId = uid;
    renderSummary();
    renderMonthlyMatrix();
  });

  correctionsBody?.addEventListener("click", async (e) => {
    if (!(e.target instanceof Element)) return;
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const tr = btn.closest("tr[data-id]");
    const correctionId = Number(tr?.dataset?.id || 0);
    const action = btn.dataset.action || "";
    if (!correctionId || !action) return;

    const isApprove = action === "approve";
    const ok = typeof window.appConfirm === "function"
      ? await window.appConfirm(isApprove ? "이 정정요청을 승인할까요?" : "이 정정요청을 반려할까요?")
      : (window.confirm?.(isApprove ? "이 정정요청을 승인할까요?" : "이 정정요청을 반려할까요?") ?? true);
    if (!ok) return;

    const note = "";
    btn.disabled = true;
    try {
      await patchCorrection(correctionId, action, note);
      await refreshData();
      window.showAlert?.(isApprove ? "정정요청을 승인했습니다." : "정정요청을 반려했습니다.");
    } catch (err) {
      const msg = String(err?.message || "");
      if (msg === "forbidden") {
        window.showAlert?.("권한이 없습니다.");
      } else if (msg === "not_found") {
        window.showAlert?.("요청 건을 찾을 수 없습니다.");
      } else if (msg === "invalid_action") {
        window.showAlert?.("처리 방식이 올바르지 않습니다.");
      } else {
        window.showAlert?.("처리에 실패했습니다.");
      }
    } finally {
      btn.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const now = new Date();
  state.month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const monthInput = document.getElementById("attendanceMonthInput");
  if (monthInput) monthInput.value = state.month;

  try {
    const openType = (sessionStorage.getItem("openNotifyType") || "").trim();
    if (openType === "attendance") state.tab = "corrections";
    sessionStorage.removeItem("openNotifyId");
    sessionStorage.removeItem("openNotifyType");
    sessionStorage.removeItem("openNotifyDate");
  } catch (_e) {
    // ignore
  }

  bindEvents();
  renderTabs();
  try {
    await refreshData();
  } catch (_e) {
    const matrix = document.getElementById("attendanceMatrixBody");
    if (matrix) matrix.innerHTML = `<tr><td class="muted">기록을 불러오지 못했습니다.</td></tr>`;
  }
});
