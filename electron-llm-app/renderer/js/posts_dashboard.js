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
let currentType = "opinion";
let currentPlatform = "all";
let currentMonth = "";
let currentQuery = "";
let currentSort = "latest";
let postsCache = new Map();
let currentPosts = [];
let pagePosts = [];
let currentPage = 1;
const PAGE_SIZE = 8;
let editingPostId = null;
let editingAll = false;
let selectedPostIds = new Set();

const askConfirm = async (message) => {
  if (typeof window.appConfirm === "function") {
    return window.appConfirm(message);
  }
  return confirm(message);
};



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

function formatMonthLabel(value) {
  if (!value) return "-";
  const [y, m] = value.split("-").map(Number);
  if (!y || !m) return value;
  return `${y}년 ${m}월`;
}

function shiftMonth(value, delta) {
  const [y, m] = value.split("-").map(Number);
  if (!y || !m) return value;
  const next = new Date(y, m - 1 + delta, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}

function getPostDateValue(post) {
  return post.published_at || post.created_at || post.updated_at || "";
}

function sortPosts(list) {
  if (currentSort === "oldest") {
    return list.sort((a, b) => getPostDateValue(a).localeCompare(getPostDateValue(b)));
  }
  return list.sort((a, b) => getPostDateValue(b).localeCompare(getPostDateValue(a)));
}

function setMonth(value) {
  currentMonth = value;
  const monthInput = document.getElementById("postMonth");
  const monthLabel = document.getElementById("postMonthLabel");
  if (monthInput) monthInput.value = value;
  if (monthLabel) monthLabel.textContent = formatMonthLabel(value);
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

async function fetchPosts(type, { month } = {}) {
  const params = new URLSearchParams({
    type,
    platform: currentPlatform,
  });
  const monthValue = month === undefined ? monthKey() : month;
  if (monthValue) params.set("month", monthValue);
  if (currentQuery) params.set("q", currentQuery);
  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;
  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
  if (!res.ok) return { results: [], count: 0 };
  const data = await res.json();
  return {
    results: data.results || [],
    count: data.count ?? (data.results ? data.results.length : 0),
  };
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
  const activeBtn = root.querySelector(".type-pill.active");
  if (activeBtn) currentType = activeBtn.dataset.type || "opinion";
  root.querySelectorAll(".type-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentType = btn.dataset.type || "all";
      root.querySelectorAll(".type-pill").forEach((b) => b.classList.toggle("active", b === btn));
      loadPosts();
    });
  });
}

function enableDragScroll(container) {
  if (!container) return;
  let isDown = false;
  let startX = 0;
  let startY = 0;
  let scrollLeft = 0;
  let scrollTop = 0;

  const isInteractive = (target) =>
    target.closest("a, button, input, select, textarea, label");

  container.classList.add("drag-scroll");
    container.addEventListener("mousedown", (e) => {
      if (document.body.classList.contains("editing-posts")) return;
      if (e.button !== 0) return;
      if (isInteractive(e.target)) return;
      isDown = true;
    startX = e.pageX;
    startY = e.pageY;
    scrollLeft = container.scrollLeft;
    scrollTop = container.scrollTop;
      container.classList.add("dragging");
      document.body.classList.add("drag-scroll-active");
    });

  window.addEventListener("mousemove", (e) => {
    if (!isDown) return;
    const dx = e.pageX - startX;
    const dy = e.pageY - startY;
    container.scrollLeft = scrollLeft - dx;
    container.scrollTop = scrollTop - dy;
  });

  window.addEventListener("mouseup", () => {
    if (!isDown) return;
    isDown = false;
    container.classList.remove("dragging");
    document.body.classList.remove("drag-scroll-active");
  });
}

