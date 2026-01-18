const { contextBridge, ipcRenderer } = require("electron");

const API_BASE = "http://localhost:8000";
let sessionKey = null;

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

contextBridge.exposeInMainWorld("api", {
  /* =========================
     인증
  ========================= */
  login: async (username, password) => {
    const data = await requestJson("/api/accounts/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    if (data?.session_key) {
      sessionKey = data.session_key;
      await ipcRenderer.invoke("set-session-key", data.session_key);
      await ipcRenderer.invoke("set-session-cookie", {
        url: API_BASE,
        name: "sessionid",
        value: data.session_key,
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

  generateGangnamReview: (payload) =>
    requestJson("/api/ml/gangnam/review/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /* =========================
     즐겨찾기
  ========================= */
  getFavorites: () =>
    requestJson("/api/data/favorites/", { method: "GET" }),

  addFavorite: (clinicId) =>
    requestJson("/api/data/favorites/", {
      method: "POST",
      body: JSON.stringify({ clinic_id: clinicId }),
    }),

  removeFavorite: (clinicId) =>
    requestJson(`/api/data/favorites/${clinicId}/`, {
      method: "DELETE",
    }),
});

contextBridge.exposeInMainWorld("nav", {
  go: (page) => ipcRenderer.invoke("go", page),
});

contextBridge.exposeInMainWorld("session", {
  clear: async () => {
    const { session } = require("electron").remote || require("electron");
    await session.defaultSession.clearStorageData();
  },
});
