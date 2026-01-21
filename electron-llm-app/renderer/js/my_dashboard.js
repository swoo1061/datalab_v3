console.log("my_dashboard.js loaded");
const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

// ================================
// (기존) 로컬 즐겨찾기 - 유지
// ================================
function getCurrentUserId() {
  return "user_demo"; // 공용과 동일(기존 유지)
}

function getFavorites() {
  const key = `favoriteClinics::${getCurrentUserId()}`;
  return JSON.parse(localStorage.getItem(key) || "[]");
}

// ================================
// ✅ 서버 즐겨찾기 기반 “나의 대시보드”
// ================================
async function getFavoritesFromServer() {
  try {
    const list = await window.api.getFavorites();
    return (list || []).map((f) => Number(f.clinic_id));
  } catch (e) {
    console.warn("getFavoritesFromServer failed", e);
    return [];
  }
}

async function renderMyDashboard() {
  const gridId = "myClinicGrid";

  try {
    // 1️⃣ 서버에서 즐겨찾기 ID 목록
    const favorites = await window.api.getFavorites();
    const favoriteIds = favorites.map(f => Number(f.clinic_id));

    if (favoriteIds.length === 0) {
      document.getElementById(gridId).innerHTML =
        `<p class="muted">즐겨찾기한 병원이 없습니다.</p>`;
      return;
    }

    // 2️⃣ 공용 clinics에서 필터링
    const myClinics = clinics
      .filter(c => favoriteIds.includes(Number(c.id)))
      .map(c => ({
        ...c,
        isFavorite: true, // 개인 대시보드는 전부 즐겨찾기
      }));

    // 3️⃣ 공용 카드 그대로 렌더
    renderClinics(myClinics, gridId);
    await renderMySchedule(favoriteIds, myClinics);

  } catch (e) {
    console.error("❌ 내 대시보드 로드 실패", e);
  }
}

let weekOffset = 0;
let weekItemsCache = [];
let activeWeekDate = "";

function toYmd(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function getWeekStart(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getWeekRange() {
  const base = new Date();
  base.setDate(base.getDate() + weekOffset * 7);
  const start = getWeekStart(base);
  const end = new Date(start);
  end.setDate(start.getDate() + 4);
  return { start, end };
}

function formatWeekLabel(start, end) {
  const opts = { month: "2-digit", day: "2-digit" };
  const startLabel = start.toLocaleDateString("ko-KR", opts);
  const endLabel = end.toLocaleDateString("ko-KR", opts);
  return `${start.getFullYear()}.${startLabel} ~ ${end.getFullYear()}.${endLabel}`;
}

function getPostDate(post) {
  const raw = post.published_at || post.updated_at || "";
  if (!raw) return "";
  return raw.slice(0, 10);
}

function isWeekdayDate(date) {
  const day = date.getDay();
  return day >= 1 && day <= 5;
}

function isWeekdayDateStr(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return false;
  return isWeekdayDate(d);
}

async function fetchClinicPostsByMonth(clinicId, month, type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month,
    assignee: "me",
  });
  const url = `${API_BASE}/api/data/clinics/${clinicId}/posts/?${params}`;
  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function isDateInRange(dateStr, start, end) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  return d >= start && d <= end;
}

function getWeekDays(start) {
  const days = [];
  for (let i = 0; i < 5; i += 1) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    days.push(d);
  }
  return days;
}

function formatWeekDayLabel(date) {
  return date.toLocaleDateString("ko-KR", { weekday: "short" });
}

function renderWeekCalendar(items, weekStart) {
  const calendar = document.getElementById("myWeekCalendar");
  if (!calendar) return;

  const grouped = new Map();
  items.forEach((item) => {
    if (!item.date) return;
    if (!isWeekdayDateStr(item.date)) return;
    if (!grouped.has(item.date)) grouped.set(item.date, []);
    grouped.get(item.date).push(item);
  });

  const days = getWeekDays(weekStart);
  const dayHtml = days.map((day) => {
    const dateStr = toYmd(day);
    const dayItems = grouped.get(dateStr) || [];
    const count = dayItems.length;
    const itemsHtml = count
      ? dayItems.slice(0, 2).map((item) => {
        const title = item.title || "-";
        const tag = item.type === "review" ? "review" : "opinion";
        return `<div class="week-task ${tag}">${title}</div>`;
      }).join("")
      : `<div class="week-empty">작업 없음</div>`;

    return `
      <div class="week-day ${count ? "clickable" : ""}" data-date="${dateStr}">
        <div class="week-day-head">
          <span class="week-day-label">${formatWeekDayLabel(day)}</span>
          ${count ? `<span class="week-count">${count}</span>` : ""}
        </div>
        <div class="week-day-date">${dateStr}</div>
        <div class="week-day-list">${itemsHtml}</div>
      </div>
    `;
  }).join("");

  calendar.innerHTML = dayHtml;

  calendar.querySelectorAll(".week-day.clickable").forEach((cell) => {
    cell.addEventListener("click", () => {
      activeWeekDate = cell.dataset.date || "";
      renderWeekDetailList(activeWeekDate);
      openWeekDetailPanel();
    });
  });
}

