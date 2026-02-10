const { contextBridge, ipcRenderer } = require("electron");

const API_BASE = (process.env.DATALAB_API_BASE || process.env.API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
let sessionKey = null;

function installExternalLinkInterceptor() {
  const resolveExternalUrl = (href) => {
    try {
      const resolved = new URL(href, window.location.href);
      if (/^https?:$/i.test(resolved.protocol)) {
        return resolved.toString();
      }
      return "";
    } catch (_e) {
      return "";
    }
  };

  const openExternalSafely = async (href) => {
    const targetUrl = resolveExternalUrl(href);
    if (!targetUrl) return;
    try {
      await ipcRenderer.invoke("open-external", targetUrl);
    } catch (_e) {
      // ignore open failures to avoid breaking UI handlers
    }
  };

  const handleAnchorEvent = (event) => {
    const anchor = event.target?.closest?.("a[href]");
    if (!anchor) return;
    const href = anchor.getAttribute("href") || anchor.href || "";
    const targetUrl = resolveExternalUrl(href);
    if (!targetUrl) return;
    event.preventDefault();
    event.stopPropagation();
    openExternalSafely(targetUrl);
  };

  window.addEventListener("click", handleAnchorEvent, true);
  window.addEventListener("auxclick", handleAnchorEvent, true);

  const originalOpen = window.open;
  window.open = function patchedOpen(url, target, features) {
    const targetUrl = resolveExternalUrl(url);
    if (targetUrl) {
      openExternalSafely(url);
      return null;
    }
    return originalOpen.call(window, url, target, features);
  };
}

if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", installExternalLinkInterceptor, { once: true });
} else {
  installExternalLinkInterceptor();
}

async function ensureSessionKey() {
  if (sessionKey) return sessionKey;
  sessionKey = await ipcRenderer.invoke("get-session-key");
  return sessionKey;
}

async function requestJson(path, options = {}) {
  const url = API_BASE + path;

  const key = await ensureSessionKey();
  const extraHeaders = key ? { "X-Sessionid": key } : {};
  const res = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...extraHeaders,
      ...(options.headers || {}),
    },
  });

  const text = await res.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    const err = new Error(data?.message || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

async function requestWithStatus(path, options = {}) {
  const url = API_BASE + path;
  const key = await ensureSessionKey();
  const extraHeaders = key ? { "X-Sessionid": key } : {};
  const res = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...extraHeaders,
      ...(options.headers || {}),
    },
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }

  return {
    ok: res.ok,
    status: res.status,
    data,
  };
}

