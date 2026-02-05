window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";

window.globalSearchIndex = window.globalSearchIndex || {
  pages: [],
};
if (Array.isArray(window.globalSearchIndex.pages)) {
  window.globalSearchIndex.pages.push({ key: "시스템 모니터링", page: "system_monitor" });
}

const state = {
  me: null,
  appVersion: "-",
  checks: [],
  llm: [],
  auto: false,
  timer: null,
};
const AUTO_REFRESH_STORAGE_KEY = "system_monitor_auto_refresh";

const STATIC_CHECKS = [
  { key: "accounts_me", label: "계정 인증 API", path: "/api/accounts/me/" },
  { key: "accounts_users", label: "유저 목록 API", path: "/api/accounts/users/" },
  { key: "clinics_list", label: "병원 목록 API", path: "/api/data/clinics/?limit=1" },
  { key: "llm_models", label: "LLM 모델 목록 API", path: "/api/data/llm/models/" },
  { key: "my_clinics", label: "내 병원 API", path: "/api/data/my-clinics/?months=1" },
  { key: "favorites", label: "즐겨찾기 API", path: "/api/data/favorites/" },
  { key: "calendar_memos", label: "캘린더 메모 API", path: "/api/data/calendar-memos/?limit=1" },
  { key: "notifications", label: "알림 API", path: "/api/data/notifications/?limit=1" },
  { key: "attendance_me", label: "출퇴근 API", path: "/api/data/attendance/me/" },
  { key: "attendance_corrections", label: "정정요청 목록 API", path: "/api/data/attendance/me/corrections/?limit=1" },
  { key: "permissions_me", label: "내 권한 API", path: "/api/data/system-permissions/me/?key=web_dashboard_access" },
  { key: "permissions_users", label: "권한 유저목록 API", path: "/api/data/system-permissions/users/" },
  { key: "messages", label: "메일 API", path: "/api/data/messages/?box=inbox&limit=1" },
  { key: "monitor_llm", label: "LLM 키 점검 API", path: "/api/data/system-monitor/llm-status/?connectivity=1" },
  { key: "clinics_legacy", label: "병원 목록 API(legacy)", path: "/api/data/clinics/" },
];

function roleLabel(role) {
  const map = {
    admin: "ADMIN",
    ceo: "CEO",
    leader: "LEADER",
    manager: "MANAGER",
  };
  const raw = String(role || "").toLowerCase();
  return map[raw] || (raw ? raw.toUpperCase() : "-");
}

async function buildHeaders() {
  const headers = {};
  const key = await window.session?.getKey?.();
  if (key) headers["X-Sessionid"] = key;
  return headers;
}

