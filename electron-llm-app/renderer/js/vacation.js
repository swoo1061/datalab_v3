window.globalSearchIndex = window.globalSearchIndex || { pages: [] };
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "휴가 신청", page: "vacation" });
}

const state = {
  year: new Date().getFullYear(),
  data: [],
  summary: null,
  workStartHour: 9,
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

function renderSummary() {
  const root = document.getElementById("vacationSummary");
  if (!root) return;
  const s = state.summary || { total_days: 15, used_days: 0, pending_days: 0, remaining_days: 15 };
  root.innerHTML = `
    <div class="vacation-chip"><span class="label">총 연차</span><span class="value">${s.total_days}일</span></div>
    <div class="vacation-chip"><span class="label">사용</span><span class="value">${s.used_days}일</span></div>
    <div class="vacation-chip"><span class="label">대기</span><span class="value">${s.pending_days}일</span></div>
    <div class="vacation-chip"><span class="label">잔여</span><span class="value">${s.remaining_days}일</span></div>
  `;
}

function renderList() {
  const body = document.getElementById("vacationListBody");
  if (!body) return;
  if (!state.data.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted">신청 내역이 없습니다.</td></tr>`;
    return;
  }
  body.innerHTML = state.data
    .map((row) => {
      const status = statusLabel(row.status);
      const type = typeLabel(row.type);
      const period = row.start_date === row.end_date ? row.start_date : `${row.start_date} ~ ${row.end_date}`;
      const badge = `<span class="vacation-status ${row.status}">${status}</span>`;
      return `
        <tr>
          <td>${badge}</td>
          <td>${row.created_at?.slice?.(0, 10) || "-"}</td>
          <td>${period}</td>
          <td>${type}</td>
          <td>${row.days}일</td>
          <td>${row.reason || "-"}</td>
        </tr>
      `;
    })
    .join("");
}

function renderShiftInfo() {
  const root = document.getElementById("vacationShiftInfo");
  if (!root) return;
  const hour = Number(state.workStartHour || 9);
  if (hour === 10) {
    root.innerHTML = `
      <div>오전반차: 10시 출근 → 2시 퇴근 (점심 포함 시 3시)</div>
      <div>오후반차: 3시 출근</div>
    `;
    return;
  }
  root.innerHTML = `
    <div>오전반차: 9시 출근 → 1시 퇴근 (점심 포함 시 2시)</div>
    <div>오후반차: 2시 출근</div>
  `;
}

function calcDays(type, startDate, endDate) {
  if (!startDate) return 0;
  if (type === "half_am" || type === "half_pm") return 0.5;
  if (!endDate) return 0;
  const s = new Date(startDate);
  const e = new Date(endDate);
  if (Number.isNaN(s.valueOf()) || Number.isNaN(e.valueOf())) return 0;
  const diff = Math.floor((e - s) / (24 * 60 * 60 * 1000)) + 1;
  return diff > 0 ? diff : 0;
}

function updateDayHint() {
  const hint = document.getElementById("vacationDayHint");
  const startInput = document.getElementById("vacationStart");
  const endInput = document.getElementById("vacationEnd");
  const type = document.querySelector("input[name='vacationType']:checked")?.value || "annual";
  const days = calcDays(type, startInput?.value, endInput?.value);
  if (hint) hint.textContent = `사용 일수: ${days || "-"}일`;
}

function syncDateInputs() {
  const startInput = document.getElementById("vacationStart");
  const endInput = document.getElementById("vacationEnd");
  const type = document.querySelector("input[name='vacationType']:checked")?.value || "annual";
  if (!startInput || !endInput) return;
  const isHalf = type === "half_am" || type === "half_pm";
  endInput.disabled = isHalf;
  if (isHalf) {
    endInput.value = startInput.value || endInput.value;
  }
  updateDayHint();
}

async function fetchData() {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/vacations/me/?year=${state.year}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("vacation_fetch_failed");
  return res.json();
}

async function createRequest(payload) {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/vacations/me/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.message || "vacation_create_failed");
  return data;
}

function setupYearSelect() {
  const select = document.getElementById("vacationYear");
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

async function refresh() {
  const data = await fetchData();
  state.data = data.results || [];
  state.summary = data.summary || null;
  renderSummary();
  renderList();
}

document.addEventListener("DOMContentLoaded", async () => {
  setupYearSelect();
  renderSummary();
  renderShiftInfo();

  const form = document.getElementById("vacationForm");
  const startInput = document.getElementById("vacationStart");
  const endInput = document.getElementById("vacationEnd");
  const reasonInput = document.getElementById("vacationReason");
  const refreshBtn = document.getElementById("vacationRefresh");

  refreshBtn?.addEventListener("click", refresh);
  startInput?.addEventListener("change", syncDateInputs);
  endInput?.addEventListener("change", updateDayHint);
  document.querySelectorAll("input[name='vacationType']").forEach((el) => {
    el.addEventListener("change", syncDateInputs);
  });

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const type = document.querySelector("input[name='vacationType']:checked")?.value || "annual";
    const start_date = startInput?.value;
    let end_date = endInput?.value || start_date;
    if (type !== "annual") end_date = start_date;
    const reason = reasonInput?.value || "";
    try {
      await createRequest({ type, start_date, end_date, reason });
      window.showAlert?.("휴가 신청이 접수되었습니다.");
      if (reasonInput) reasonInput.value = "";
      await refresh();
    } catch (err) {
      const msg = String(err?.message || "");
      if (msg === "half_day_single_date") {
        window.showAlert?.("반차는 하루만 선택해주세요.");
      } else if (msg === "invalid_date_range") {
        window.showAlert?.("날짜 범위를 확인해주세요.");
      } else if (msg === "date_required") {
        window.showAlert?.("날짜를 입력해주세요.");
      } else if (msg === "type_required") {
        window.showAlert?.("유형을 선택해주세요.");
      } else {
        window.showAlert?.("휴가 신청에 실패했습니다.");
      }
    }
  });

  try {
    const me = await window.api?.getMe?.();
    state.workStartHour = Number(me?.work_start_hour || 9);
    renderShiftInfo();
  } catch (_e) {}

  syncDateInputs();
  await refresh();
});