async function loadPosts() {
  if (!currentClinicId) return;
  const list = document.getElementById("postList");
  const opinionCountEl = document.getElementById("opinionCount");
  const reviewCountEl = document.getElementById("reviewCount");
  const opinionTotalEl = document.getElementById("opinionTotalCount");
  const reviewTotalEl = document.getElementById("reviewTotalCount");
  if (list) list.innerHTML = `<div class="table-muted">불러오는 중...</div>`;
  selectedPostIds = new Set();

  let posts = [];
  const [
    { results: opinionResults, count: opinionMonthCount },
    { results: reviewResults, count: reviewMonthCount },
    { count: opinionTotalCount },
    { count: reviewTotalCount },
  ] = await Promise.all([
    fetchPosts("opinion"),
    fetchPosts("review"),
    fetchPosts("opinion", { month: null }),
    fetchPosts("review", { month: null }),
  ]);
  if (currentType === "opinion") posts = opinionResults;
  else if (currentType === "review") posts = reviewResults;
  else posts = [...opinionResults, ...reviewResults];

  sortPosts(posts);
  postsCache = new Map(posts.map((p) => [String(p.id), p]));
  currentPosts = posts;

  if (opinionCountEl) opinionCountEl.textContent = opinionMonthCount;
  if (reviewCountEl) reviewCountEl.textContent = reviewMonthCount;
  if (opinionTotalEl) opinionTotalEl.textContent = opinionTotalCount;
  if (reviewTotalEl) reviewTotalEl.textContent = reviewTotalCount;
  if (editingAll) toggleHeaderEditActions(true);
  currentPage = 1;
  renderPostList();
}

function renderPostList() {
  const list = document.getElementById("postList");
  const pager = document.getElementById("postPager");
  if (!list) return;
  if (!currentPosts.length) {
    list.innerHTML = `<div class="table-muted">표시할 게시글이 없습니다.</div>`;
    if (pager) pager.innerHTML = "";
    return;
  }
  const table = list.closest(".post-table");
  const isEditing = editingAll || Boolean(editingPostId);
  document.body.classList.toggle("editing-posts", isEditing);
  if (table) {
    table.classList.remove("card-view");
    table.classList.toggle("editing-view", isEditing);
  }
  list.classList.remove("card-view");
  list.classList.toggle("editing-view", isEditing);
  list.classList.toggle("edit-only", isEditing);
  if (isEditing) {
    document.body.classList.remove("drag-scroll-active");
    document.body.classList.remove("resizing-panel");
    document.querySelectorAll(".dragging").forEach((el) => el.classList.remove("dragging"));
  }

  const totalPages = Math.max(1, Math.ceil(currentPosts.length / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  const start = (currentPage - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  pagePosts = currentPosts.slice(start, end);

  list.innerHTML = pagePosts.map((p) => (
    editingAll || String(p.id) === String(editingPostId)
      ? renderEditRow(p)
      : renderViewRow(p)
  )).join("");

  renderPager(totalPages);
  bindRowActions();
  bindPhotoButtons();
  bindSelectionActions();
  if (editingAll) {
    bindTypeSelects();
    bindSelectDefaults();
  }
}

function renderPager(totalPages) {
  const pager = document.getElementById("postPager");
  if (!pager) return;
  if (totalPages <= 1) {
    pager.innerHTML = "";
    return;
  }

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);
  pager.innerHTML = `
    <button class="pager-btn" data-page="${Math.max(1, currentPage - 1)}" ${currentPage === 1 ? "disabled" : ""}>이전</button>
    ${pages.map((page) => `
      <button class="pager-btn ${page === currentPage ? "active" : ""}" data-page="${page}">
        ${page}
      </button>
    `).join("")}
    <button class="pager-btn" data-page="${Math.min(totalPages, currentPage + 1)}" ${currentPage === totalPages ? "disabled" : ""}>다음</button>
  `;

  pager.querySelectorAll(".pager-btn[data-page]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const page = Number(btn.dataset.page || "1");
      if (!page || page === currentPage) return;
      currentPage = page;
      renderPostList();
    });
  });
}

