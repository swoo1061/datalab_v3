const state = {
  rows: [],
  search: "",
};

const KEY_ATTENDANCE = "attendance_requests_access";
const KEY_WEB_DASHBOARD = "web_dashboard_access";
const KEY_VACATION_ADMIN = "vacation_admin_access";
const KEY_EMPLOYEE_MANAGEMENT = "employee_management_access";
const KEY_SYSTEM_MONITOR = "system_monitor_access";

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function roleLabel(role) {
  const map = {
    admin: "ADMIN",
    ceo: "CEO",
    leader: "LEADER",
    manager: "MANAGER",
  };
  return map[String(role || "").toLowerCase()] || String(role || "-").toUpperCase();
}

async function fetchRows() {
  const data = await window.api?.getSystemPermissionUsers?.(state.search || "");
  state.rows = data.results || [];
}

function renderRows() {
  const tbody = document.getElementById("permTableBody");
  if (!tbody) return;
  if (!state.rows.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="muted">표시할 계정이 없습니다.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.rows
    .map((row) => {
      const attendanceOn = Boolean(row?.permissions?.[KEY_ATTENDANCE]);
      const webOn = Boolean(row?.permissions?.[KEY_WEB_DASHBOARD]);
      const vacationOn = Boolean(row?.permissions?.[KEY_VACATION_ADMIN]);
      const employeeOn = Boolean(row?.permissions?.[KEY_EMPLOYEE_MANAGEMENT]);
      const monitorOn = Boolean(row?.permissions?.[KEY_SYSTEM_MONITOR]);
      return `
        <tr data-user-id="${row.id}">
          <td>
            <div class="perm-name">${escapeHtml(row.name || "-")}</div>
            <div class="perm-role-sub">${escapeHtml(roleLabel(row.role))}</div>
          </td>
          <td><button type="button" class="perm-toggle ${attendanceOn ? "on" : ""}" data-key="${KEY_ATTENDANCE}" aria-label="근태 권한 토글"></button></td>
          <td><button type="button" class="perm-toggle ${webOn ? "on" : ""}" data-key="${KEY_WEB_DASHBOARD}" aria-label="웹 접근 권한 토글"></button></td>
          <td><button type="button" class="perm-toggle ${vacationOn ? "on" : ""}" data-key="${KEY_VACATION_ADMIN}" aria-label="휴가 관리 권한 토글"></button></td>
          <td><button type="button" class="perm-toggle ${employeeOn ? "on" : ""}" data-key="${KEY_EMPLOYEE_MANAGEMENT}" aria-label="직원 관리 권한 토글"></button></td>
          <td><button type="button" class="perm-toggle ${monitorOn ? "on" : ""}" data-key="${KEY_SYSTEM_MONITOR}" aria-label="서버 관리 권한 토글"></button></td>
        </tr>
      `;
    })
    .join("");
}

async function updatePermission(userId, key, enabled) {
  return window.api?.updateSystemPermissionUser?.(userId, { [key]: enabled });
}

function bindEvents() {
  const search = document.getElementById("permSearchInput");
  const refresh = document.getElementById("permRefreshBtn");
  const tbody = document.getElementById("permTableBody");

  search?.addEventListener("input", async () => {
    state.search = (search.value || "").trim();
    await fetchRows();
    renderRows();
  });

  refresh?.addEventListener("click", async () => {
    await fetchRows();
    renderRows();
    window.showAlert?.("권한 목록을 새로고침했습니다.");
  });

  tbody?.addEventListener("click", async (e) => {
    const btn = e.target?.closest?.(".perm-toggle");
    if (!btn) return;
    const tr = btn.closest("tr[data-user-id]");
    const userId = Number(tr?.dataset?.userId || 0);
    const key = btn.dataset.key || "";
    if (!userId || !key) return;

    const next = !btn.classList.contains("on");
    btn.disabled = true;
    try {
      await updatePermission(userId, key, next);
      btn.classList.toggle("on", next);
    } catch (err) {
      window.showAlert?.("권한 변경에 실패했습니다.");
    } finally {
      btn.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  try {
    await fetchRows();
    renderRows();
  } catch (err) {
    const tbody = document.getElementById("permTableBody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="muted">데이터를 불러오지 못했습니다.</td></tr>`;
  }
});