function renderWeekDetailList(filterDate) {
  const list = document.getElementById("myWeekDetailList");
  if (!list) return;
  const filtered = filterDate
    ? weekItemsCache.filter((i) => i.date === filterDate)
    : weekItemsCache;
  if (!filtered.length) {
    list.innerHTML = `<div class="muted">선택한 날짜의 작업이 없습니다.</div>`;
    return;
  }
  list.innerHTML = filtered.map((item) => {
    const title = item.title || "-";
    const link = item.url
      ? `<a href="${item.url}" target="_blank" rel="noreferrer">${title}</a>`
      : title;
    const subtypeLabel = item.review_subtype === "photo"
      ? "사진"
      : item.review_subtype === "text"
        ? "텍스트"
        : "";
    const typeLabel = item.type === "review" ? "후기" : item.type === "opinion" ? "여론" : "";
    const reviewLabel = typeLabel
      ? (subtypeLabel ? `${typeLabel}/${subtypeLabel}` : typeLabel)
      : "";
    const metaCells = [
      { label: "날짜", value: item.date || "-" },
      { label: "클리닉", value: item.clinic || "" },
      { label: "원장님", value: item.doctor_name || "" },
      { label: "ID", value: item.account || "" },
      { label: "리뷰 구분", value: reviewLabel },
      { label: "플랫폼", value: item.platform || "" },
      { label: "담당자", value: item.assignee || "" },
      { label: "PW", value: item.account_password || "" },
    ].filter((cell) => cell.value);
    const metaGrid = metaCells
      .map((cell) => `
        <div class="meta-cell">
          <span class="meta-label">${cell.label}</span>
          <span class="meta-value">${cell.value}</span>
        </div>
      `)
      .join("");
    const metrics = [
      Number.isFinite(item.views) ? `<span class="metric-chip">조회 ${item.views}</span>` : "",
      Number.isFinite(item.comments) ? `<span class="metric-chip">댓글 ${item.comments}</span>` : "",
      Number.isFinite(item.message_count) ? `<span class="metric-chip">쪽지 ${item.message_count}</span>` : "",
    ].filter(Boolean).join("");

    return `
      <div class="schedule-item compact">
        <div class="schedule-top">
          <div class="schedule-title">${link}</div>
        </div>
        <div class="schedule-meta-grid">
          ${metaGrid || `<div class="meta-empty">메타 정보 없음</div>`}
        </div>
        ${item.memo ? `<div class="schedule-memo">${item.memo}</div>` : ""}
        ${(metrics || item.photos?.length) ? `
          <div class="schedule-bottom">
            ${metrics ? `<div class="schedule-metrics">${metrics}</div>` : ""}
            ${item.photos?.length ? `
              <div class="schedule-photos">
                ${item.photos.slice(0, 4).map((url) => `<img src="${url}" alt="photo" />`).join("")}
              </div>
            ` : ""}
          </div>
        ` : ""}
      </div>
    `;
  }).join("");

  bindPhotoPreviews(list);
}

let photoPreviewReady = false;

function initPhotoPreviewModal() {
  if (photoPreviewReady) return;
  const modal = document.getElementById("photoPreviewModal");
  if (!modal) return;
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) {
      modal.classList.add("hidden");
    }
  });
  const closeBtn = modal.querySelector(".photo-preview-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.classList.add("hidden");
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      modal.classList.add("hidden");
    }
  });
  photoPreviewReady = true;
}

function openPhotoPreview(src) {
  const modal = document.getElementById("photoPreviewModal");
  const image = document.getElementById("photoPreviewImage");
  if (!modal || !image) return;
  image.src = src;
  modal.classList.remove("hidden");
}