function renderViewRow(p) {
  const dateLabel = (p.published_at || p.created_at || p.updated_at || "").slice(0, 10);
  const typeLabel = p.type === "review" ? "후기" : "여론";
  const reviewSubtypeLabel = p.review_subtype_label
    || (p.review_subtype === "photo" ? "사진"
      : p.review_subtype === "text" ? "텍스트"
        : p.review_subtype === "consultation" ? "상담" : "");
  const opinionSubtypeLabel = p.opinion_subtype_label
    || (p.opinion_subtype === "concern" ? "고민"
      : p.opinion_subtype === "hand" ? "손품"
        : p.opinion_subtype === "foot" ? "발품" : "고민");
  const titleHint = String(p.title || "").toLowerCase();
  const fallbackReviewSubtype = p.type === "review" && !p.review_subtype
    ? (titleHint.includes("상담") ? "상담"
      : (Array.isArray(p.photos) && p.photos.length ? "사진" : "텍스트"))
    : "";
  const subtypeLabel = p.type === "review" ? (reviewSubtypeLabel || fallbackReviewSubtype) : opinionSubtypeLabel;
  const typeDisplay = subtypeLabel ? `${typeLabel}/${subtypeLabel}` : typeLabel;
  const platformLabel = p.platform_label || p.platform || "-";
  const photoUrls = Array.isArray(p.photos)
    ? p.photos.map((photo) => photo?.url || photo).filter(Boolean)
    : [];
  const photoAttr = photoUrls.length
    ? `data-photos="${encodeURIComponent(JSON.stringify(photoUrls))}"`
    : "";
  const photoButton = photoUrls.length
    ? `<button class="post-photo-btn" ${photoAttr}>사진</button>`
    : "";
  return `
    <div class="table-row" data-post-id="${p.id}">
      <span class="cell-check"></span>
      <span class="cell-meta">
        <span class="meta-date">${dateLabel}</span>
        <span class="meta-type">${typeDisplay}</span>
      </span>
      <span class="cell-title">
        <a href="${p.url}" target="_blank" rel="noreferrer">${p.title}</a>
        <a class="url-link" href="${p.url}" target="_blank" rel="noreferrer">${p.url}</a>
      </span>
      <span class="cell-metrics">
        <span class="metric-chip">조회 ${p.views ?? 0}</span>
        <span class="metric-chip">댓글 ${p.comments ?? 0}</span>
        <span class="metric-chip">쪽지 ${p.message_count ?? 0}</span>
      </span>
      <span class="cell-assignee">${p.assignee_name || "-"}</span>
      <span class="cell-platform">${platformLabel}${photoButton ? ` ${photoButton}` : ""}</span>
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
      <span class="cell-check edit-only"><input type="checkbox" class="row-select" data-post-id="${p.id}" /></span>
      <span class="cell-meta">
        <input class="inline-input edit-date" type="date" value="${(p.published_at || p.updated_at || "").slice(0, 10)}" />
        <select class="inline-select edit-type">
          <option value="opinion" ${p.type === "opinion" ? "selected" : ""}>여론</option>
          <option value="review" ${p.type === "review" ? "selected" : ""}>후기</option>
        </select>
        <select class="inline-select edit-subtype" style="${subtypeVisible ? "" : "display:none;"}">
          <option value="text" ${p.review_subtype === "text" ? "selected" : ""}>텍스트</option>
          <option value="photo" ${p.review_subtype === "photo" ? "selected" : ""}>사진</option>
          <option value="consultation" ${p.review_subtype === "consultation" ? "selected" : ""}>상담</option>
        </select>
      </span>
      <span class="cell-title">
        <input class="inline-input edit-title" value="${escapeHtml(p.title || "")}" />
        <input class="inline-input edit-url" value="${escapeHtml(p.url || "")}" />

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
        if (!(await askConfirm("게시글을 삭제할까요?"))) {
          window.resetInteractionState?.();
          return;
        }
        const headers = await buildAuthHeaders();
        const res = await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`, {
          method: "DELETE",
          credentials: "include",
          headers,
        });
        if (!res.ok) {
          window.showAlert?.("삭제 실패");
          window.resetInteractionState?.();
          return;
        }
        editingPostId = null;
        loadPosts();
        window.resetInteractionState?.();
      });
    });
  }

function bindPhotoButtons() {
  const list = document.getElementById("postList");
  if (!list) return;
  list.querySelectorAll(".post-photo-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const raw = btn.dataset.photos || "";
      if (!raw) return;
      try {
        const urls = JSON.parse(decodeURIComponent(raw));
        openPhotoModal(urls);
      } catch (err) {
        console.warn("photo parse failed", err);
      }
    });
  });
}

function openPhotoModal(urls) {
  const modal = document.getElementById("postPhotoModal");
  const list = document.getElementById("postPhotoList");
  if (!modal || !list) return;
  const safeUrls = Array.isArray(urls) ? urls.filter(Boolean) : [];
  if (!safeUrls.length) return;
  const size = Math.max(120, Math.min(220, Math.floor(520 / safeUrls.length)));
  list.style.setProperty("--photo-size", `${size}px`);
  list.innerHTML = safeUrls.map((url) => `<img src="${url}" alt="photo" />`).join("");
  modal.classList.remove("hidden");
}

