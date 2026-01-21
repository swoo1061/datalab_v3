console.log("posts_dashboard.js loaded");

const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";
const PLATFORM_PILLS = [
  { key: "all", label: "전체" },
  { key: "naver", label: "네이버" },
  { key: "gn_jp", label: "JP강남언니" },
  { key: "gangnam", label: "강남언니" },
  { key: "babytok", label: "바비톡" },
  { key: "todaktok", label: "토닥톡" },
  { key: "yeoshin", label: "여신티켓" },
  { key: "seongyesa", label: "성예사" },
  { key: "dadamo", label: "대다모" },
];

let currentClinicId = null;
let currentType = "all";
let currentPlatform = "all";
let currentMonth = "";
let currentQuery = "";
let postsCache = new Map();
let currentPosts = [];
let editingPostId = null;
let editingAll = false;
let selectedPostIds = new Set();


function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

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
  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
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
  selectedPostIds = new Set();

  let posts = [];
  const [opinions, reviews] = await Promise.all([fetchPosts("opinion"), fetchPosts("review")]);
  if (currentType === "opinion") posts = opinions;
  else if (currentType === "review") posts = reviews;
  else posts = [...opinions, ...reviews];

  posts.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  postsCache = new Map(posts.map((p) => [String(p.id), p]));
  currentPosts = posts;

  if (opinionCountEl) opinionCountEl.textContent = opinions.length;
  if (reviewCountEl) reviewCountEl.textContent = reviews.length;
  if (editingAll) toggleHeaderEditActions(true);
  renderPostList();
}

function renderPostList() {
  const list = document.getElementById("postList");
  if (!list) return;
  if (!currentPosts.length) {
    list.innerHTML = `<div class="table-muted">표시할 게시글이 없습니다.</div>`;
    return;
  }

  list.innerHTML = currentPosts.map((p) => (
    editingAll || String(p.id) === String(editingPostId)
      ? renderEditRow(p)
      : renderViewRow(p)
  )).join("");

  bindRowActions();
  bindSelectionActions();
  if (editingAll) {
    bindTypeSelects();
    bindSelectDefaults();
  }
}

function renderViewRow(p) {
  return `
    <div class="table-row" data-post-id="${p.id}">
      <span class="cell-check"><input type="checkbox" class="row-select" data-post-id="${p.id}" /></span>
      <span class="cell-meta">
        <span class="meta-date">${(p.updated_at || "").slice(0, 10)}</span>
        <span class="meta-type">${p.type === "review" ? "후기" : "여론"}</span>
      </span>
      <span class="cell-title">
        <span class="title-text">
          <a href="${p.url}" target="_blank" rel="noreferrer">${p.title}</a>
        </span>
        <a class="url-link" href="${p.url}" target="_blank" rel="noreferrer">${p.url}</a>
      </span>
      <span class="cell-metrics">
        <span class="metric-chip">조회 ${p.views ?? 0}</span>
        <span class="metric-chip">댓글 ${p.comments ?? 0}</span>
        <span class="metric-chip">쪽지 ${p.message_count ?? 0}</span>
      </span>
      <span class="cell-assignee">${p.assignee_name || "-"}</span>
      <span class="cell-platform">${p.platform_label || p.platform}</span>
    </div>
  `;
}

function renderEditRow(p) {
  const platformOptions = PLATFORM_PILLS.filter((pl) => pl.key !== "all")
    .map((pl) => `<option value="${pl.key}">${pl.label}</option>`)
    .join("");
  const subtypeVisible = p.type === "review";

  return `
    <div class="table-row editing" data-post-id="${p.id}">
      <span class="cell-check"><input type="checkbox" class="row-select" data-post-id="${p.id}" /></span>
      <span class="cell-meta">
        <input class="inline-input edit-date" type="date" value="${(p.published_at || p.updated_at || "").slice(0, 10)}" />
        <select class="inline-select edit-type">
          <option value="opinion" ${p.type === "opinion" ? "selected" : ""}>여론</option>
          <option value="review" ${p.type === "review" ? "selected" : ""}>후기</option>
        </select>
        <select class="inline-select edit-subtype" style="${subtypeVisible ? "" : "display:none;"}">
          <option value="text" ${p.review_subtype === "text" ? "selected" : ""}>텍스트</option>
          <option value="photo" ${p.review_subtype === "photo" ? "selected" : ""}>사진</option>
        </select>
      </span>
      <span class="cell-title">
        <input class="inline-input edit-title" value="${escapeHtml(p.title || "")}" />
        <input class="inline-input edit-url" value="${escapeHtml(p.url || "")}" />
        <span class="title-actions">
          <button class="table-delete" data-post-id="${p.id}">삭제</button>
        </span>
      </span>
      <span class="cell-metrics">
        <input class="inline-input edit-views" type="number" min="0" value="${p.views ?? 0}" />
        <input class="inline-input edit-comments" type="number" min="0" value="${p.comments ?? 0}" />
        <input class="inline-input edit-messages" type="number" min="0" value="${p.message_count ?? 0}" />
      </span>
      <span class="cell-assignee">${p.assignee_name || "-"}</span>
      <span class="cell-platform">
        <select class="inline-select edit-platform">
          ${platformOptions}
        </select>
      </span>
    </div>
  `;
}

