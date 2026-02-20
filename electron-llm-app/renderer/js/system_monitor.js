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

async function loadMonitorSnapshot() {
  try {
    const data = await window.api?.getSystemMonitorSnapshot?.();
    state.checks = Array.isArray(data?.checks) ? data.checks : [];
    state.llm = Array.isArray(data?.llm) ? data.llm : [];
  } catch (_e) {
    state.checks = [];
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
    <div class="monitor-row"><span class="k">IP 주소</span><span class="v">${window.API_BASE}</span></div>
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

function getCheckCategory(item) {
  const key = String(item?.key || "");
  if (key === "llm_key_openai" || key === "llm_key_anthropic") return "llm_key";
  if (key.startsWith("accounts_")) return "account";
  if (key.startsWith("clinic_")) return "clinic_dynamic";
  if (key.startsWith("ml_") || key === "llm_models" || key === "monitor_llm") return "ml";
  return "data";
}

function categoryMeta(categoryKey) {
  const map = {
    llm_key: { title: "LLM 키 상태", order: 1 },
    account: { title: "인증/계정 API", order: 2 },
    data: { title: "데이터 API", order: 3 },
    ml: { title: "ML API", order: 4 },
    clinic_dynamic: { title: "병원 상세 API (동적)", order: 5 },
  };
  return map[categoryKey] || { title: "기타", order: 99 };
}

function groupChecksByCategory(checks) {
  const groups = new Map();
  checks.forEach((item) => {
    const categoryKey = getCheckCategory(item);
    if (!groups.has(categoryKey)) groups.set(categoryKey, []);
    groups.get(categoryKey).push(item);
  });
  return Array.from(groups.entries())
    .sort((a, b) => categoryMeta(a[0]).order - categoryMeta(b[0]).order)
    .map(([categoryKey, items]) => ({ categoryKey, items }));
}

function renderChecks() {
  const root = document.getElementById("monitorApiChecks");
  if (!root) return;
  const llmChecks = (state.llm || []).map((row) => {
    const configured = Boolean(row?.configured);
    const connected = Boolean(row?.connected);
    return {
      key: row?.provider === "openai" ? "llm_key_openai" : "llm_key_anthropic",
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

  const grouped = groupChecksByCategory(merged);
  root.innerHTML = grouped
    .map(({ categoryKey, items }) => {
      const meta = categoryMeta(categoryKey);
      const okCount = items.filter((x) => x.ok).length;
      const total = items.length;
      return `
      <section class="monitor-group">
        <header class="monitor-group-head">
          <h4 class="monitor-group-title">${meta.title}</h4>
          <span class="monitor-group-count">${okCount}/${total}</span>
        </header>
        <div class="monitor-group-list">
          ${items
            .map((item) => `
            <div class="monitor-item">
              <div class="top">
                <span class="name">${item.label}</span>
                <span class="status-pill ${statusClass(item)}">${statusText(item)}</span>
              </div>
              <div class="meta">${item.note ? item.note : `HTTP ${item.status || "-"} · ${item.latency}ms`}</div>
            </div>
          `)
            .join("")}
        </div>
      </section>
      `;
    })
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
  await loadMonitorSnapshot();
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
