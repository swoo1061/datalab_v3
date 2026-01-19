console.log("clinic_page.js loaded");

const API_BASE = "http://127.0.0.1:8000";

// ================================
// 상태
// ================================
let currentClinicId = null;
let currentMonth = getThisMonth();   // YYYY-MM
let currentType = "opinion";         // opinion | review
let currentPlatform = "all";         // all | naver | ...
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

  initAiIntakeForm();
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
  const sel = document.getElementById("monthFilter");
  if (!sel) return;
  sel.value = currentMonth;
  sel.onchange = () => {
    currentMonth = sel.value;
    loadPosts();
  };
}

function initAiIntakeForm() {
  const urlInput = document.getElementById("aiIntakeUrl");
  const titleInput = document.getElementById("aiIntakeTitle");
  const platformSelect = document.getElementById("aiIntakePlatform");
  const submitBtn = document.getElementById("aiIntakeSubmit");
  const reviewBtn = document.getElementById("aiIntakeReviewBtn");
  const statusEl = document.getElementById("aiIntakeStatus");
  const photoInput = document.getElementById("aiIntakePhotos");
  const photoHint = document.getElementById("aiIntakePhotoHint");
  const reviewMenu = document.querySelector(".ai-review-menu");

  if (!urlInput || !platformSelect || !submitBtn) return;

  if (!platformSelect.options.length) {
    platformSelect.innerHTML = `
      <option value="">플랫폼 선택</option>
      ${PLATFORM_PILLS.filter(p => p.key !== "all")
        .map(p => `<option value="${p.key}">${p.label}</option>`)
        .join("")}
    `;
  }

  submitBtn.onclick = async () => {
    const url = urlInput.value.trim();
    const platform = platformSelect.value;
    const title = (titleInput?.value || "").trim();

    if (!url || !platform) {
      if (statusEl) statusEl.textContent = "URL과 플랫폼을 입력하세요.";
      return;
    }

    const form = new FormData();
    form.append("url", url);
    form.append("platform", platform);
    form.append("title", title);
    form.append("auto_classify", "true");
    if (photoInput?.files?.length) {
      Array.from(photoInput.files).forEach((file) => {
        form.append("photos", file);
      });
    }

    if (statusEl) statusEl.textContent = "처리 중...";
    submitBtn.disabled = true;
    try {
      const res = await fetch(
        `${API_BASE}/api/data/clinics/${currentClinicId}/posts/`,
        {
          method: "POST",
          credentials: "include",
          body: form,
        }
      );

      if (!res.ok) {
        if (statusEl) statusEl.textContent = "저장 실패";
        return;
      }

      if (statusEl) statusEl.textContent = "저장 완료";
      urlInput.value = "";
      if (titleInput) titleInput.value = "";
      if (photoInput) photoInput.value = "";
      if (photoHint) photoHint.textContent = "선택된 파일 없음";
      await loadPosts();
    } catch (e) {
      console.error("ai intake error", e);
      if (statusEl) statusEl.textContent = "저장 실패";
    } finally {
      submitBtn.disabled = false;
    }
  };

  if (reviewBtn) {
    reviewBtn.onclick = (e) => {
      e.stopPropagation();
      if (reviewMenu) reviewMenu.classList.toggle("open");
    };
  }

  if (reviewMenu) {
    reviewMenu.querySelectorAll(".menu-item").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const type = btn.dataset.type;
        reviewMenu.classList.remove("open");
        if (type === "gangnam") {
          window.location.href = `gangnam_review.html?clinic_id=${currentClinicId}`;
          return;
        }
        if (type === "babytok") {
          window.location.href = `review.html?clinic_id=${currentClinicId}&platform=babytok`;
          return;
        }
        if (type === "yeoshin") {
          window.location.href = `review.html?clinic_id=${currentClinicId}&platform=yeoshin`;
          return;
        }
        window.location.href = `review.html?clinic_id=${currentClinicId}`;
      });
    });

    document.addEventListener("click", () => {
      reviewMenu.classList.remove("open");
    });
  }

  if (photoInput && photoHint) {
    photoInput.addEventListener("change", () => {
      const count = photoInput.files ? photoInput.files.length : 0;
      photoHint.textContent = count ? `${count}개 파일 선택됨` : "선택된 파일 없음";
    });
  }
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
      <div>
        <input class="post-input message-input" type="number" min="0" value="${p.message_count ?? 0}" data-post-id="${p.id}" />
      </div>
      <div class="post-status">${p.status}</div>
      <div class="post-updated">${fmtDateTime(p.updated_at)}</div>
    </div>
  `).join("");

  bindMessageInputs();
}

function bindMessageInputs() {
  document.querySelectorAll(".message-input").forEach((input) => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        input.blur();
      }
    });
    input.addEventListener("blur", async () => {
      const postId = input.dataset.postId;
      const value = Number(input.value || 0);
      if (!postId) return;
      await updatePostMessageCount(postId, value);
    });
  });
}

async function updatePostMessageCount(postId, messageCount) {
  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`;
  try {
    await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_count: messageCount }),
    });
  } catch (e) {
    console.error("message count update failed", e);
  }
}

function getPostDate(post) {
  const raw = post.published_at || post.updated_at || "";
  if (!raw) return "";
  return raw.slice(0, 10);
}

async function fetchPostsByMonth(type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month: currentMonth,
  });

  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function reloadClinicPage() {
  loadPosts();
}

// ================================
// 시작
// ================================
document.addEventListener("DOMContentLoaded", initClinicPage);
