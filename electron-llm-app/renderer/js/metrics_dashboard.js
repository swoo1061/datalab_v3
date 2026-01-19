console.log("metrics_dashboard.js loaded");

const API_BASE = "http://127.0.0.1:8000";
let currentType = "all";

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function toMonthValue() {
  const input = document.getElementById("detailMonth");
  if (!input) return "";
  if (!input.value) {
    const d = new Date();
    input.value = monthKey(d);
  }
  return input.value;
}

async function fetchClinics() {
  try {
    if (window.api?.getClinics) {
      return await window.api.getClinics();
    }
  } catch (e) {
    console.warn("getClinics failed", e);
  }

  if (Array.isArray(window.clinics)) {
    return window.clinics.map((c) => ({ id: c.id, name: c.name }));
  }

  return [];
}

async function fetchClinicPosts(clinicId, month, type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month,
  });
  const url = `${API_BASE}/api/data/clinics/${clinicId}/posts/?${params}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function sumMetric(posts, field) {
  return posts.reduce((acc, p) => acc + Number(p[field] || 0), 0);
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("ko-KR");
}

function renderSummary(current, prev, split) {
  const fields = [
    { key: "posts", el: "summaryPosts", delta: "summaryPostsDelta" },
    { key: "opinion_posts", el: "summaryOpinionPosts", delta: "summaryOpinionPostsDelta" },
    { key: "review_posts", el: "summaryReviewPosts", delta: "summaryReviewPostsDelta" },
    { key: "comments", el: "summaryComments", delta: "summaryCommentsDelta" },
    { key: "views", el: "summaryViews", delta: "summaryViewsDelta" },
    { key: "messages", el: "summaryMessages", delta: "summaryMessagesDelta" },
  ];

  fields.forEach((f) => {
    const value = split[f.key] ?? current[f.key];
    const prevValue = split[`prev_${f.key}`] ?? prev[f.key];
    const diff = value - prevValue;
    const rate = prevValue ? ((diff / prevValue) * 100).toFixed(1) : "0.0";
    const sign = diff >= 0 ? "+" : "";
    const el = document.getElementById(f.el);
    const deltaEl = document.getElementById(f.delta);
    if (el) el.textContent = formatNumber(value);
    if (deltaEl) deltaEl.textContent = `${sign}${formatNumber(diff)} (${sign}${rate}%)`;
  });

  const opinionCard = document.getElementById("summaryOpinionPosts")?.closest(".summary-card");
  const reviewCard = document.getElementById("summaryReviewPosts")?.closest(".summary-card");
  if (currentType === "opinion") {
    if (opinionCard) opinionCard.style.display = "none";
    if (reviewCard) reviewCard.style.display = "none";
  } else if (currentType === "review") {
    if (opinionCard) opinionCard.style.display = "none";
    if (reviewCard) reviewCard.style.display = "none";
  } else {
    if (opinionCard) opinionCard.style.display = "";
    if (reviewCard) reviewCard.style.display = "";
  }
}

function renderTrend(months) {
  const root = document.getElementById("trendBars");
  if (!root) return;
  const max = Math.max(...months.map((m) => m.score), 1);
  root.innerHTML = months.map((m) => `
    <div class="spark-item">
      <div class="spark-bar"><span style="height:${(m.score / max) * 100}%"></span></div>
      <div>${m.label}</div>
    </div>
  `).join("");
}

function renderCompare(current, prev, split, type) {
  const root = document.getElementById("compareList");
  if (!root) return;
  const items = [
    { label: "게시글", curr: current.posts, prev: prev.posts },
    ...(type === "all"
      ? [
          { label: "여론 게시글", curr: split.opinion_posts, prev: split.prev_opinion_posts },
          { label: "후기 게시글", curr: split.review_posts, prev: split.prev_review_posts },
        ]
      : []),
    { label: "댓글", curr: current.comments, prev: prev.comments },
    { label: "조회수", curr: current.views, prev: prev.views },
    { label: "쪽지", curr: current.messages, prev: prev.messages },
  ];
  root.innerHTML = items.map((item) => {
    const diff = item.curr - item.prev;
    const sign = diff >= 0 ? "+" : "";
    return `
      <div class="compare-item">
        <span>${item.label}</span>
        <span class="compare-value">${formatNumber(item.curr)} (${sign}${formatNumber(diff)})</span>
      </div>
    `;
  }).join("");
}

function renderForecast(current, prev) {
  const predict = (value, prevValue) => Math.max(0, value + (value - prevValue));
  const next = {
    posts: predict(current.posts, prev.posts),
    comments: predict(current.comments, prev.comments),
    views: predict(current.views, prev.views),
    messages: predict(current.messages, prev.messages),
  };

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = formatNumber(value);
  };

  setText("forecastPosts", next.posts);
  setText("forecastComments", next.comments);
  setText("forecastViews", next.views);
  setText("forecastMessages", next.messages);
}


async function loadDetail() {
  const clinicSelect = document.getElementById("detailClinicSelect");
  const month = toMonthValue();
  if (!clinicSelect || !month) return;

  const clinicId = clinicSelect.value;
  const [year, mon] = month.split("-").map(Number);
  const currentDate = new Date(year, mon - 1, 1);
  const prevDate = new Date(year, mon - 2, 1);

  const currentMonth = monthKey(currentDate);
  const prevMonth = monthKey(prevDate);

  const [opinions, reviews, prevOpinions, prevReviews] = await Promise.all([
    fetchClinicPosts(clinicId, currentMonth, "opinion"),
    fetchClinicPosts(clinicId, currentMonth, "review"),
    fetchClinicPosts(clinicId, prevMonth, "opinion"),
    fetchClinicPosts(clinicId, prevMonth, "review"),
  ]);

  const currentPostsAll = [...opinions, ...reviews];
  const prevPostsAll = [...prevOpinions, ...prevReviews];
  const currentPosts = currentType === "opinion"
    ? opinions
    : currentType === "review"
      ? reviews
      : currentPostsAll;
  const prevPosts = currentType === "opinion"
    ? prevOpinions
    : currentType === "review"
      ? prevReviews
      : prevPostsAll;

  const current = {
    posts: currentPosts.length,
    comments: sumMetric(currentPosts, "comments"),
    views: sumMetric(currentPosts, "views"),
    messages: sumMetric(currentPosts, "message_count"),
  };
  const prev = {
    posts: prevPosts.length,
    comments: sumMetric(prevPosts, "comments"),
    views: sumMetric(prevPosts, "views"),
    messages: sumMetric(prevPosts, "message_count"),
  };

  const months = [prevMonth, currentMonth];
  const trend = [];
  for (let i = 5; i >= 0; i -= 1) {
    const d = new Date(year, mon - 1 - i, 1);
    const key = monthKey(d);
    const [o, r] = await Promise.all([
      fetchClinicPosts(clinicId, key, "opinion"),
      fetchClinicPosts(clinicId, key, "review"),
    ]);
    const posts = currentType === "opinion"
      ? o
      : currentType === "review"
        ? r
        : [...o, ...r];
    trend.push({
      label: `${String(d.getMonth() + 1).padStart(2, "0")}월`,
      score: sumMetric(posts, "comments") + sumMetric(posts, "views") + sumMetric(posts, "message_count"),
    });
  }

  const split = {
    opinion_posts: opinions.length,
    review_posts: reviews.length,
    prev_opinion_posts: prevOpinions.length,
    prev_review_posts: prevReviews.length,
  };

  renderSummary(current, prev, split);
  renderCompare(current, prev, split, currentType);
  renderForecast(current, prev);
  renderTrend(trend);
}

function bindTypePills() {
  const root = document.getElementById("detailTypePills");
  if (!root) return;
  root.querySelectorAll(".type-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentType = btn.dataset.type || "all";
      root.querySelectorAll(".type-pill").forEach((b) => b.classList.toggle("active", b === btn));
      loadDetail();
    });
  });
}

async function initDetail() {
  const clinicSelect = document.getElementById("detailClinicSelect");
  if (!clinicSelect) return;

  const clinics = await fetchClinics();
  clinicSelect.innerHTML = clinics.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
  clinicSelect.addEventListener("change", loadDetail);

  const monthInput = document.getElementById("detailMonth");
  if (monthInput) monthInput.addEventListener("change", loadDetail);

  bindTypePills();
  loadDetail();
}

document.addEventListener("DOMContentLoaded", initDetail);
