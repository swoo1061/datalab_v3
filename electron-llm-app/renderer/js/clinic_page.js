console.log("clinic_page.js loaded");

const API_BASE = "http://127.0.0.1:8000";

// ================================
// 상태
// ================================
let currentClinicId = null;
let currentMonth = getThisMonth();   // YYYY-MM
let currentType = "opinion";         // opinion | review
let currentPlatform = "all";         // all | naver | ...
let currentAssignee = "all";         // all | user_id
let currentQuery = "";

// ================================
// 플랫폼 정의
// ================================
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

// ================================
// 유틸
// ================================
function getClinicIdFromQuery() {
  return new URLSearchParams(window.location.search).get("clinic_id");
}

function getThisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function fmtDateTime(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", { hour12: false });
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// ================================
// 초기 로드
// ================================
async function initClinicPage() {
  currentClinicId = getClinicIdFromQuery();
  if (!currentClinicId) {
    alert("clinic_id 없음");
    return;
  }

  renderPlatformPills();
  initMonthSelect();
  bindSearch();

  await loadClinicInfo();
  await loadAssignees();   // ⭐ 추가
  await loadPosts();
}

// ================================
// 병원 정보
// ================================
async function loadClinicInfo() {
  const data = await window.api.getClinicDetail(currentClinicId);
  const c = data?.clinic || {};

  const titleEl = document.getElementById("clinicTitle");
  const metaEl = document.getElementById("clinicMeta");

  if (titleEl) {
    titleEl.innerText = c.name || "병원";
  }

  if (metaEl) {
    metaEl.innerText = `${c.location || ""} · ${c.hours || ""}`.trim();
  }
}

// ================================
// 담당자 필터
// ================================
async function loadAssignees() {
  const root = document.getElementById("assigneePills");
  if (!root) return;

  const res = await fetch(
    `${API_BASE}/api/data/clinics/${currentClinicId}/assignees/`,
    { credentials: "include" }
  );
  const list = await res.json();

  root.innerHTML = `
    <button class="pill active" data-assignee="all"
            onclick="setAssignee('all')">전체</button>
    ${list.map(a => `
      <button class="pill"
              data-assignee="${a.id}"
              onclick="setAssignee('${a.id}')">
        ${a.name}
      </button>
    `).join("")}
  `;
}

function setAssignee(userId) {
  currentAssignee = userId;

  document.querySelectorAll("#assigneePills .pill").forEach(el => {
    el.classList.toggle("active", el.dataset.assignee === userId);
  });

  loadPosts();
}

window.setAssignee = setAssignee;

// ================================
// 플랫폼 / 타입 / 검색
// ================================
function renderPlatformPills() {
  const root = document.getElementById("platformPills");
  if (!root) return;

  root.innerHTML = PLATFORM_PILLS.map(p => `
    <button class="pill ${p.key === "all" ? "active" : ""}"
            data-platform="${p.key}"
            onclick="setPlatform('${p.key}')">
      ${p.label}
    </button>
  `).join("");
}

function setPlatform(key) {
  currentPlatform = key;

  document.querySelectorAll("#platformPills .pill").forEach(el => {
    el.classList.toggle("active", el.dataset.platform === key);
  });

  loadPosts();
}

function setPostType(type) {
  currentType = type;

  document.querySelectorAll(".seg-tab").forEach(el => {
    el.classList.toggle("active", el.dataset.type === type);
  });

  loadPosts();
}

function bindSearch() {
  const el = document.getElementById("postSearch");
  if (!el) return;

  el.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      currentQuery = el.value.trim();
      loadPosts();
    }
  });
}

function initMonthSelect() {
  const sel = document.getElementById("monthSelect");
  if (!sel) return;

  const now = new Date();
  const months = [];

  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  }

  sel.innerHTML = months.map(m =>
    `<option value="${m}" ${m === currentMonth ? "selected" : ""}>${m}</option>`
  ).join("");

  sel.onchange = () => {
    currentMonth = sel.value;
    loadPosts();
  };
}

// ================================
// 게시글 로드
// ================================
async function loadPosts() {
  const root = document.getElementById("postList");
  if (!root) return;

  root.innerHTML = `<div class="muted">불러오는 중...</div>`;

  const params = new URLSearchParams({
    type: currentType,
    platform: currentPlatform,
    month: currentMonth,
  });

  if (currentAssignee !== "all") {
    params.set("assignee", currentAssignee);
  }

  if (currentQuery) {
    params.set("q", currentQuery);
  }

  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;

  const res = await fetch(url, { credentials: "include" });
  const data = await res.json();

  if (!data.results || data.results.length === 0) {
    root.innerHTML = `<div class="muted">표시할 게시글이 없습니다.</div>`;
    return;
  }

  root.innerHTML = data.results.map(p => `
    <div class="post-row">
      <div class="post-platform">${p.platform}</div>
      <div class="post-title">
        <a href="${p.url}" target="_blank">${escapeHtml(p.title)}</a>
      </div>
      <div class="post-num">${p.views}</div>
      <div class="post-num">${p.comments}</div>
      <div class="post-status">${p.status}</div>
      <div class="post-updated">${fmtDateTime(p.updated_at)}</div>
    </div>
  `).join("");
}

// ================================
// 시작
// ================================
document.addEventListener("DOMContentLoaded", initClinicPage);