function bindPhotoPreviews(listEl) {
  initPhotoPreviewModal();
  const imgs = listEl.querySelectorAll(".schedule-photos img");
  if (!imgs.length) return;
  imgs.forEach((img) => {
    img.addEventListener("click", (e) => {
      e.stopPropagation();
      openPhotoPreview(img.src);
    });
  });
}

function openWeekDetailPanel() {
  const panel = document.getElementById("myWeekDetailPanel");
  if (panel) panel.classList.add("open");
}

async function renderMySchedule(favoriteIds, clinicList) {
  const { start, end } = getWeekRange();
  const weekLabel = document.getElementById("weekLabel");
  if (weekLabel) {
    weekLabel.textContent = formatWeekLabel(start, end);
  }

  const clinicMap = new Map((clinicList || []).map(c => [Number(c.id), c.name]));
  const items = [];

  for (const clinicId of favoriteIds) {
    try {
      const monthKeys = new Set([
        `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, "0")}`,
        `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, "0")}`,
      ]);
      const results = [];
      for (const month of monthKeys) {
        const [opinions, reviews] = await Promise.all([
          fetchClinicPostsByMonth(clinicId, month, "opinion"),
          fetchClinicPostsByMonth(clinicId, month, "review"),
        ]);
        results.push(...opinions, ...reviews);
      }

      results.forEach((post) => {
        const date = getPostDate(post);
        if (!isDateInRange(date, start, end)) return;
        if (!isWeekdayDateStr(date)) return;
        const typeLabel = post.type === "review" ? "후기" : "여론";
        const titlePrefix = `[${typeLabel}]`;
        items.push({
          date,
          title: `${titlePrefix} ${post.title}`,
          url: post.url,
          clinic: clinicMap.get(Number(clinicId)) || "병원",
          clinicId: clinicId,
          platform: post.platform_label || post.platform,
          account: post.account || post.assignee_name || "",
          account_password: post.account_password || "",
          assignee: post.assignee_name || "",
          doctor_name: post.doctor_name || "",
          memo: post.memo || "",
          views: post.views ?? 0,
          comments: post.comments ?? 0,
          message_count: post.message_count ?? 0,
          post_id: post.id,
          type: post.type,
          review_subtype: post.review_subtype || null,
          photos: (post.photos || []).map((p) => p.url),
        });
      });
    } catch (e) {
      console.warn("schedule load failed:", clinicId, e);
    }
  }

  const sorted = items.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
  weekItemsCache = sorted;
  renderWeekCalendar(sorted, start);
  if (activeWeekDate) {
    renderWeekDetailList(activeWeekDate);
  }
}


document.addEventListener("DOMContentLoaded", renderMyDashboard);
document.addEventListener("DOMContentLoaded", () => {
  const prevBtn = document.getElementById("weekPrevBtn");
  const nextBtn = document.getElementById("weekNextBtn");
  const detailClose = document.getElementById("myWeekDetailClose");
  if (detailClose) {
    detailClose.addEventListener("click", () => {
      document.getElementById("myWeekDetailPanel")?.classList.remove("open");
    });
  }
  document.addEventListener("keydown", (e) => {
    const panel = document.getElementById("myWeekDetailPanel");
    const previewOpen = document.getElementById("photoPreviewModal")?.classList.contains("hidden") === false;
    if (e.key === "Escape" && panel?.classList.contains("open") && !previewOpen) {
      panel.classList.remove("open");
    }
  });
  initPanelResize("myWeekDetailPanel");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      weekOffset -= 1;
      renderMyDashboard();
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      weekOffset += 1;
      renderMyDashboard();
    });
  }
});

function initPanelResize(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  const handle = panel.querySelector(".panel-resizer");
  if (!handle) return;

  let startY = 0;
  let startHeight = 0;

  const onMove = (e) => {
    const delta = startY - e.clientY;
    const styles = window.getComputedStyle(panel);
    const minHeight = parseFloat(styles.minHeight) || 0;
    const maxHeight = parseFloat(styles.maxHeight) || Infinity;
    const next = Math.max(minHeight, Math.min(maxHeight, startHeight + delta));
    panel.style.height = `${next}px`;
  };

  const onStop = () => {
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onStop);
    document.body.classList.remove("resizing-panel");
  };

  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    startY = e.clientY;
    startHeight = panel.getBoundingClientRect().height;
    document.body.classList.add("resizing-panel");
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onStop);
  });
}
