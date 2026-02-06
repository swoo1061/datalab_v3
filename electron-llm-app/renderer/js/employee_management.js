window.globalSearchIndex = window.globalSearchIndex || { pages: [] };
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "직원 관리", page: "employee_management" });
}

const state = {
  q: "",
  rows: [],
};

async function buildHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

function roleLabel(role) {
  const map = { admin: "관리자", ceo: "대표", leader: "팀장", manager: "매니저" };
  return map[String(role || "").toLowerCase()] || String(role || "-").toUpperCase();
}

function shiftLabel(hour) {
  const h = Number(hour || 9);
  return h === 10 ? "AE" : "AM";
}

function daysUntilBirthday(birthDate) {
  if (!birthDate) return null;
  const d = new Date(birthDate);
  if (Number.isNaN(d.valueOf())) return null;
  const now = new Date();
  const year = now.getFullYear();
  const next = new Date(year, d.getMonth(), d.getDate());
  if (next < now) next.setFullYear(year + 1);
  const diff = Math.ceil((next - now) / (24 * 60 * 60 * 1000));
  return diff;
}


function renderGrid() {
  const grid = document.getElementById("employeeGrid");
  if (!grid) return;
  const rolePriority = { ceo: 0, leader: 1, manager: 2 };
  const visibleRows = state.rows
    .filter((row) => String(row.position || "").toLowerCase() !== "admin")
    .slice()
    .sort((a, b) => {
      const ra = rolePriority[String(a.position || "").toLowerCase()] ?? 9;
      const rb = rolePriority[String(b.position || "").toLowerCase()] ?? 9;
      if (ra !== rb) return ra - rb;
      if (ra === rolePriority.manager && rb === rolePriority.manager) {
        const da = a.hire_date ? new Date(a.hire_date).getTime() : Number.MAX_SAFE_INTEGER;
        const db = b.hire_date ? new Date(b.hire_date).getTime() : Number.MAX_SAFE_INTEGER;
        return da - db;
      }
      const na = String(a.name || "");
      const nb = String(b.name || "");
      return na.localeCompare(nb, "ko");
    });
  if (!visibleRows.length) {
    grid.innerHTML = `<div class="muted">직원 정보가 없습니다.</div>`;
    return;
  }
  grid.innerHTML = visibleRows
    .map((row) => {
      const daysLeft = Number(row.remaining_days || 0);
      const birthLeft = daysUntilBirthday(row.birth_date);
      return `
        <div class="employee-card">
          <div class="employee-head">
            <div class="employee-name">${row.name || "-"}</div>
            <div class="employee-tags">
              <span class="employee-tag role">${roleLabel(row.position)}</span>
            </div>
          </div>
          <div class="employee-meta">
            <div><span>이메일</span>${row.email || "-"}</div>
            <div><span>전화</span>${row.phone || "-"}</div>
            <div><span>생일</span>${row.birth_date || "-"}${birthLeft ? ` (${birthLeft}일 남음)` : ""}</div>
            <div><span>입사일</span>${row.hire_date || "-"}</div>
          </div>
          <div class="employee-stats">
            <div class="employee-stat"><span class="label">총 연차</span><span class="value">${row.total_days}일</span></div>
            <div class="employee-stat"><span class="label">사용</span><span class="value">${row.used_days}일</span></div>
            <div class="employee-stat">
              <span class="label">잔여</span>
              <span class="value employee-remaining ${daysLeft < 0 ? "negative" : ""}">${row.remaining_days}일</span>
            </div>
          </div>
        </div>
      `;
    })
    .join("");
}

async function fetchEmployees() {
  const headers = await buildHeaders();
  const params = new URLSearchParams({ year: new Date().getFullYear() });
  if (state.q) params.set("q", state.q);
  const res = await fetch(`${window.API_BASE}/api/data/vacations/admin/summary/?${params.toString()}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("employee_fetch_failed");
  return res.json();
}

async function refresh() {
  const data = await fetchEmployees();
  state.rows = data.results || [];
  renderGrid();
}

document.addEventListener("DOMContentLoaded", async () => {
  await refresh();
});