function bindRowActions() {
  const list = document.getElementById("postList");
  if (!list) return;

  list.querySelectorAll(".table-delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const postId = btn.dataset.postId;
      if (!postId) return;
      if (!confirm("게시글을 삭제할까요?")) return;
      const headers = await buildAuthHeaders();
      const res = await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`, {
        method: "DELETE",
        credentials: "include",
        headers,
      });
      if (!res.ok) {
        alert("삭제 실패");
        return;
      }
      editingPostId = null;
      loadPosts();
    });
  });
}

function bindSelectionActions() {
  const list = document.getElementById("postList");
  if (!list) return;

  list.querySelectorAll(".row-select").forEach((checkbox) => {
    const postId = checkbox.dataset.postId;
    checkbox.checked = selectedPostIds.has(String(postId));
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedPostIds.add(String(postId));
      else selectedPostIds.delete(String(postId));
      syncSelectAllState();
      updateDeleteSelectedButton();
    });
  });

  const selectAll = document.getElementById("postSelectAll");
  if (selectAll) {
    selectAll.checked = selectedPostIds.size > 0 && selectedPostIds.size === currentPosts.length;
  }

  updateDeleteSelectedButton();
}

function syncSelectAllState() {
  const selectAll = document.getElementById("postSelectAll");
  if (!selectAll) return;
  selectAll.checked = selectedPostIds.size > 0 && selectedPostIds.size === currentPosts.length;
}

function updateDeleteSelectedButton() {
  const btn = document.getElementById("postDeleteSelectedBtn");
  if (!btn) return;
  btn.disabled = selectedPostIds.size === 0;
}

function toggleHeaderEditActions(editing) {
  const editBtn = document.getElementById("postEditAllBtn");
  const saveBtn = document.getElementById("postSaveAllBtn");
  const cancelBtn = document.getElementById("postCancelAllBtn");
  if (editBtn) editBtn.classList.toggle("hidden", editing);
  if (saveBtn) saveBtn.classList.toggle("hidden", !editing);
  if (cancelBtn) cancelBtn.classList.toggle("hidden", !editing);
}

function bindTypeSelects() {
  const list = document.getElementById("postList");
  if (!list) return;
  list.querySelectorAll(".edit-type").forEach((typeSelect) => {
    typeSelect.addEventListener("change", () => {
      const row = typeSelect.closest(".table-row");
      const subtypeSelect = row?.querySelector(".edit-subtype");
      if (!subtypeSelect) return;
      subtypeSelect.style.display = typeSelect.value === "review" ? "block" : "none";
    });
  });
}

function bindSelectDefaults() {
  const list = document.getElementById("postList");
  if (!list) return;
  list.querySelectorAll(".table-row.editing").forEach((row) => {
    const postId = row.dataset.postId;
    const post = postsCache.get(String(postId));
    if (!post) return;
    const platformSelect = row.querySelector(".edit-platform");
    if (platformSelect) {
      platformSelect.value = post.platform || "";
    }
  });
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

  const selectAll = document.getElementById("postSelectAll");
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) {
        selectedPostIds = new Set(currentPosts.map((p) => String(p.id)));
      } else {
        selectedPostIds = new Set();
      }
      renderPostList();
    });
  }

  document.getElementById("postDeleteSelectedBtn")?.addEventListener("click", async () => {
    if (!selectedPostIds.size) return;
    if (!confirm(`선택된 ${selectedPostIds.size}건을 삭제할까요?`)) return;
    const headers = await buildAuthHeaders();
    const results = await Promise.all(
      [...selectedPostIds].map((postId) =>
        fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`, {
          method: "DELETE",
          credentials: "include",
          headers,
        })
      )
    );
    if (results.some((res) => !res.ok)) {
      alert("일부 삭제 실패");
      return;
    }
    selectedPostIds = new Set();
    loadPosts();
  });

  document.getElementById("postEditAllBtn")?.addEventListener("click", async () => {
    editingAll = true;
    editingPostId = null;
    renderPostList();
    toggleHeaderEditActions(true);
  });

  document.getElementById("postCancelAllBtn")?.addEventListener("click", () => {
    editingAll = false;
    editingPostId = null;
    renderPostList();
    toggleHeaderEditActions(false);
  });

  document.getElementById("postSaveAllBtn")?.addEventListener("click", async () => {
    if (!editingAll) return;
    const list = document.getElementById("postList");
    if (!list) return;
    const rows = Array.from(list.querySelectorAll(".table-row.editing"));
    const headers = await buildAuthHeaders();
    const results = await Promise.all(rows.map(async (row) => {
      const postId = row.dataset.postId;
      const type = row.querySelector(".edit-type")?.value || "opinion";
      const payload = {
        type,
        review_subtype: row.querySelector(".edit-subtype")?.value || null,
        platform: row.querySelector(".edit-platform")?.value || "",
        title: row.querySelector(".edit-title")?.value || "",
        url: row.querySelector(".edit-url")?.value || "",
        views: Number(row.querySelector(".edit-views")?.value || 0),
        comments: Number(row.querySelector(".edit-comments")?.value || 0),
        message_count: Number(row.querySelector(".edit-messages")?.value || 0),
        published_at: row.querySelector(".edit-date")?.value || "",
      };
      if (type !== "review") payload.review_subtype = null;
      const res = await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
      return res.ok;
    }));
    if (results.some((ok) => !ok)) {
      alert("일부 저장 실패");
      return;
    }
    editingAll = false;
    toggleHeaderEditActions(false);
    loadPosts();
  });

  loadPosts();
}

document.addEventListener("DOMContentLoaded", initPostsDashboard);