function formatDateTime(d) {
  if (!(d instanceof Date) || Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function detectClientOs() {
  const ua = String(navigator.userAgent || "");
  const platform = String(navigator.platform || "").toLowerCase();
  if (platform.includes("win") || ua.includes("Windows")) return "Windows";
  if (platform.includes("mac") || ua.includes("Mac OS X")) return "macOS";
  if (platform.includes("linux") || ua.includes("Linux")) return "Linux";
  return "Unknown";
}

function detectClientApp() {
  const ua = String(navigator.userAgent || "");
  if (ua.includes("Electron")) return "Datalab90 Electron";
  return "Web Browser";
}

function statusClass(item) {
  if (item.ok) return "ok";
  if (item.status >= 400 && item.status < 500) return "warn";
  return "fail";
}

function statusText(item) {
  if (item.ok) return "정상";
  if (item.status >= 400 && item.status < 500) return `경고 (${item.status})`;
  return `오류 (${item.status || "-"})`;
}

async function runSingleCheck(def) {
  const headers = await buildHeaders();
  const started = performance.now();
  try {
    const res = await fetch(`${window.API_BASE}${def.path}`, {
      credentials: "include",
      headers,
    });
    const latency = Math.round(performance.now() - started);
    return {
      key: def.key,
      label: def.label,
      ok: res.ok,
      status: res.status,
      latency,
    };
  } catch (e) {
    const latency = Math.round(performance.now() - started);
    return {
      key: def.key,
      label: def.label,
      ok: false,
      status: 0,
      latency,
    };
  }
}

async function loadBaseInfo() {
  try {
    state.me = await window.api?.getMe?.();
  } catch (_e) {
    state.me = null;
  }
  try {
    state.appVersion = await window.api?.getAppVersion?.();
  } catch (_e) {
    state.appVersion = "-";
  }
}

async function loadChecks() {
  const checks = await Promise.all(STATIC_CHECKS.map((def) => runSingleCheck(def)));

  let firstClinicId = null;

  try {
    const headers = await buildHeaders();
    const clinicsRes = await fetch(`${window.API_BASE}/api/data/clinics/?limit=1`, {
      credentials: "include",
      headers,
    });
    if (clinicsRes.ok) {
      const clinicsData = await clinicsRes.json();
      const first = Array.isArray(clinicsData?.results) ? clinicsData.results[0] : null;
      firstClinicId = Number(first?.id || 0) || null;
    }
  } catch (_e) {}

  const dynamicChecks = [];
  if (firstClinicId) {
    dynamicChecks.push(
      { key: "clinic_detail", label: "병원 상세 API", path: `/api/data/clinics/${firstClinicId}/` },
      { key: "clinic_doctors", label: "병원 의료진 API", path: `/api/data/clinics/${firstClinicId}/doctors/` },
      { key: "clinic_worklogs", label: "병원 작업로그 API", path: `/api/data/clinics/${firstClinicId}/worklogs/` },
      { key: "clinic_worklogs_summary", label: "작업로그 요약 API", path: `/api/data/clinics/${firstClinicId}/worklogs/summary/` },
      { key: "clinic_posts", label: "병원 게시글 API", path: `/api/data/clinics/${firstClinicId}/posts/?type=all&platform=all` },
      { key: "clinic_assignees", label: "병원 담당자 API", path: `/api/data/clinics/${firstClinicId}/assignees/` },
      { key: "clinic_detail_legacy", label: "병원 상세 API(legacy)", path: `/api/data/clinics/${firstClinicId}/detail/` },
    );
  }

  const dynamicResults = await Promise.all(dynamicChecks.map((def) => runSingleCheck(def)));
  state.checks = [...checks, ...dynamicResults];
}

async function loadLlmStatus() {
  const headers = await buildHeaders();
  try {
    const res = await fetch(`${window.API_BASE}/api/data/system-monitor/llm-status/?connectivity=1`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) {
      state.llm = [];
      return;
    }
    const data = await res.json();
    state.llm = Array.isArray(data?.providers) ? data.providers : [];
  } catch (_e) {
    state.llm = [];
  }
}

function renderInfo() {
  const root = document.getElementById("monitorInfo");
  if (!root) return;
  const sessionExists = Boolean(window.session?.getKey);
  const me = state.me || {};
  const openai = state.llm.find((x) => x.provider === "openai");
  const anthropic = state.llm.find((x) => x.provider === "anthropic");
  const llmLabel = (row) => {
    if (!row) return "-";
    if (!row.configured) return "미설정";
    return row.connected ? "연결됨" : `연결실패 (${row.detail || "-"})`;
  };
  const firewallLabel = (() => {
    if (!Array.isArray(state.checks) || !state.checks.length) return "-";
    const networkBlocked = state.checks.some((x) => Number(x?.status || 0) === 0);
    return networkBlocked ? "의심 (통신 차단 가능)" : "정상 (API 통신 가능)";
  })();
  root.innerHTML = `
    <div class="monitor-row"><span class="k">클라이언트 OS</span><span class="v">${detectClientOs()}</span></div>
    <div class="monitor-row"><span class="k">실행 앱</span><span class="v">${detectClientApp()}</span></div>
    <div class="monitor-row"><span class="k">앱 버전</span><span class="v">${state.appVersion || "-"}</span></div>
    <div class="monitor-row"><span class="k">API 주소</span><span class="v">${window.API_BASE}</span></div>
    <div class="monitor-row"><span class="k">로그인 계정</span><span class="v">${me?.name || me?.username || "-"}</span></div>
    <div class="monitor-row"><span class="k">권한</span><span class="v">${roleLabel(me?.position || me?.role)}</span></div>
    <div class="monitor-row"><span class="k">세션 모듈</span><span class="v">${sessionExists ? "연결됨" : "없음"}</span></div>
    <div class="monitor-row"><span class="k">방화벽 상태</span><span class="v">${firewallLabel}</span></div>
    <div class="monitor-row"><span class="k">OPENAI_API_KEY</span><span class="v">${llmLabel(openai)}</span></div>
    <div class="monitor-row"><span class="k">ANTHROPIC_API_KEY</span><span class="v">${llmLabel(anthropic)}</span></div>
  `;
}

function renderSummary() {
  const root = document.getElementById("monitorSummaryCards");
  if (!root) return;
  const llmChecks = (state.llm || []).map((row) => ({
    ok: Boolean(row?.configured) && Boolean(row?.connected),
    latency: 0,
  }));
  const allChecks = [...llmChecks, ...state.checks];
  const total = allChecks.length;
  const okCount = allChecks.filter((x) => x.ok).length;
  const failCount = total - okCount;
  const avg = total
    ? Math.round(allChecks.reduce((acc, cur) => acc + (Number(cur.latency) || 0), 0) / total)
    : 0;
  root.innerHTML = `
    <div class="monitor-chip"><span class="label">전체 체크</span><span class="value">${total}</span></div>
    <div class="monitor-chip"><span class="label">정상</span><span class="value">${okCount}</span></div>
    <div class="monitor-chip"><span class="label">오류</span><span class="value">${failCount}</span></div>
    <div class="monitor-chip"><span class="label">평균 지연</span><span class="value">${avg}ms</span></div>
  `;
}

function renderChecks() {
  const root = document.getElementById("monitorApiChecks");
  if (!root) return;
  const llmChecks = (state.llm || []).map((row) => {
    const configured = Boolean(row?.configured);
    const connected = Boolean(row?.connected);
    return {
      label: row?.provider === "openai" ? "OPENAI_API_KEY" : "ANTHROPIC_API_KEY",
      ok: configured && connected,
      status: configured ? (connected ? 200 : 503) : 400,
      latency: 0,
      note: configured ? (connected ? "연결 확인 완료" : `연결 실패 (${row?.detail || "-"})`) : "키 미설정",
    };
  });
  const merged = [...llmChecks, ...state.checks];

  if (!merged.length) {
    root.innerHTML = `<div class="muted">체크 결과가 없습니다.</div>`;
    return;
  }
  root.innerHTML = merged
    .map((item) => `
      <div class="monitor-item">
        <div class="top">
          <span class="name">${item.label}</span>
          <span class="status-pill ${statusClass(item)}">${statusText(item)}</span>
        </div>
        <div class="meta">${item.note ? item.note : `HTTP ${item.status || "-"} · ${item.latency}ms`}</div>
      </div>
    `)
    .join("");
}

function renderUpdatedAt() {
  const el = document.getElementById("monitorUpdatedAt");
  if (!el) return;
  el.textContent = `최근 갱신: ${formatDateTime(new Date())}`;
}

function renderAutoButton() {
  const btn = document.getElementById("monitorAutoBtn");
  if (!btn) return;
  btn.textContent = state.auto ? "ON" : "OFF";
  btn.classList.toggle("primary", state.auto);
  btn.classList.toggle("is-on", state.auto);
}

function persistAutoRefresh() {
  try {
    localStorage.setItem(AUTO_REFRESH_STORAGE_KEY, state.auto ? "1" : "0");
  } catch (_e) {
    // ignore storage errors
  }
}

function restoreAutoRefresh() {
  try {
    const raw = localStorage.getItem(AUTO_REFRESH_STORAGE_KEY);
    state.auto = raw === "1";
  } catch (_e) {
    state.auto = false;
  }
}

function applyAutoRefreshTimer() {
  if (state.timer) {
    window.clearInterval(state.timer);
    state.timer = null;
  }
  if (state.auto) {
    state.timer = window.setInterval(() => {
      refreshAll().catch(() => {});
    }, 30000);
  }
}

async function refreshAll() {
  await loadBaseInfo();
  await Promise.all([loadChecks(), loadLlmStatus()]);
  renderInfo();
  renderSummary();
  renderChecks();
  renderUpdatedAt();
}

function toggleAutoRefresh() {
  state.auto = !state.auto;
  applyAutoRefreshTimer();
  persistAutoRefresh();
  renderAutoButton();
}

function bindEvents() {
  const refreshBtn = document.getElementById("monitorRefreshBtn");
  const autoBtn = document.getElementById("monitorAutoBtn");
  refreshBtn?.addEventListener("click", async () => {
    await refreshAll();
    window.showAlert?.("시스템 상태를 갱신했습니다.");
  });
  autoBtn?.addEventListener("click", toggleAutoRefresh);
}

document.addEventListener("DOMContentLoaded", async () => {
  restoreAutoRefresh();
  applyAutoRefreshTimer();
  bindEvents();
  renderAutoButton();
  try {
    await refreshAll();
  } catch (_e) {
    const root = document.getElementById("monitorApiChecks");
    if (root) root.innerHTML = `<div class="muted">상태를 불러오지 못했습니다.</div>`;
  }
});
