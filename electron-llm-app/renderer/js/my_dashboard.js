console.log("my_dashboard.js loaded");

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
  end.setDate(start.getDate() + 6);
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

async function fetchClinicPostsByMonth(clinicId, month, type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month,
    assignee: "me",
  });
  const url = `http://127.0.0.1:8000/api/data/clinics/${clinicId}/posts/?${params}`;
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function isDateInRange(dateStr, start, end) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  return d >= start && d <= end;
}

function renderWeekList(items) {
  const list = document.getElementById("myScheduleList");
  if (!list) return;
  if (!items.length) {
    list.innerHTML = `<div class="muted">이번 주 작업이 없습니다.</div>`;
    return;
  }

  list.innerHTML = items.map((item) => {
    const link = item.url
      ? `<a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>`
      : item.title;
    return `
      <div class="schedule-item">
        <div class="schedule-title">${link}</div>
        <div class="schedule-meta">
          <span>${item.date || "-"}</span>
          ${item.clinic ? `<span class="schedule-badge">${item.clinic}</span>` : ""}
          ${item.platform ? `<span>${item.platform}</span>` : ""}
          ${item.account ? `<span>아이디: ${item.account}</span>` : ""}
          ${Number.isFinite(item.views) ? `<span>조회 ${item.views}</span>` : ""}
          ${Number.isFinite(item.comments) ? `<span>댓글 ${item.comments}</span>` : ""}
          ${Number.isFinite(item.message_count) ? `<span>쪽지 ${item.message_count}</span>` : ""}
        </div>
        ${item.photos?.length ? `
          <div class="schedule-photos">
            ${item.photos.slice(0, 4).map((url) => `<img src="${url}" alt="photo" />`).join("")}
          </div>
        ` : ""}
      </div>
    `;
  }).join("");
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
        const subtype = post.review_subtype === "photo" ? "사진" : post.review_subtype === "text" ? "텍스트" : "";
        const typeLabel = post.type === "review" ? "후기" : "여론";
        const titlePrefix = subtype ? `[${typeLabel}/${subtype}]` : `[${typeLabel}]`;
        items.push({
          date,
          title: `${titlePrefix} ${post.title}`,
          url: post.url,
          clinic: clinicMap.get(Number(clinicId)) || "병원",
          clinicId: clinicId,
          platform: post.platform_label || post.platform,
          account: post.assignee_name || "",
          views: post.views ?? 0,
          comments: post.comments ?? 0,
          message_count: post.message_count ?? 0,
          post_id: post.id,
          photos: (post.photos || []).map((p) => p.url),
        });
      });
    } catch (e) {
      console.warn("schedule load failed:", clinicId, e);
    }
  }

  const sorted = items.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
  renderWeekList(sorted);
}


document.addEventListener("DOMContentLoaded", renderMyDashboard);
document.addEventListener("DOMContentLoaded", () => {
  const prevBtn = document.getElementById("weekPrevBtn");
  const nextBtn = document.getElementById("weekNextBtn");
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