function initPhotoModal() {
  const modal = document.getElementById("postPhotoModal");
  if (!modal) return;
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) {
      modal.classList.add("hidden");
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      modal.classList.add("hidden");
    }
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
    const pageIds = pagePosts.map((p) => String(p.id));
    const checkedCount = pageIds.filter((id) => selectedPostIds.has(id)).length;
    selectAll.checked = pageIds.length > 0 && checkedCount === pageIds.length;
  }

  updateDeleteSelectedButton();
}

function syncSelectAllState() {
  const selectAll = document.getElementById("postSelectAll");
  if (!selectAll) return;
  const pageIds = pagePosts.map((p) => String(p.id));
  const checkedCount = pageIds.filter((id) => selectedPostIds.has(id)).length;
  selectAll.checked = pageIds.length > 0 && checkedCount === pageIds.length;
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
  const deleteBtn = document.getElementById("postDeleteSelectedBtn");
  if (editBtn) editBtn.classList.toggle("hidden", editing);
  if (saveBtn) saveBtn.classList.toggle("hidden", !editing);
  if (cancelBtn) cancelBtn.classList.toggle("hidden", !editing);
  if (deleteBtn) deleteBtn.classList.toggle("hidden", !editing);
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
  const sortSelect = document.getElementById("postSortSelect");
  const sortChips = document.querySelectorAll("#postSortChips .sort-chip");
  const monthInput = document.getElementById("postMonth");
  const monthPrev = document.getElementById("postMonthPrev");
  const monthNext = document.getElementById("postMonthNext");
  const searchInput = document.getElementById("postSearch");
  const toggleFiltersBtn = document.getElementById("toggleFiltersBtn");
  const filtersPanel = document.getElementById("postFiltersPanel");
  const tableBody = document.querySelector(".post-table .card-bd");

  renderPlatformPills();
  bindTypePills();
  initPhotoModal();
  enableDragScroll(tableBody);

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
  if (sortSelect) {
    sortSelect.value = currentSort;
    sortSelect.addEventListener("change", () => {
      currentSort = sortSelect.value || "latest";
      loadPosts();
    });
  }
  sortChips.forEach((chip) => {
    chip.classList.toggle("active", (chip.dataset.sort || "latest") === currentSort);
    chip.addEventListener("click", () => {
      currentSort = chip.dataset.sort || "latest";
      sortChips.forEach((item) => {
        item.classList.toggle("active", item === chip);
      });
      if (sortSelect) sortSelect.value = currentSort;
      loadPosts();
    });
  });

  if (monthInput) {
    setMonth(monthKey());
    monthInput.addEventListener("change", () => {
      setMonth(monthInput.value);
      loadPosts();
    });
  }
  if (monthPrev) {
    monthPrev.addEventListener("click", () => {
      setMonth(shiftMonth(monthKey(), -1));
      loadPosts();
    });
  }
  if (monthNext) {
    monthNext.addEventListener("click", () => {
      setMonth(shiftMonth(monthKey(), 1));
      loadPosts();
    });
  }

  if (toggleFiltersBtn && filtersPanel) {
    toggleFiltersBtn.addEventListener("click", () => {
      filtersPanel.classList.toggle("hidden");
      toggleFiltersBtn.classList.toggle("active", !filtersPanel.classList.contains("hidden"));
      if (!filtersPanel.classList.contains("hidden")) {
        const btnRect = toggleFiltersBtn.getBoundingClientRect();
        const parentRect = toggleFiltersBtn.parentElement?.getBoundingClientRect();
        if (parentRect) {
          const centerX = btnRect.left + btnRect.width / 2;
          filtersPanel.style.left = `${centerX - parentRect.left}px`;
        }
      }
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
        pagePosts.forEach((p) => selectedPostIds.add(String(p.id)));
      } else {
        pagePosts.forEach((p) => selectedPostIds.delete(String(p.id)));
      }
      renderPostList();
    });
  }

  document.getElementById("postDeleteSelectedBtn")?.addEventListener("click", async () => {
    if (!selectedPostIds.size) return;
    if (!(await askConfirm(`선택된 ${selectedPostIds.size}건을 삭제할까요?`))) {
      window.resetInteractionState?.();
      return;
    }
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
        window.showAlert?.("일부 삭제 실패");
        window.resetInteractionState?.();
        return;
      }
      selectedPostIds = new Set();
      loadPosts();
      window.resetInteractionState?.();
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
      window.showAlert?.("일부 저장 실패");
      return;
    }
    editingAll = false;
    toggleHeaderEditActions(false);
    loadPosts();
  });

  loadPosts();
}

document.addEventListener("DOMContentLoaded", initPostsDashboard);
