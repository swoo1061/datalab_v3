const axios = require("axios");

module.exports = {
  async login(username, password) {
    const res = await axios.post(
      "http://localhost:8000/api/accounts/login/",
      { username, password }
    );
    return res.data;
  },

  async generateReview(payload) {
    console.log("📡 generateReview called"); // 디버깅용 로그

    const res = await axios.post(
      "http://localhost:8000/api/ml/review/",
      payload,
      { timeout: 30000 }
    );

    console.log("📡 review response:", res.data); // 디버깅용 로그
    return res.data;
  },

  async getClinics() {
  const axios = require("axios");

  const res = await axios.get(
    "http://localhost:8000/api/data/clinics/"
  );

  return res.data.results;
}
};
