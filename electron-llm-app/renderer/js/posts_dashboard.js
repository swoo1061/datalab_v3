console.log("posts_dashboard.js loaded");

const API_BASE = "http://127.0.0.1:8000";
const PLATFORM_PILLS = [
  { key: "all", label: "전체" },
  { key: "naver", label: "네이버" },
  { key: "gn_jp", label: "JP강남언니" },
  { key: "gangnam", label: "강남언니" },
  { key: "babytok", label: "바비톡" },
  { key: "yeoshin", label: "여신티켓" },
  { key: "seongyesa", label: "성예사" },
  { key: "dadamo", label: "대다모" },
];

let currentClinicId = null;
let currentType = "all";
let currentPlatform = "all";
let currentMonth = "";
let currentQuery = "";

function monthKey() {
  if (currentMonth) return currentMonth;
  const d = new Date();
  currentMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  return currentMonth;
}

async function fetchClinics() {
  try {
    if (window.api?.getClinics) {
      return await window.api.getClinics();
    }
  } catch (e) {
    console.warn("getClinics failed", e);
  }
  return [];
}

async function fetchPosts(type) {
  const params = new URLSearchParams({
    type,
    platform: currentPlatform,
    month: monthKey(),
  });
  if (currentQuery) params.set("q", currentQuery);
  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function renderPlatformPills() {
  const root = document.getElementById("postPlatformPills");
  if (!root) return;
  root.innerHTML = PLATFORM_PILLS.map((p) => `
    <button class="platform-pill platform-${p.key} ${p.key === "all" ? "active" : ""}" data-platform="${p.key}">
      ${p.label}
    </button>
  `).join("");

  root.querySelectorAll(".platform-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentPlatform = btn.dataset.platform;
      root.querySelectorAll(".platform-pill").forEach((b) => b.classList.toggle("active", b === btn));
      loadPosts();
    });
  });
}

function bindTypePills() {
  const root = document.getElementById("postTypePills");
  if (!root) return;
  root.querySelectorAll(".type-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentType = btn.dataset.type || "all";
      root.querySelectorAll(".type-pill").forEach((b) => b.classList.toggle("active", b === btn));
      loadPosts();
    });
  });
}

async function loadPosts() {
  if (!currentClinicId) return;
  const list = document.getElementById("postList");
  const opinionCountEl = document.getElementById("opinionCount");
  const reviewCountEl = document.getElementById("reviewCount");
  if (list) list.innerHTML = `<div class="table-muted">불러오는 중...</div>`;

  let posts = [];
  const [opinions, reviews] = await Promise.all([fetchPosts("opinion"), fetchPosts("review")]);
  if (currentType === "opinion") posts = opinions;
  else if (currentType === "review") posts = reviews;
  else posts = [...opinions, ...reviews];

  posts.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));

  if (opinionCountEl) opinionCountEl.textContent = opinions.length;
  if (reviewCountEl) reviewCountEl.textContent = reviews.length;
  if (!list) return;
  if (!posts.length) {
    list.innerHTML = `<div class="table-muted">표시할 게시글이 없습니다.</div>`;
    return;
  }

  list.innerHTML = posts.map((p) => `
    <div class="table-row">
      <span>${p.type === "review" ? "후기" : "여론"}</span>
      <span>${p.platform_label || p.platform}</span>
      <span><a href="${p.url}" target="_blank" rel="noreferrer">${p.title}</a></span>
      <span><a class="url-link" href="${p.url}" target="_blank" rel="noreferrer">${p.url}</a></span>
      <span>${p.assignee_name || "-"}</span>
      <span>${p.comments ?? 0}</span>
      <span>${p.views ?? 0}</span>
      <span>${p.message_count ?? 0}</span>
      <span>${(p.updated_at || "").slice(0, 10)}</span>
    </div>
  `).join("");
}

async function initPostsDashboard() {
  const clinicSelect = document.getElementById("postClinicSelect");
  const monthInput = document.getElementById("postMonth");
  const searchInput = document.getElementById("postSearch");
  const toggleFiltersBtn = document.getElementById("toggleFiltersBtn");
  const filtersPanel = document.getElementById("postFiltersPanel");

  renderPlatformPills();
  bindTypePills();

  const clinics = await fetchClinics();
  const clinicIdFromQuery = new URLSearchParams(window.location.search).get("clinic_id");
  if (clinicSelect) {
    clinicSelect.innerHTML = clinics.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
    if (clinicIdFromQuery) clinicSelect.value = clinicIdFromQuery;
    clinicSelect.addEventListener("change", () => {
      currentClinicId = clinicSelect.value;
      loadPosts();
    });
  }

  if (monthInput) {
    monthInput.value = monthKey();
    monthInput.addEventListener("change", () => {
      currentMonth = monthInput.value;
      loadPosts();
    });
  }

  if (toggleFiltersBtn && filtersPanel) {
    toggleFiltersBtn.addEventListener("click", () => {
      filtersPanel.classList.toggle("hidden");
      toggleFiltersBtn.textContent = filtersPanel.classList.contains("hidden")
        ? "필터 열기"
        : "필터 닫기";
    });
  }

  if (searchInput) {
    searchInput.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      currentQuery = searchInput.value.trim();
      loadPosts();
    });
  }

  if (clinicSelect && clinics.length) {
    currentClinicId = clinicSelect.value;
  }

  loadPosts();
}

document.addEventListener("DOMContentLoaded", initPostsDashboard);
