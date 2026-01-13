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

contextBridge.exposeInMainWorld("api", {
  // 인증 (Django HTTP)
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

  // 병원
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
    requestJson(`/api/clinics/${clinicId}/detail/`, { method: "GET" }),

  getLLMModels: async () => {
    const data = await requestJson("/api/llm/models/", { method: "GET" });
    return data.results;
  },

  generateReview: (payload) =>
    requestJson("/api/review/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
});

contextBridge.exposeInMainWorld("nav", {
  go: (page) => ipcRenderer.invoke("go", page),
});