function getCurrentMonthKey() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${now.getFullYear()}-${month}`;
}

function getCurrentYearKey() {
  return String(new Date().getFullYear());
}

function getSystemMonitorStaticChecks() {
  const monthKey = getCurrentMonthKey();
  const yearKey = getCurrentYearKey();
  return [
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
    { key: "attendance_admin_records", label: "출퇴근 관리 API", path: `/api/data/attendance/admin/records/?month=${monthKey}&status=all` },
    { key: "attendance_admin_corrections", label: "정정요청 관리 API", path: `/api/data/attendance/admin/corrections/?month=${monthKey}&status=pending` },
    { key: "vacation_me", label: "휴가 신청 API", path: `/api/data/vacations/me/?year=${yearKey}` },
    { key: "vacation_admin", label: "휴가 관리 API", path: `/api/data/vacations/admin/?year=${yearKey}` },
    { key: "employee_summary", label: "직원 관리 API", path: `/api/data/vacations/admin/summary/?year=${yearKey}` },
    { key: "permissions_me", label: "내 권한 API", path: "/api/data/system-permissions/me/?key=web_dashboard_access" },
    { key: "permissions_users", label: "권한 유저목록 API", path: "/api/data/system-permissions/users/" },
    { key: "messages", label: "메일 API", path: "/api/data/messages/?box=inbox&limit=1" },
    { key: "monitor_llm", label: "LLM 키 점검 API", path: "/api/data/system-monitor/llm-status/?connectivity=1" },
    { key: "clinics_legacy", label: "병원 목록 API(legacy)", path: "/api/data/clinics/" },
  ];
}

async function runSystemMonitorCheck(def) {
  const started = performance.now();
  try {
    const res = await requestWithStatus(def.path, { method: "GET" });
    return {
      key: def.key,
      label: def.label,
      ok: res.ok,
      status: res.status,
      latency: Math.round(performance.now() - started),
    };
  } catch {
    return {
      key: def.key,
      label: def.label,
      ok: false,
      status: 0,
      latency: Math.round(performance.now() - started),
    };
  }
}

async function getSystemMonitorSnapshot() {
  const staticChecks = getSystemMonitorStaticChecks();
  const checks = await Promise.all(staticChecks.map((def) => runSystemMonitorCheck(def)));

  let firstClinicId = null;
  try {
    const clinics = await requestWithStatus("/api/data/clinics/?limit=1", { method: "GET" });
    if (clinics.ok) {
      const first = Array.isArray(clinics.data?.results) ? clinics.data.results[0] : null;
      firstClinicId = Number(first?.id || 0) || null;
    }
  } catch {
    firstClinicId = null;
  }

  const dynamicChecks = [];
  if (firstClinicId) {
    dynamicChecks.push(
      { key: "clinic_detail", label: "병원 상세 API", path: `/api/data/clinics/${firstClinicId}/` },
      { key: "clinic_doctors", label: "병원 의료진 API", path: `/api/data/clinics/${firstClinicId}/doctors/` },
      { key: "clinic_worklogs", label: "병원 작업로그 API", path: `/api/data/clinics/${firstClinicId}/worklogs/` },
      { key: "clinic_worklogs_summary", label: "작업로그 요약 API", path: `/api/data/clinics/${firstClinicId}/worklogs/summary/` },
      { key: "clinic_posts", label: "병원 게시글 API", path: `/api/data/clinics/${firstClinicId}/posts/?type=all&platform=all` },
      { key: "clinic_assignees", label: "병원 담당자 API", path: `/api/data/clinics/${firstClinicId}/assignees/` },
      { key: "clinic_detail_legacy", label: "병원 상세 API(legacy)", path: `/api/data/clinics/${firstClinicId}/detail/` }
    );
  }

  const dynamicResults = await Promise.all(dynamicChecks.map((def) => runSystemMonitorCheck(def)));

  let llmProviders = [];
  try {
    const llmRes = await requestWithStatus("/api/data/system-monitor/llm-status/?connectivity=1", { method: "GET" });
    if (llmRes.ok && Array.isArray(llmRes.data?.providers)) {
      llmProviders = llmRes.data.providers;
    }
  } catch {
    llmProviders = [];
  }

  return {
    checks: [...checks, ...dynamicResults],
    llm: llmProviders,
    fetchedAt: new Date().toISOString(),
  };
}

contextBridge.exposeInMainWorld("api", {
  /* =========================
     인증
  ========================= */
  login: async (username, password, remember = false) => {
    const data = await requestJson("/api/accounts/login/", {
      method: "POST",
      body: JSON.stringify({ username, password, remember }),
    });
    if (data?.session_key) {
      sessionKey = data.session_key;
      const expirationDate = remember
        ? Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 30
        : undefined;
      await ipcRenderer.invoke("set-session-key", data.session_key);
      await ipcRenderer.invoke("set-session-cookie", {
        url: API_BASE,
        name: "sessionid",
        value: data.session_key,
        expirationDate,
      });
    }
    return data;
  },

  logout: async () => {
    const data = await requestJson("/api/accounts/logout/", {
      method: "POST",
    });
    sessionKey = null;
    await ipcRenderer.invoke("clear-session-key");
    await ipcRenderer.invoke("clear-session-cookie", {
      url: API_BASE,
      name: "sessionid",
    });
    return data;
  },

  quitApp: () => ipcRenderer.invoke("app-quit"),
  getAppVersion: () => ipcRenderer.invoke("app-get-version"),
  getUpdateUrl: () => ipcRenderer.invoke("app-get-update-url"),
  setSessionKey: (key) => ipcRenderer.invoke("set-session-key", key),

  getMe: () =>
    requestJson("/api/accounts/me/", {
      method: "GET",
    }),

  /* =========================
     병원
  ========================= */
  getClinics: async () => {
    const data = await requestJson("/api/data/clinics/", { method: "GET" });
    return data.results;
  },

  getDoctors: async (clinicId) => {
    const data = await requestJson(
      `/api/data/clinics/${clinicId}/doctors/`,
      { method: "GET" }
    );
    return data.results;
  },

  getClinicDetail: (clinicId) =>
    requestJson(`/api/data/clinics/${clinicId}/`, {
      method: "GET",
    }),

  /**
   * ✅ 병원 가이드 (review.js에서 사용)
   * clinic_guide를 서버에서 그대로 받아서 전달
   */
  getClinicGuide: async (clinicId) => {
  const clinic = await requestJson(
    `/api/data/clinics/${clinicId}/`,
    { method: "GET" }
  );

  // 👉 서버에서 내려주는 guide 관련 필드만 정리
  return clinic.guide || clinic.clinic_guide || clinic;
},

  /* =========================
     LLM
  ========================= */
  getLLMModels: async () => {
    const data = await requestJson("/api/data/llm/models/");
    return data.results ?? data;
  },

  generateReview: (payload) =>
    requestJson("/api/ml/review/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  saveEditedReview: (payload) =>
    requestJson("/api/ml/review/edit/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  generateGangnamReview: (payload) =>
    requestJson("/api/ml/gangnam_review/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  agentChat: (payload) =>
    requestJson("/api/ml/agent/chat/", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }),

  /* =========================
     즐겨찾기
  ========================= */
  getFavorites: (options = {}) => {
    const params = new URLSearchParams();
    if (options?.fallback) params.set("fallback", options.fallback);
    const qs = params.toString();
    return requestJson(`/api/data/favorites/${qs ? `?${qs}` : ""}`, { method: "GET" });
  },

  addFavorite: (clinicId) =>
    requestJson("/api/data/favorites/", {
      method: "POST",
      body: JSON.stringify({ clinic_id: clinicId }),
    }),

  removeFavorite: (clinicId) =>
    requestJson(`/api/data/favorites/${clinicId}/`, {
      method: "DELETE",
    }),

  getSystemLogsData: async (limit = 200, offset = 0) => {
    const [firewall, logs] = await Promise.all([
      requestJson("/dashboard/api/firewall-status/", { method: "GET" }).catch(() => null),
      requestJson(`/dashboard/api/access-logs/?limit=${Number(limit) || 200}&offset=${Number(offset) || 0}`, {
        method: "GET",
      }).catch(() => null),
    ]);
    return { firewall, logs };
  },

  getSystemPermissionUsers: (query = "") => {
    const q = String(query || "").trim();
    const qs = q ? `?q=${encodeURIComponent(q)}` : "";
    return requestJson(`/api/data/system-permissions/users/${qs}`, { method: "GET" });
  },

  updateSystemPermissionUser: (userId, permissions = {}) =>
    requestJson(`/api/data/system-permissions/users/${userId}/`, {
      method: "PATCH",
      body: JSON.stringify({ permissions }),
    }),

  getAuditEvents: (options = {}) => {
    const params = new URLSearchParams();
    if (options.limit) params.set("limit", String(options.limit));
    if (options.offset) params.set("offset", String(options.offset));
    if (options.q) params.set("q", String(options.q));
    if (options.event_type) params.set("event_type", String(options.event_type));
    if (options.user_id) params.set("user_id", String(options.user_id));
    if (options.from) params.set("from", String(options.from));
    if (options.to) params.set("to", String(options.to));
    const qs = params.toString();
    return requestJson(`/api/data/audit-events/${qs ? `?${qs}` : ""}`, { method: "GET" });
  },

  getSystemMonitorSnapshot,
});

contextBridge.exposeInMainWorld("config", {
  apiBase: API_BASE,
});

contextBridge.exposeInMainWorld("nav", {
  go: (page) => ipcRenderer.invoke("go", page),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  openKakaoWork: () => ipcRenderer.invoke("open-kakaowork"),
  openNotion: () => ipcRenderer.invoke("open-notion"),
});



contextBridge.exposeInMainWorld("session", {
  getKey: () => ipcRenderer.invoke("get-session-key"),
  clear: async () => {
    const { session } = require("electron").remote || require("electron");
    await session.defaultSession.clearStorageData();
  },
});
