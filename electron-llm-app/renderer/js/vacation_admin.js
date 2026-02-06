window.globalSearchIndex = window.globalSearchIndex || { pages: [] };
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "휴가 관리", page: "vacation_admin" });
}

const state = {
  year: new Date().getFullYear(),
  status: "",
  q: "",
  rows: [],
};

async function buildHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

function statusLabel(status) {
  if (status === "pending") return "대기";
  if (status === "approved") return "승인";
  if (status === "rejected") return "반려";
  return "-";
}

function typeLabel(type) {
  if (type === "annual") return "연차";
  if (type === "half_am") return "오전반차";
  if (type === "half_pm") return "오후반차";
  return "-";
}

async function fetchList() {
  const headers = await buildHeaders();
  const params = new URLSearchParams({ year: state.year });
  if (state.status) params.set("status", state.status);
  if (state.q) params.set("q", state.q);
  const res = await fetch(`${window.API_BASE}/api/data/vacations/admin/?${params.toString()}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("vacation_admin_fetch_failed");
  return res.json();
}

async function patchRequest(id, action) {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/vacations/admin/${id}/`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ action }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.message || "vacation_admin_patch_failed");
  return data;
}

function renderTable() {
  const body = document.getElementById("vacationAdminBody");
  if (!body) return;
  if (!state.rows.length) {
    body.innerHTML = `<tr><td colspan="8" class="muted">데이터가 없습니다.</td></tr>`;
    return;
  }
  body.innerHTML = state.rows
    .map((row) => {
      const status = statusLabel(row.status);
      const type = typeLabel(row.type);
      const period = row.start_date === row.end_date ? row.start_date : `${row.start_date} ~ ${row.end_date}`;
      const badge = `<span class="vacation-status ${row.status}">${status}</span>`;
      const remain = typeof row.remaining_days === "number" ? row.remaining_days.toFixed(1) : "-";
      const actions = row.status === "pending"
        ? `<button class="btn" data-action="approve" data-id="${row.id}">승인</button>
           <button class="btn" data-action="reject" data-id="${row.id}">반려</button>`
        : "-";
      return `
        <tr>
          <td>${badge}</td>
          <td>${row.requester_name || "-"}</td>
          <td>${row.created_at?.slice?.(0, 10) || "-"}</td>
          <td>${period}</td>
          <td>${type}</td>
          <td>${row.days}일</td>
          <td>${remain}일</td>
          <td>${actions}</td>
        </tr>
      `;
    })
    .join("");
}

async function refresh() {
  const data = await fetchList();
  state.rows = data.results || [];
  renderTable();
}

function setupYearSelect() {
  const select = document.getElementById("vacationAdminYear");
  if (!select) return;
  const now = new Date().getFullYear();
  select.innerHTML = [now - 1, now, now + 1]
    .map((y) => `<option value="${y}" ${y === state.year ? "selected" : ""}>${y}년</option>`)
    .join("");
  select.addEventListener("change", async () => {
    state.year = Number(select.value);
    await refresh();
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupYearSelect();

  const statusSelect = document.getElementById("vacationAdminStatus");
  const searchInput = document.getElementById("vacationAdminSearch");
  const body = document.getElementById("vacationAdminBody");

  statusSelect?.addEventListener("change", async () => {
    state.status = statusSelect.value || "";
    await refresh();
  });

  searchInput?.addEventListener("input", async () => {
    state.q = (searchInput.value || "").trim();
    await refresh();
  });

  body?.addEventListener("click", async (e) => {
    const btn = e.target?.closest?.("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id || 0);
    const action = btn.dataset.action || "";
    if (!id || !action) return;
    btn.disabled = true;
    try {
      await patchRequest(id, action);
      await refresh();
      window.showAlert?.(action === "approve" ? "승인했습니다." : "반려했습니다.");
    } catch (_e) {
      window.showAlert?.("처리에 실패했습니다.");
    } finally {
      btn.disabled = false;
    }
  });

  await refresh();
});
