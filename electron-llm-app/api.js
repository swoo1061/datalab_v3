const axios = require("axios");

const BASE_URL = "http://localhost:8000";

module.exports = {
  /* =====================
     Auth
  ===================== */
  async login(username, password) {
    const res = await axios.post(
      `${BASE_URL}/api/accounts/login/`,
      { username, password }
    );
    return res.data;
  },

  /* =====================
     Clinics
  ===================== */
  async getClinics() {
    const res = await axios.get(
      `${BASE_URL}/api/data/clinics/`
    );
    return res.data.results;
  },

  /* =====================
     LLM MODELS 🔥 추가
  ===================== */
  async getLLMModels() {
    const res = await axios.get(
      `${BASE_URL}/api/ml/llm/models/`
    );
    return res.data.results ?? res.data;
  },

  /* =====================
     Review Generate (FIX)
  ===================== */
  async generateReview(payload) {
    console.log("📡 generateReview called");

    const res = await axios.post(
      `${BASE_URL}/api/ml/generate/review/`, // 🔥 수정됨
      payload,
      { timeout: 30000 }
    );

    console.log("📡 review response:", res.data);
    return res.data;
  },
};
