const { contextBridge, ipcRenderer } = require("electron");

const API_BASE = "http://127.0.0.1:8000";

async function requestJson(path, options = {}) {
  const url = API_BASE + path;

  const res = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
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

// ================================
// API 노출
// ================================
contextBridge.exposeInMainWorld("api", {
  // 인증
  login: (username, password) =>
    requestJson("/api/accounts/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () =>
    requestJson("/api/accounts/logout/", {
      method: "POST",
    }),

  getMe: () =>
    requestJson("/api/accounts/me/", {
      method: "GET",
    }),

  // 병원 / 원장
  getClinics: async () => {
    const data = await requestJson("/api/clinics/", { method: "GET" });
    return data.results;
  },

  getDoctors: async (clinicId) => {
    const data = await requestJson(
      `/api/clinics/${clinicId}/doctors/`,
      { method: "GET" }
    );
    return data.results;
  },

  getClinicDetail: (clinicId) =>
  requestJson(`/dashboard/api/clinics/${clinicId}/detail/`, {
    method: "GET",
  }),

  // ⭐ LLM 모델 (중요)
  getLLMModels: async () => {
    const data = await requestJson("/api/llm/models/", {
      method: "GET",
    });
    return data.results; // ✅ 핵심 수정
  },

  // 리뷰 생성
  generateReview: (payload) =>
    requestJson("/api/reviews/generate/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
});

// ================================
// 화면 이동
// ================================
contextBridge.exposeInMainWorld("nav", {
  go: (page) => ipcRenderer.invoke("go", page),
});
