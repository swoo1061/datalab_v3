console.log("my_dashboard.js loaded");
const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";

const PLATFORM_PILLS = [
  { key: "naver", label: "네이버" },
  { key: "gn_jp", label: "JP강남언니" },
  { key: "gangnam", label: "강남언니" },
  { key: "babytok", label: "바비톡" },
  { key: "todaktok", label: "토닥톡" },
  { key: "yeoshin", label: "여신티켓" },
  { key: "seongyesa", label: "성예사" },
  { key: "dadamo", label: "대다모" },
];

function getPlatformLabel(platformKey) {
  if (!platformKey) return "";
  const match = PLATFORM_PILLS.find((p) => p.key === platformKey);
  return match ? match.label : platformKey;
}

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

function formatMinutes(total) {
  const mins = Number(total) || 0;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}시간 ${m}분`;
}

function formatDateTimeKst(raw) {
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateTimePartsKst(raw) {
  if (!raw) return { date: "-", time: "-" };
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return { date: "-", time: "-" };
  const date = d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const time = d.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
  return { date, time };
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function fetchMyAttendance(month) {
  const headers = await buildAuthHeaders();
  const params = new URLSearchParams();
  if (month) params.set("month", month);
  const res = await fetch(`${API_BASE}/api/data/attendance/me/?${params.toString()}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("attendance_fetch_failed");
  return res.json();
}

async function postAttendanceAction(kind) {
  const headers = await buildAuthHeaders();
  const path = kind === "in" ? "check-in" : "check-out";
  const res = await fetch(`${API_BASE}/api/data/attendance/me/${path}/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: "{}",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "attendance_action_failed");
  }
  return res.json();
}

async function fetchAttendanceCorrections(limit = 5) {
  const headers = await buildAuthHeaders();
  const res = await fetch(`${API_BASE}/api/data/attendance/me/corrections/?limit=${limit}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error("attendance_corrections_fetch_failed");
  return res.json();
}

async function submitAttendanceCorrection(payload) {
  const headers = await buildAuthHeaders();
  const res = await fetch(`${API_BASE}/api/data/attendance/me/corrections/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "attendance_correction_submit_failed");
  }
  return res.json();
}

function renderAttendanceRows(rows) {
  const listEl = document.getElementById("attList");
  if (!listEl) return;
  if (!Array.isArray(rows) || !rows.length) {
    listEl.innerHTML = `<div class="muted">이번 달 기록이 없습니다.</div>`;
    return;
  }
  listEl.innerHTML = rows
    .slice(0, 10)
    .map((r) => `
      <div class="attendance-item">
        <div class="date">${r.work_date || "-"}</div>
        <div class="meta">
          출근 ${formatDateTimeKst(r.check_in_at)} · 퇴근 ${formatDateTimeKst(r.check_out_at)} · ${formatMinutes(r.worked_minutes)}
        </div>
      </div>
    `)
    .join("");
}

function renderAttendanceCorrections(rows) {
  const root = document.getElementById("attCorrections");
  if (!root) return;
  if (!Array.isArray(rows) || !rows.length) {
    root.innerHTML = `<div class="muted"></div>`;
    return;
  }
  const statusLabel = (s) => (s === "approved" ? "승인" : s === "rejected" ? "반려" : "대기");
  root.innerHTML = rows
    .map((r) => `
      <div class="attendance-correction-item">
        <div>
          <strong>${r.work_date || "-"}</strong>
          <span class="status">${statusLabel(r.status)}</span>
        </div>
        <div>출근 ${formatDateTimeKst(r.requested_check_in_at)} · 퇴근 ${formatDateTimeKst(r.requested_check_out_at)}</div>
        <div>${r.reason || ""}</div>
      </div>
    `)
    .join("");
}

function applyAttendanceState(payload) {
  const statusEl = document.getElementById("attTodayStatus");
  const metaEl = document.getElementById("attTodayMeta");
  const inBtn = document.getElementById("attCheckInBtn");
  const outBtn = document.getElementById("attCheckOutBtn");
  const sumEl = document.getElementById("attSummary");

  if (!statusEl || !metaEl || !inBtn || !outBtn || !sumEl) return;

  const today = payload?.today?.record;
  const liveMinutes = payload?.today?.live_minutes;
  if (!today) {
    statusEl.textContent = "미출근";
    metaEl.textContent = "아직 출근 기록이 없습니다.";
    inBtn.disabled = false;
    outBtn.disabled = true;
  } else if (today.check_in_at && !today.check_out_at) {
    statusEl.textContent = "근무중";
    metaEl.textContent = `출근 ${formatDateTimeKst(today.check_in_at)} · 현재 ${formatMinutes(liveMinutes || 0)}`;
    inBtn.disabled = true;
    outBtn.disabled = false;
  } else {
    statusEl.textContent = "퇴근 완료";
    metaEl.textContent = `출근 ${formatDateTimeKst(today.check_in_at)} · 퇴근 ${formatDateTimeKst(today.check_out_at)}`;
    inBtn.disabled = true;
    outBtn.disabled = true;
  }

  const summary = payload?.summary || {};
  sumEl.innerHTML = `
    <span>이번달 근무일 ${summary.worked_days || 0}일</span>
    <span>총 ${formatMinutes(summary.total_minutes || 0)}</span>
    <span>평균 ${formatMinutes(summary.average_minutes || 0)}</span>
  `;
}

async function loadAttendancePanel() {
  const inBtn = document.getElementById("attCheckInBtn");
  const outBtn = document.getElementById("attCheckOutBtn");
  if (!inBtn || !outBtn) return;
  const today = new Date();
  const monthKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const payload = await fetchMyAttendance(monthKey);
  const corrections = await fetchAttendanceCorrections(5).catch(() => ({ results: [] }));
  applyAttendanceState(payload);
  renderAttendanceRows(payload?.results || []);
  renderAttendanceCorrections(corrections?.results || []);
}

function initAttendancePanel() {
  const inBtn = document.getElementById("attCheckInBtn");
  const outBtn = document.getElementById("attCheckOutBtn");
  const openReqBtn = document.getElementById("attCorrectionOpenBtn");
  const reqModal = document.getElementById("attCorrectionModal");
  const reqSubmitBtn = document.getElementById("attReqSubmitBtn");
  if (!inBtn || !outBtn) return;

  const action = async (kind) => {
    try {
      await postAttendanceAction(kind);
      await loadAttendancePanel();
      window.showAlert?.(kind === "in" ? "출근 처리되었습니다." : "퇴근 처리되었습니다.");
    } catch (e) {
      if (String(e.message) === "check_in_required") {
        window.showAlert?.("먼저 출근 처리하세요.");
        return;
      }
      window.showAlert?.("처리 중 오류가 발생했습니다.");
    }
  };

  inBtn.addEventListener("click", () => action("in"));
  outBtn.addEventListener("click", () => action("out"));

  if (openReqBtn && reqModal) {
    openReqBtn.addEventListener("click", () => {
      const today = new Date();
      const dateEl = document.getElementById("attReqDate");
      if (dateEl && !dateEl.value) {
        dateEl.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      }
      reqModal.classList.remove("hidden");
    });
    reqModal.addEventListener("click", (e) => {
      if (e.target?.dataset?.close) reqModal.classList.add("hidden");
    });
  }

  if (reqSubmitBtn) {
    reqSubmitBtn.addEventListener("click", async () => {
      const workDate = document.getElementById("attReqDate")?.value || "";
      const requestedCheckInAt = document.getElementById("attReqCheckIn")?.value || "";
      const requestedCheckOutAt = document.getElementById("attReqCheckOut")?.value || "";
      const reason = (document.getElementById("attReqReason")?.value || "").trim();
      if (!workDate) {
        window.showAlert?.("대상일을 입력하세요.");
        return;
      }
      if (!reason) {
        window.showAlert?.("정정 사유를 입력하세요.");
        return;
      }
      const payload = {
        work_date: workDate,
        reason,
      };
      if (requestedCheckInAt) payload.requested_check_in_at = new Date(requestedCheckInAt).toISOString();
      if (requestedCheckOutAt) payload.requested_check_out_at = new Date(requestedCheckOutAt).toISOString();
      try {
        await submitAttendanceCorrection(payload);
        if (reqModal) reqModal.classList.add("hidden");
        const inEl = document.getElementById("attReqCheckIn");
        const outEl = document.getElementById("attReqCheckOut");
        const reasonEl = document.getElementById("attReqReason");
        if (inEl) inEl.value = "";
        if (outEl) outEl.value = "";
        if (reasonEl) reasonEl.value = "";
        await loadAttendancePanel();
        window.showAlert?.("정정 요청이 전송되었습니다. 대표님 계정으로 알림을 보냈습니다.");
      } catch (e) {
        const msg = String(e.message || "");
        if (msg === "invalid_time_range") {
          window.showAlert?.("퇴근 시각은 출근 시각보다 늦어야 합니다.");
          return;
        }
        window.showAlert?.("정정 요청 전송에 실패했습니다.");
      }
    });
  }

  loadAttendancePanel().catch(() => {
    window.showAlert?.("출퇴근 정보를 불러오지 못했습니다.");
  });
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
    const list = await window.api.getFavorites({ fallback: "assignee" });
    return (list || []).map((f) => Number(f.clinic_id));
  } catch (e) {
    console.warn("getFavoritesFromServer failed", e);
    return [];
  }
}

async function getMyClinicIdsFromServer(months = 3) {
  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/my-clinics/?months=${months}`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data?.results || []).map((id) => Number(id));
  } catch (e) {
    console.warn("getMyClinicIdsFromServer failed", e);
    return [];
  }
}

async function renderMyDashboard() {
  const gridId = "myClinicGrid";

  try {
    // 1️⃣ 서버에서 즐겨찾기 + 내가 작성한 병원 목록
    const favorites = await window.api.getFavorites({ fallback: "assignee" });
    const favoriteIds = favorites.map(f => Number(f.clinic_id));
    const myClinicIds = await getMyClinicIdsFromServer(3);
    const mergedIds = Array.from(new Set([...favoriteIds, ...myClinicIds]));

    if (mergedIds.length === 0) {
      document.getElementById(gridId).innerHTML =
        `<p class="muted">표시할 병원이 없습니다.</p>`;
      return;
    }

    // 2️⃣ 공용 clinics에서 필터링
    const myClinics = clinics
      .filter(c => mergedIds.includes(Number(c.id)))
      .map(c => ({
        ...c,
        isFavorite: true, // 개인 대시보드는 전부 즐겨찾기
      }));

    // 3️⃣ 공용 카드 그대로 렌더
    renderClinics(myClinics, gridId);
    await renderMySchedule(mergedIds, myClinics);

  } catch (e) {
    console.error("❌ 내 대시보드 로드 실패", e);
  }
}

let monthOffset = 0;
let weekItemsCache = [];
let activeWeekDate = "";

function toYmd(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function getMonthRange() {
  const base = new Date();
  base.setMonth(base.getMonth() + monthOffset, 1);
  const start = new Date(base.getFullYear(), base.getMonth(), 1);
  start.setHours(0, 0, 0, 0);
  const end = new Date(base.getFullYear(), base.getMonth() + 1, 0);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

function formatMonthLabel(start) {
  return `${start.getFullYear()}.${String(start.getMonth() + 1).padStart(2, "0")}`;
}

function getPostDate(post) {
  const raw = post.published_at || post.updated_at || "";
  if (!raw) return "";
  return raw.slice(0, 10);
}

function getReviewSubtypeLabel(post) {
  const subtype = post?.review_subtype;
  if (subtype === "photo") return "사진";
  if (subtype === "text") return "텍스트";
  if (subtype === "consultation") return "상담";
  const titleHint = String(post?.title || "").toLowerCase();
  if (titleHint.includes("상담")) return "상담";
  return Array.isArray(post?.photos) && post.photos.length ? "사진" : "텍스트";
}

function getOpinionSubtypeLabel(post) {
  const subtype = post?.opinion_subtype;
  if (subtype === "hand") return "손품";
  if (subtype === "foot") return "발품";
  return "고민";
}

function getTypeDisplayLabel(post) {
  if (post?.type === "review") return `후기/${getReviewSubtypeLabel(post)}`;
  if (post?.type === "opinion") return `여론/${getOpinionSubtypeLabel(post)}`;
  return "작업";
}

function buildCalendarCardTitle(post, clinicName) {
  return `[${getTypeDisplayLabel(post)}] ${clinicName || "병원"}`;
}

async function fetchClinicPostsByMonth(clinicId, month, type) {
  const sessionKey = await window.session?.getKey?.();
  const params = new URLSearchParams({
    type,
    platform: "all",
    month,
  });
  if (sessionKey) {
    params.set("assignee", "me");
  }

  let url = `${API_BASE}/api/data/clinics/${clinicId}/posts/?${params}`;
  const headers = await buildAuthHeaders();
  let res = await fetch(url, { credentials: "include", headers });

  // 세션 만료 등으로 401이 나면 assignee 필터 없이 한 번 더 시도
  if (res.status === 401 && params.get("assignee") === "me") {
    params.delete("assignee");
    url = `${API_BASE}/api/data/clinics/${clinicId}/posts/?${params}`;
    res = await fetch(url, { credentials: "include", headers });
  }

  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function isDateInRange(dateStr, start, end) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  return d >= start && d <= end;
}

function formatWeekDayLabel(date) {
  return date.toLocaleDateString("ko-KR", { weekday: "short" });
}

function renderWeekCalendar(items, monthStart) {
  const calendar = document.getElementById("myWeekCalendar");
  if (!calendar) return;

  const grouped = new Map();
  items.forEach((item) => {
    if (!item.date) return;
    if (!grouped.has(item.date)) grouped.set(item.date, []);
    grouped.get(item.date).push(item);
  });

  const year = monthStart.getFullYear();
  const month = monthStart.getMonth();
  const labels = ["월", "화", "수", "목", "금"];
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  let week = new Array(5).fill(null);

  for (let day = 1; day <= daysInMonth; day += 1) {
    const dateObj = new Date(year, month, day);
    const dayOfWeek = dateObj.getDay(); // 0=Sun, 1=Mon ... 6=Sat
    if (dayOfWeek === 0 || dayOfWeek === 6) continue; // 주말 제외

    if (dayOfWeek === 1 && week.some(Boolean)) {
      cells.push(...week);
      week = new Array(5).fill(null);
    }

    week[dayOfWeek - 1] = dateObj;
  }

  if (week.some(Boolean)) cells.push(...week);

  const headerHtml = labels.map((label) => `<div class="calendar-head">${label}</div>`).join("");
  const dayHtml = cells.map((day) => {
    if (!day) return `<div class="calendar-cell muted"></div>`;

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
      <div class="calendar-cell clickable" data-date="${dateStr}">
        <div class="week-day-head">
          <span class="calendar-day">${day.getDate()}</span>
          ${count ? `<span class="calendar-count">${count}건</span>` : ""}
        </div>
        <div class="week-day-list">${itemsHtml}</div>
      </div>
    `;
  }).join("");

  calendar.innerHTML = `${headerHtml}${dayHtml}`;

  calendar.querySelectorAll(".calendar-cell.clickable").forEach((cell) => {
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
    const reviewSubtypeLabel = item.review_subtype === "photo"
      ? "사진"
      : item.review_subtype === "text"
        ? "텍스트"
        : item.review_subtype === "consultation"
          ? "상담"
          : "";
    const opinionSubtypeLabel = item.opinion_subtype === "hand"
      ? "손품"
      : item.opinion_subtype === "foot"
        ? "발품"
        : "고민";
    const typeLabel = item.type === "review" ? "후기" : item.type === "opinion" ? "여론" : "";
    const detailTypeLabel = typeLabel
      ? `${typeLabel}/${item.type === "review" ? (reviewSubtypeLabel || "텍스트") : opinionSubtypeLabel}`
      : "";
    const metaCells = [
      { label: "날짜", value: item.date || "-" },
      { label: "클리닉", value: item.clinic || "" },
      { label: "원장님", value: item.doctor_name || "" },
      { label: "ID", value: item.account || "" },
      { label: "리뷰 구분", value: detailTypeLabel },
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
  const { start, end } = getMonthRange();
  const weekLabel = document.getElementById("weekLabel");
  if (weekLabel) {
    weekLabel.textContent = formatMonthLabel(start);
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
        const clinicName = clinicMap.get(Number(clinicId)) || "병원";
        items.push({
          date,
          title: buildCalendarCardTitle(post, clinicName),
          url: post.url,
          clinic: clinicName,
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
          opinion_subtype: post.opinion_subtype || null,
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

function initReviewSchedulePlanner() {
  const calendarEl = document.getElementById("myReviewScheduleCalendar");
  const listEl = document.getElementById("myReviewScheduleList");
  const selectedDateEl = document.getElementById("myReviewScheduleSelectedDate");
  const monthLabelEl = document.getElementById("reviewScheduleMonthLabel");
  const prevBtn = document.getElementById("reviewSchedulePrevBtn");
  const nextBtn = document.getElementById("reviewScheduleNextBtn");
  const openAddBtn = document.getElementById("myReviewScheduleAdd");
  const openGenerateBtn = document.getElementById("myReviewScheduleGenerate");
  const generateModal = document.getElementById("reviewScheduleGenerateModal");
  const generateConfirmBtn = document.getElementById("reviewScheduleGenerateConfirm");
  const planTitleInputEl = document.getElementById("reviewSchedulePlanTitle");
  const personaKeywordsInputEl = document.getElementById("reviewSchedulePersonaKeywords");
  const platformAccountInputEl = document.getElementById("reviewSchedulePlatformAccount");
  const platformPasswordInputEl = document.getElementById("reviewSchedulePlatformPassword");
  const planGroupsWrapEl = document.getElementById("reviewSchedulePlanGroups");
  const itemModal = document.getElementById("reviewScheduleItemModal");
  const itemModalTitleEl = document.getElementById("reviewScheduleItemModalTitle");
  const itemDateEl = document.getElementById("reviewScheduleItemDate");
  const itemRemindEl = document.getElementById("reviewScheduleItemRemind");
  const itemLabelEl = document.getElementById("reviewScheduleItemLabel");
  const itemDetailEl = document.getElementById("reviewScheduleItemDetail");
  const itemDraftEl = document.getElementById("reviewScheduleItemDraft");
  const itemSaveBtn = document.getElementById("reviewScheduleItemSave");
  const planDetailModal = document.getElementById("planDetailModal");
  const planDetailModalTitleEl = document.getElementById("planDetailModalTitle");
  const planDetailModalBodyEl = document.getElementById("planDetailModalBody");
  if (!calendarEl || !monthLabelEl) return;
  const hasPlanList = !!(listEl && selectedDateEl);

  const today = new Date();
  let currentMonthDate = new Date(today.getFullYear(), today.getMonth(), 1);
  let selectedDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  let editingScheduleId = null;
  const cache = new Map();
  const activeItemByBundle = new Map();
  let activeBundleKey = "";
  let pendingModalOpen = null;
  const planTitleStorageKey = "myDashboard::reviewPlanTitles";
  const planCompleteStorageKey = "myDashboard::reviewPlanCompleted";
  let planTitleMap = {};
  let planCompleteMap = {};
  try {
    const rawPlanTitleMap = localStorage.getItem(planTitleStorageKey);
    planTitleMap = rawPlanTitleMap ? JSON.parse(rawPlanTitleMap) : {};
  } catch (e) {
    planTitleMap = {};
  }
  try {
    const rawPlanCompleteMap = localStorage.getItem(planCompleteStorageKey);
    planCompleteMap = rawPlanCompleteMap ? JSON.parse(rawPlanCompleteMap) : {};
  } catch (e) {
    planCompleteMap = {};
  }

  const toYmd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const monthKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  const monthTitle = (d) => `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
  const esc = (v) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const attrEsc = (v) => esc(v).replace(/"/g, "&quot;");
  const persistPlanTitleMap = () => {
    try {
      localStorage.setItem(planTitleStorageKey, JSON.stringify(planTitleMap));
    } catch (e) {
      console.warn("plan title save failed", e);
    }
  };
  const persistPlanCompleteMap = () => {
    try {
      localStorage.setItem(planCompleteStorageKey, JSON.stringify(planCompleteMap));
    } catch (e) {
      console.warn("plan complete save failed", e);
    }
  };
  const completionKeyOf = (bundleKey, slotKey) => `${bundleKey}::${slotKey}`;

  const initFlatpickr = (input) => {
    if (!input || !window.flatpickr) return null;
    if (window.flatpickr.l10ns?.ko) {
      window.flatpickr.localize(window.flatpickr.l10ns.ko);
    }
    if (input._flatpickr) return input._flatpickr;
    const fp = window.flatpickr(input, {
      enableTime: true,
      dateFormat: "Y-m-d H:i",
      time_24hr: false,
      allowInput: true,
      onOpen: (selectedDates, dateStr, instance) => {
        if (instance?.calendarContainer) {
          instance.calendarContainer.classList.add("memo-flatpickr");
        }
      },
    });
    input.addEventListener("focus", () => fp.open());
    return fp;
  };
  initFlatpickr(itemRemindEl);

  const parseScheduleContent = (rawContent) => {
    const raw = String(rawContent || "").trim();
    const mNew = raw.match(/^\[리뷰설계\/([^\/\]]+)\/([^\]]+)\]\s*([\s\S]*?)(?:\n(?:리뷰|초안):\s*([\s\S]*))?$/);
    if (mNew) {
      return {
        planId: String(mNew[1] || "").trim(),
        label: String(mNew[2] || "").trim() || "리뷰 설계",
        detail: String(mNew[3] || "").trim(),
        draft: String(mNew[4] || "").trim(),
      };
    }
    const mOld = raw.match(/^\[리뷰설계\/([^\]]+)\]\s*([\s\S]*?)(?:\n(?:리뷰|초안):\s*([\s\S]*))?$/);
    if (!mOld) return { planId: "", label: "리뷰 설계", detail: raw, draft: "" };
    return {
      planId: "",
      label: String(mOld[1] || "").trim() || "리뷰 설계",
      detail: String(mOld[2] || "").trim(),
      draft: String(mOld[3] || "").trim(),
    };
  };

  const buildScheduleContent = ({ planId, label, detail, draft }) => {
    const pid = String(planId || "").trim();
    const l = String(label || "").trim();
    const d = String(detail || "").trim();
    const dr = String(draft || "").trim();
    let content = pid ? `[리뷰설계/${pid}/${l}] ${d}` : `[리뷰설계/${l}] ${d}`;
    if (dr) content += `\n리뷰: ${dr}`;
    return content;
  };
  const bundleKeyOf = (row) => {
    const parsed = parseScheduleContent(row?.content || "");
    return parsed.planId ? `plan-${parsed.planId}` : `single-${row?.id}`;
  };

  const slotKeyOfLabel = (label) => {
    const s = String(label || "");
    const week = s.match(/(\d+)\s*주차/);
    if (week) {
      const n = Number(week[1]);
      if (n >= 1 && n <= 3) return `week${n}`;
    }
    const month = s.match(/(\d+)\s*개월/);
    if (month) {
      const n = Number(month[1]);
      if (n >= 1 && n <= 6) return `month${n}`;
    }
    if (/상담/.test(s)) return "consult";
    if (/고민|여론|관심/.test(s)) return "worry";
    if (/손품|발품|검색|비교|커뮤니티/.test(s)) return "research";
    return "";
  };
  const normalizeScheduleDateKey = (value) => {
    const s = String(value || "").trim();
    if (!s) return "";
    const m = s.match(/^(\d{4}-\d{2}-\d{2})/);
    if (m) return m[1];
    const d = new Date(s);
    if (!Number.isNaN(d.valueOf())) {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    }
    return s;
  };
  const renderCalendarDayRows = (rows) => {
    if (!rows.length) return `<div class="plan-empty"><strong>표시할 리뷰가 없습니다.</strong></div>`;
    return rows.map((row) => {
      const parsed = parseScheduleContent(row?.content || "");
      const planTitle = String(row?.plan_title || "").trim();
      const remindText = row?.remind_at ? `알림 ${new Date(row.remind_at).toLocaleString("ko-KR")}` : "";
      return `
        <article class="plan-row" data-id="${esc(row?.id || "")}">
          <div class="plan-row-head">
            <span class="plan-type-badge">${esc(parsed.label || "리뷰 설계")}</span>
            <span class="plan-date">${esc(normalizeScheduleDateKey(row?.date || ""))}</span>
          </div>
          <div class="plan-detail">${esc(planTitle || "설계안")}</div>
          ${parsed.draft ? `<div class="plan-draft"><div>${esc(parsed.draft)}</div></div>` : ""}
          ${remindText ? `<div class="plan-row-meta">${esc(remindText)}</div>` : ""}
        </article>
      `;
    }).join("");
  };
  const fetchSchedules = async (month) => {
    const key = month || "__all__";
    if (cache.has(key)) return cache.get(key);
    try {
      const headers = await buildAuthHeaders();
      const params = new URLSearchParams();
      if (month) params.set("month", month);
      const res = await fetch(`${API_BASE}/api/data/review-schedules/?${params}`, {
        credentials: "include",
        headers,
      });
      if (!res.ok) return [];
      const data = await res.json();
      const rows = data.results || [];
      cache.set(key, rows);
      return rows;
    } catch (e) {
      console.error("review schedule load failed", e);
      return [];
    }
  };

  const clearMonthCache = (month) => {
    if (!month) return;
    cache.delete(month);
  };
  const clearAllCache = () => cache.clear();

  const closeItemModal = () => {
    itemModal?.classList.add("hidden");
    editingScheduleId = null;
  };
  const closePlanDetailModal = () => {
    planDetailModal?.classList.add("hidden");
  };
  const openPlanDetailModal = ({ title, bodyHtml }) => {
    if (!planDetailModal || !planDetailModalTitleEl || !planDetailModalBodyEl) return;
    planDetailModalTitleEl.textContent = title || "리뷰 상세";
    planDetailModalBodyEl.innerHTML = bodyHtml || `<div class="plan-empty"><strong>표시할 리뷰가 없습니다.</strong></div>`;
    planDetailModal.classList.remove("hidden");
  };

  const openItemModal = (mode = "create", row = null) => {
    if (!itemModal) return;
    editingScheduleId = mode === "edit" ? row?.id || null : null;
    if (itemModalTitleEl) itemModalTitleEl.textContent = mode === "edit" ? "리뷰 스케줄 수정" : "리뷰 스케줄 추가";

    const parsed = parseScheduleContent(row?.content || "");
    if (itemDateEl) itemDateEl.value = mode === "edit" ? String(row?.date || selectedDate) : selectedDate;
    if (itemLabelEl) itemLabelEl.value = mode === "edit" ? parsed.label : "";
    if (itemDetailEl) itemDetailEl.value = mode === "edit" ? parsed.detail : "";
    if (itemDraftEl) itemDraftEl.value = mode === "edit" ? parsed.draft : "";
    if (itemRemindEl) {
      const fp = initFlatpickr(itemRemindEl);
      if (mode === "edit" && row?.remind_at) {
        const d = new Date(row.remind_at);
        if (!Number.isNaN(d.valueOf())) {
          fp?.setDate(d, true);
          itemRemindEl.value = fp?.input?.value || itemRemindEl.value;
        }
      } else {
        fp?.clear();
        itemRemindEl.value = "";
      }
    }
    itemModal.classList.remove("hidden");
  };

  const renderList = async () => {
    if (!hasPlanList) return;
    const rows = (await fetchSchedules()).sort((a, b) => `${a.date || ""}`.localeCompare(`${b.date || ""}`));
    selectedDateEl.textContent = `설계표 전체 (${rows.length}건)`;
    if (!rows.length) {
      listEl.innerHTML = `<div class="plan-empty"><strong>설계 항목이 없습니다.</strong></div>`;
      return;
    }

    const rowById = new Map(rows.map((row) => [String(row.id), row]));
    const parsedRows = rows.map((row) => ({ row, parsed: parseScheduleContent(row.content) }));
    const bundles = parsedRows.reduce((acc, item) => {
      const bKey = item.parsed.planId ? `plan-${item.parsed.planId}` : `single-${item.row.id}`;
      if (!acc[bKey]) acc[bKey] = [];
      acc[bKey].push(item);
      return acc;
    }, {});

    const stageTypeOf = (label) => {
      const s = String(label || "");
      if (/고민|여론|관심/.test(s)) return "worry";
      if (/손품|발품|검색|비교|커뮤니티/.test(s)) return "research";
      if (/상담/.test(s)) return "consult";
      if (/주차/.test(s)) return "week";
      if (/개월/.test(s)) return "month";
      return "worry";
    };
    const extractNum = (label, unit) => {
      const m = String(label || "").match(new RegExp(`(\\d+)\\s*${unit}`));
      return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
    };
    const sortByStageOrder = (arr, unit) => [...arr].sort((a, b) => {
      const na = extractNum(a.parsed.label, unit);
      const nb = extractNum(b.parsed.label, unit);
      if (na !== nb) return na - nb;
      return String(a.row.date || "").localeCompare(String(b.row.date || ""));
    });
    const sortByDate = (arr) => [...arr].sort((a, b) => String(a.row.date || "").localeCompare(String(b.row.date || "")));
    const formatRemindLabel = (remindAt) => (
      remindAt
        ? new Date(remindAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
        : "-"
    );
    const toLocalInputValue = (isoLike) => {
      if (!isoLike) return "";
      const dt = new Date(isoLike);
      if (Number.isNaN(dt.valueOf())) return "";
      const local = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000);
      return local.toISOString().slice(0, 16);
    };
    const renderRowReadHtml = (row, parsed) => {
      const remindLabel = formatRemindLabel(row.remind_at);
      const hasDraft = !!parsed.draft;
      return `
        <header class="plan-row-head">
          <span class="plan-type-badge">${esc(parsed.label || "")}</span>
          <span class="plan-date plan-date-pill">${esc(row.date || "-")}</span>
        </header>
        <div class="plan-row-meta">알림 ${remindLabel}</div>
        ${hasDraft ? `
          <div class="plan-draft">
            ${esc(parsed.draft)}
          </div>
        ` : ""}
        <div class="plan-row-actions">
          <button type="button" class="plan-edit" data-id="${row.id}">수정</button>
          <button type="button" class="plan-delete" data-id="${row.id}">삭제</button>
        </div>
      `;
    };
    const renderRows = (items) => items.map(({ row, parsed }) => {
      const remindLabel = row.remind_at
        ? new Date(row.remind_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
        : "-";
      const hasDraft = !!parsed.draft;
      return `
        <article class="plan-row" data-id="${row.id || ""}">
          ${renderRowReadHtml(row, parsed)}
        </article>
      `;
    }).join("");
    const showInlineEditStatus = (article, message, isError = false) => {
      if (!article) return;
      let el = article.querySelector(".plan-inline-status");
      if (!el) {
        el = document.createElement("div");
        el.className = "plan-inline-status";
        const actions = article.querySelector(".plan-row-actions");
        if (actions) actions.insertAdjacentElement("beforebegin", el);
      }
      el.textContent = message || "";
      el.dataset.state = isError ? "error" : "ok";
    };

    const bundleKeys = Object.keys(bundles).sort((a, b) => {
      const ad = String(bundles[a][0]?.row?.date || "");
      const bd = String(bundles[b][0]?.row?.date || "");
      return bd.localeCompare(ad);
    });
    if (!activeBundleKey || !bundles[activeBundleKey]) {
      activeBundleKey = bundleKeys[0] || "";
    }
    const key = activeBundleKey;
    const items = sortByDate(bundles[key] || []);
    const idx = Math.max(0, bundleKeys.indexOf(key));
    let modalPayload = null;

    const worryItems = items.filter((x) => stageTypeOf(x.parsed.label) === "worry");
    const researchItems = items.filter((x) => stageTypeOf(x.parsed.label) === "research");
    const consultItems = items.filter((x) => stageTypeOf(x.parsed.label) === "consult");
    const weekItems = sortByStageOrder(items.filter((x) => stageTypeOf(x.parsed.label) === "week"), "주차");
    const monthItems = sortByStageOrder(items.filter((x) => stageTypeOf(x.parsed.label) === "month"), "개월");

    const detectWeekIndex = (entry) => {
      const text = `${entry?.parsed?.label || ""} ${entry?.parsed?.detail || ""} ${entry?.row?.content || ""}`;
      const m = text.match(/(^|\D)([1-3])\s*주차/);
      return m ? Number(m[2]) : 0;
    };
    const detectMonthIndex = (entry) => {
      const text = `${entry?.parsed?.label || ""} ${entry?.parsed?.detail || ""} ${entry?.row?.content || ""}`;
      const m = text.match(/(^|\D)([1-6])\s*개월/);
      return m ? Number(m[2]) : 0;
    };
    const allocateByIndex = (rowsForSlot, maxN, detector) => {
      const slots = Array.from({ length: maxN }, () => []);
      const leftovers = [];
      rowsForSlot.forEach((row) => {
        const n = detector(row);
        if (n >= 1 && n <= maxN) slots[n - 1].push(row);
        else leftovers.push(row);
      });
      leftovers.forEach((row, i) => {
        slots[i % maxN].push(row);
      });
      return slots;
    };
    const weekSlots = allocateByIndex(weekItems, 3, detectWeekIndex);
    const monthSlots = allocateByIndex(monthItems, 6, detectMonthIndex);

    const slotMap = {
      worry: worryItems,
      research: researchItems,
      consult: consultItems,
      week1: weekSlots[0],
      week2: weekSlots[1],
      week3: weekSlots[2],
      month1: monthSlots[0],
      month2: monthSlots[1],
      month3: monthSlots[2],
      month4: monthSlots[3],
      month5: monthSlots[4],
      month6: monthSlots[5],
    };

    const buttonDefs = [
      { slot: "worry", label: "고민" },
      { slot: "research", label: "손품/발품" },
      { slot: "consult", label: "상담후기" },
      { slot: "week1", label: "1주차" },
      { slot: "week2", label: "2주차" },
      { slot: "week3", label: "3주차" },
      { slot: "month1", label: "1개월" },
      { slot: "month2", label: "2개월" },
      { slot: "month3", label: "3개월" },
      { slot: "month4", label: "4개월" },
      { slot: "month5", label: "5개월" },
      { slot: "month6", label: "6개월" },
    ];
    const firstAvailableSlot = buttonDefs.find((d) => (slotMap[d.slot] || []).length > 0)?.slot || "worry";
    const activeSlot = activeItemByBundle.get(key) || firstAvailableSlot;
    const activeRows = slotMap[activeSlot] || [];
    const activeAccount = String(activeRows[0]?.row?.account || "").trim();
    const activePassword = String(activeRows[0]?.row?.account_password || "").trim();
    const slotLabelByKey = buttonDefs.reduce((acc, def) => {
      acc[def.slot] = def.label;
      return acc;
    }, {});
    activeItemByBundle.set(key, activeSlot);
    const savedTitle = String(planTitleMap[key] || "").trim();
    const defaultTitle = String(items[0]?.row?.plan_title || "").trim()
      || `설계안 ${idx + 1}`;
    const titleValue = savedTitle || defaultTitle;

    if (pendingModalOpen && pendingModalOpen.bundleKey === key && pendingModalOpen.slotKey === activeSlot) {
      modalPayload = {
        title: `${titleValue} - ${slotLabelByKey[activeSlot] || "상세"}`,
        bodyHtml: activeRows.length ? renderRows(activeRows) : `<div class="plan-empty"><strong>표시할 리뷰가 없습니다.</strong></div>`,
      };
    }

    const makeGroup = (title, defs) => {
      const buttons = defs.map((def) => {
        const rowsForSlot = slotMap[def.slot] || [];
        const on = def.slot === activeSlot;
        const completed = !!planCompleteMap[completionKeyOf(key, def.slot)];
        const disabledAttr = rowsForSlot.length ? "" : "disabled";
        return `
          <div class="plan-item-entry ${completed ? "completed" : ""}">
            <button type="button" class="plan-item-btn ${on ? "active" : ""} ${completed ? "completed" : ""}" data-bundle="${esc(key)}" data-slot-key="${esc(def.slot)}" ${disabledAttr}>${esc(def.label)}</button>
            <button type="button" class="plan-item-toggle ${completed ? "completed" : ""}" data-bundle="${esc(key)}" data-slot-key="${esc(def.slot)}" aria-label="완료 토글" title="완료 토글" ${disabledAttr}>${completed ? "✓" : ""}</button>
          </div>
        `;
      }).join("");
      return `
        <div class="plan-btn-group">
          <div class="plan-btn-group-title">${esc(title)}</div>
          <div class="plan-item-buttons">${buttons}</div>
        </div>
      `;
    };

    const bundleMeta = bundleKeys.map((bk, i) => {
      const bItems = sortByDate(bundles[bk] || []);
      const bSavedTitle = String(planTitleMap[bk] || "").trim();
      const bDefaultTitle = String(bItems[0]?.row?.plan_title || "").trim()
        || `설계안 ${i + 1}`;
      const bTitle = bSavedTitle || bDefaultTitle;
      const firstDate = String(bItems[0]?.row?.date || "").trim();
      const lastDate = String(bItems[bItems.length - 1]?.row?.date || "").trim();
      const rangeLabel = firstDate && lastDate
        ? (firstDate === lastDate ? firstDate : `${firstDate}~${lastDate}`)
        : (firstDate || lastDate || "-");
      return { key: bk, title: bTitle, rangeLabel };
    });
    const activeMeta = bundleMeta.find((m) => m.key === key) || bundleMeta[0] || null;
    const selectorRows = bundleMeta.map((meta) => `
      <div class="plan-selector-row ${meta.key === key ? "active" : ""}">
        <button type="button" class="plan-selector-item" data-bundle="${attrEsc(meta.key)}">
          <span class="plan-selector-item-title">${esc(meta.title)}</span>
          <span class="plan-selector-item-meta">${esc(meta.rangeLabel)}</span>
        </button>
        <button type="button" class="plan-selector-delete" data-bundle-delete="${attrEsc(meta.key)}" aria-label="설계안 삭제" title="설계안 삭제">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v8h-2V9zm4 0h2v8h-2V9zM7 9h2v8H7V9zm-1 12h12l1-12H5l1 12z"/>
          </svg>
        </button>
      </div>
    `).join("");
    const selectorLabel = activeMeta ? `${activeMeta.title} (${activeMeta.rangeLabel})` : "설계안 선택";
    const selectorHtml = `
      <label class="plan-title-editor">
        <span>설계안 선택</span>
        <div class="plan-selector" id="planBundleSelector">
          <button type="button" class="plan-selector-trigger" id="planBundleTrigger">
            <span>${esc(selectorLabel)}</span>
          </button>
          <div class="plan-selector-menu hidden" id="planBundleMenu">
            ${selectorRows}
          </div>
        </div>
      </label>
    `;

    const html = `
      <section class="plan-v2-card">
        <div class="plan-v2-head">
          <div class="plan-v2-head-main">
            <strong>${esc(titleValue)}</strong>
            <div class="plan-v2-credentials">
              <span><b>ID</b> ${esc(activeAccount || "-")}</span>
              <span><b>PW</b> ${esc(activePassword || "-")}</span>
            </div>
          </div>
          <div class="plan-v2-head-actions">
            ${selectorHtml}
          </div>
        </div>
        <div class="plan-v2-buttons">
          ${makeGroup("탐색", buttonDefs.filter((d) => d.slot === "worry" || d.slot === "research"))}
          ${makeGroup("상담", buttonDefs.filter((d) => d.slot === "consult"))}
          ${makeGroup("주차", buttonDefs.filter((d) => d.slot.startsWith("week")))}
          ${makeGroup("개월", buttonDefs.filter((d) => d.slot.startsWith("month")))}
        </div>
      </section>
    `;

    listEl.innerHTML = `<div class="plan-v2-wrap">${html}</div>`;
    const deleteBundleByKey = async (bundleKey) => {
      const targetItems = bundles[bundleKey] || [];
      const ids = targetItems.map((x) => x?.row?.id).filter((v) => v !== null && v !== undefined);
      if (!ids.length) {
        window.showAlert?.("삭제할 설계안이 없습니다.");
        return;
      }
      const targetMeta = bundleMeta.find((m) => m.key === bundleKey);
      const targetTitle = targetMeta?.title || "설계안";
      const ok = (typeof window.appConfirm === "function")
        ? await window.appConfirm(`'${targetTitle}' 설계안을 삭제할까요?`)
        : (window.confirm?.(`'${targetTitle}' 설계안을 삭제할까요?`) ?? true);
      if (!ok) return;
      try {
        const headers = await buildAuthHeaders();
        for (const id of ids) {
          const res = await fetch(`${API_BASE}/api/data/review-schedules/${id}/`, {
            method: "DELETE",
            credentials: "include",
            headers,
          });
          if (!res.ok) throw new Error(`delete failed: ${id}`);
        }
        activeItemByBundle.delete(bundleKey);
        if (activeBundleKey === bundleKey) activeBundleKey = "";
        if (planTitleMap[bundleKey]) {
          delete planTitleMap[bundleKey];
          persistPlanTitleMap();
        }
        Object.keys(planCompleteMap).forEach((k2) => {
          if (k2.startsWith(`${bundleKey}::`)) delete planCompleteMap[k2];
        });
        persistPlanCompleteMap();
        clearAllCache();
        await renderCalendar();
        await renderList();
        window.showAlert?.("설계안을 삭제했습니다.");
      } catch (e) {
        console.error("plan bundle delete failed", e);
        window.showAlert?.("설계안 삭제 실패");
      }
    };
    const planBundleSelectorEl = document.getElementById("planBundleSelector");
    const planBundleTriggerEl = document.getElementById("planBundleTrigger");
    const planBundleMenuEl = document.getElementById("planBundleMenu");
    if (planBundleSelectorEl && planBundleTriggerEl && planBundleMenuEl) {
      const closeSelectorMenu = () => planBundleMenuEl.classList.add("hidden");
      planBundleTriggerEl.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (planBundleTriggerEl.disabled) return;
        planBundleMenuEl.classList.toggle("hidden");
      });
      planBundleSelectorEl.addEventListener("click", async (event) => {
        const deleteBtn = event.target?.closest?.("[data-bundle-delete]");
        if (deleteBtn) {
          event.preventDefault();
          event.stopPropagation();
          const bundleKey = String(deleteBtn.getAttribute("data-bundle-delete") || "");
          if (!bundleKey) return;
          await deleteBundleByKey(bundleKey);
          return;
        }
        const itemBtn = event.target?.closest?.("[data-bundle]");
        if (itemBtn) {
          event.preventDefault();
          event.stopPropagation();
          const bundleKey = String(itemBtn.getAttribute("data-bundle") || "");
          if (!bundleKey) return;
          activeBundleKey = bundleKey;
          closeSelectorMenu();
          await renderList();
        }
      });
      planBundleSelectorEl.addEventListener("focusout", (event) => {
        const next = event.relatedTarget;
        if (!next || !planBundleSelectorEl.contains(next)) closeSelectorMenu();
      });
    }

    listEl.querySelectorAll(".plan-item-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const bundleKey = String(btn.dataset.bundle || "");
        const slotKey = String(btn.dataset.slotKey || "");
        if (!bundleKey || !slotKey) return;
        activeItemByBundle.set(bundleKey, slotKey);
        pendingModalOpen = { bundleKey, slotKey };
        await renderList();
      });
    });
    listEl.querySelectorAll(".plan-item-toggle").forEach((btn) => {
      btn.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const bundleKey = String(btn.dataset.bundle || "");
        const slotKey = String(btn.dataset.slotKey || "");
        if (!bundleKey || !slotKey) return;
        const cKey = completionKeyOf(bundleKey, slotKey);
        const next = !planCompleteMap[cKey];
        if (next) planCompleteMap[cKey] = true;
        else delete planCompleteMap[cKey];
        persistPlanCompleteMap();
        await renderCalendar();
        await renderList();
      });
    });

    const bindPlanRowActions = (rootEl) => {
      if (!rootEl) return;
      if (rootEl.dataset.planRowBound === "1") return;
      rootEl.dataset.planRowBound = "1";
      rootEl.addEventListener("click", async (event) => {
        const editBtn = event.target?.closest?.(".plan-edit");
        if (editBtn && rootEl.contains(editBtn)) {
          event.preventDefault();
          event.stopPropagation();
          const id = String(editBtn.dataset.id || "");
          const row = rowById.get(id);
          if (!row) return;
          const inDetailModal = rootEl === planDetailModalBodyEl;
          if (!inDetailModal) {
            closePlanDetailModal();
            openItemModal("edit", row);
            return;
          }
          const article = editBtn.closest(".plan-row");
          if (!article) return;
          if (article.dataset.editing === "1") return;
          article.dataset.editing = "1";
          const parsed = parseScheduleContent(row?.content || "");
          article.innerHTML = `
            <div class="plan-inline-editor">
              <label>리뷰 결과
                <textarea class="input plan-inline-draft" rows="8" autofocus>${esc(parsed.draft || "")}</textarea>
              </label>
              <div class="plan-row-actions">
                <button type="button" class="plan-inline-save" data-id="${row.id}">저장</button>
                <button type="button" class="plan-inline-cancel" data-id="${row.id}">취소</button>
              </div>
            </div>
          `;
          return;
        }

        const inlineSaveBtn = event.target?.closest?.(".plan-inline-save");
        if (inlineSaveBtn && rootEl.contains(inlineSaveBtn)) {
          event.preventDefault();
          event.stopPropagation();
          const id = String(inlineSaveBtn.dataset.id || "");
          const row = rowById.get(id);
          const article = inlineSaveBtn.closest(".plan-row");
          if (!id || !row || !article) return;
          const draft = String(article.querySelector(".plan-inline-draft")?.value || "").trim();
          const payload = { draft };
          try {
            const headers = await buildAuthHeaders();
            const res = await fetch(`${API_BASE}/api/data/review-schedules/${id}/`, {
              method: "PATCH",
              credentials: "include",
              headers: { ...headers, "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            });
            if (!res.ok) {
              window.showAlert?.("스케줄 수정 실패");
              return;
            }
            const updated = await res.json();
            rowById.set(id, updated);
            article.dataset.editing = "0";
            article.innerHTML = renderRowReadHtml(updated, parseScheduleContent(updated?.content || ""));
            clearAllCache();
            await renderCalendar();
          } catch (e) {
            console.error("review schedule inline edit failed", e);
            showInlineEditStatus(article, "저장에 실패했습니다. 다시 시도해주세요.", true);
          }
          return;
        }

        const inlineCancelBtn = event.target?.closest?.(".plan-inline-cancel");
        if (inlineCancelBtn && rootEl.contains(inlineCancelBtn)) {
          event.preventDefault();
          event.stopPropagation();
          const id = String(inlineCancelBtn.dataset.id || "");
          const row = rowById.get(id);
          const article = inlineCancelBtn.closest(".plan-row");
          if (!row || !article) return;
          article.dataset.editing = "0";
          article.innerHTML = renderRowReadHtml(row, parseScheduleContent(row?.content || ""));
          return;
        }

        const deleteBtn = event.target?.closest?.(".plan-delete");
        if (deleteBtn && rootEl.contains(deleteBtn)) {
          event.preventDefault();
          event.stopPropagation();
          const id = String(deleteBtn.dataset.id || "");
          if (!id) return;
          try {
            const headers = await buildAuthHeaders();
            const res = await fetch(`${API_BASE}/api/data/review-schedules/${id}/`, {
              method: "DELETE",
              credentials: "include",
              headers,
            });
            if (!res.ok) {
              window.showAlert?.("스케줄 삭제 실패");
              return;
            }
            clearAllCache();
            await renderCalendar();
            await renderList();
          } catch (e) {
            console.error("review schedule delete failed", e);
            window.showAlert?.("스케줄 삭제 실패");
          }
        }
      });
    };
    bindPlanRowActions(listEl);
    bindPlanRowActions(planDetailModalBodyEl);

    if (modalPayload) {
      openPlanDetailModal(modalPayload);
      pendingModalOpen = null;
    }
  };

  const renderCalendar = async () => {
    const mKey = monthKey(currentMonthDate);
    const rows = await fetchSchedules(mKey);
    monthLabelEl.textContent = monthTitle(currentMonthDate);

    const counts = rows.reduce((acc, row) => {
      const key = normalizeScheduleDateKey(row.date || "");
      if (!key) return acc;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const titlesByDate = rows.reduce((acc, row) => {
      const key = normalizeScheduleDateKey(row.date || "");
      if (!key) return acc;
      const parsed = parseScheduleContent(row?.content || "");
      const bKey = parsed.planId ? `plan-${parsed.planId}` : `single-${row?.id}`;
      const sKey = slotKeyOfLabel(parsed.label);
      const completed = !!(bKey && sKey && planCompleteMap[completionKeyOf(bKey, sKey)]);
      const rawTitle = String(row?.plan_title || "").trim();
      const title = rawTitle || "설계안";
      if (!acc[key]) acc[key] = [];
      const existing = acc[key].find((item) => item.title === title);
      if (existing) {
        existing.completed = existing.completed || completed;
      } else {
        acc[key].push({ title, completed });
      }
      return acc;
    }, {});

    const y = currentMonthDate.getFullYear();
    const m = currentMonthDate.getMonth();
    const firstDay = new Date(y, m, 1);
    const lastDay = new Date(y, m + 1, 0);
    const weekLabels = ["월", "화", "수", "목", "금"];

    const startMonday = new Date(firstDay);
    const startDay = startMonday.getDay(); // 0-6
    const deltaToMonday = startDay === 0 ? -6 : 1 - startDay;
    startMonday.setDate(startMonday.getDate() + deltaToMonday);

    const endFriday = new Date(lastDay);
    const endDay = endFriday.getDay(); // 0-6
    const deltaToFriday = endDay === 0 ? -2 : 5 - endDay;
    endFriday.setDate(endFriday.getDate() + deltaToFriday);

    const cells = [];
    for (let d = new Date(startMonday); d <= endFriday; d.setDate(d.getDate() + 1)) {
      const weekday = d.getDay();
      if (weekday === 0 || weekday === 6) continue; // weekend hidden
      const inMonth = d.getMonth() === m;
      if (!inMonth) {
        cells.push(`<div class="calendar-cell muted"></div>`);
        continue;
      }
      const key = toYmd(d);
      const count = counts[key] || 0;
      const isSelected = key === selectedDate;
      const dayTitles = titlesByDate[key] || [];
      const dayTitlesHtml = dayTitles.length
        ? `
          <div class="calendar-plan-titles">
            ${dayTitles.slice(0, 2).map((item) => `<span class="calendar-plan-title ${item.completed ? "completed" : ""}">${esc(item.title)}</span>`).join("")}
            ${dayTitles.length > 2 ? `<span class="calendar-plan-more">+${dayTitles.length - 2}</span>` : ""}
          </div>
        `
        : "";
      cells.push(`
        <button type="button" class="calendar-cell review-day ${isSelected ? "selected" : ""}" data-date="${key}">
          <span class="calendar-day">${d.getDate()}</span>
          ${count ? `<span class="calendar-count">${count}건</span>` : ""}
          ${dayTitlesHtml}
        </button>
      `);
    }

    while (cells.length % 5 !== 0) cells.push(`<div class="calendar-cell muted"></div>`);

    const header = weekLabels.map((label) => `<div class="calendar-head">${label}</div>`).join("");
    calendarEl.innerHTML = `<div class="calendar-grid">${header}${cells.join("")}</div>`;
  };

  // Event delegation: survives calendar re-render and prevents click handler loss.
  calendarEl.addEventListener("click", async (e) => {
    const btn = e.target?.closest?.(".review-day[data-date]");
    if (!btn || !calendarEl.contains(btn)) return;
    e.preventDefault();
    const nextDate = String(btn.dataset.date || "").trim();
    if (!nextDate) return;
    selectedDate = nextDate;

    const allRows = (await fetchSchedules()).filter(
      (row) => normalizeScheduleDateKey(row?.date || "") === nextDate
    );
    pendingModalOpen = null;

    await renderCalendar();
    if (hasPlanList) {
      await renderList();
      listEl.scrollTop = 0;
    }

    if (allRows.length) {
      const sortedRows = allRows.sort((a, b) => Number(a?.id || 0) - Number(b?.id || 0));
      openPlanDetailModal({
        title: `${nextDate} 리뷰 상세 (${sortedRows.length}건)`,
        bodyHtml: renderCalendarDayRows(sortedRows),
      });
    } else {
      openPlanDetailModal({
        title: `${nextDate} 리뷰 상세`,
        bodyHtml: `<div class="plan-empty"><strong>해당 날짜의 리뷰가 없습니다.</strong></div>`,
      });
    }
  });

  const closeGenerateModal = () => {
    generateModal?.classList.add("hidden");
  };
  const openGenerateModal = () => {
    if (!generateModal) return;
    generateModal.classList.remove("hidden");
  };

  if (generateModal) {
    const modalCard = generateModal.querySelector(".modal-card");
    modalCard?.addEventListener("pointerdown", (e) => e.stopPropagation());
    modalCard?.addEventListener("click", (e) => e.stopPropagation());
    generateModal.addEventListener("click", (e) => {
      if (e.target === generateModal || e.target?.dataset?.close) closeGenerateModal();
    });
    generateModal.querySelectorAll('[data-close="true"]').forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeGenerateModal();
      });
    });
    if (planGroupsWrapEl && planGroupsWrapEl.dataset.bound !== "1") {
      planGroupsWrapEl.dataset.bound = "1";
      planGroupsWrapEl.querySelectorAll(".stage-chip").forEach((chip) => {
        chip.addEventListener("click", () => chip.classList.toggle("is-active"));
      });
    }
  }

  if (itemModal) {
    const modalCard = itemModal.querySelector(".modal-card");
    modalCard?.addEventListener("pointerdown", (e) => e.stopPropagation());
    modalCard?.addEventListener("click", (e) => e.stopPropagation());
    itemModal.addEventListener("click", (e) => {
      if (e.target === itemModal || e.target?.dataset?.close) closeItemModal();
    });
    itemModal.querySelectorAll('[data-close="true"]').forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeItemModal();
      });
    });
  }

  if (planDetailModal) {
    const modalCard = planDetailModal.querySelector(".modal-card");
    modalCard?.addEventListener("pointerdown", (e) => e.stopPropagation());
    modalCard?.addEventListener("click", (e) => e.stopPropagation());
    planDetailModal.addEventListener("click", (e) => {
      if (e.target === planDetailModal || e.target?.dataset?.close) closePlanDetailModal();
    });
    planDetailModal.querySelectorAll('[data-close="true"]').forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        closePlanDetailModal();
      });
    });
  }

  openAddBtn?.addEventListener("click", () => openItemModal("create"));
  itemSaveBtn?.addEventListener("click", async () => {
    const date = (itemDateEl?.value || "").trim();
    const label = (itemLabelEl?.value || "").trim();
    const detail = (itemDetailEl?.value || "").trim();
    const draft = (itemDraftEl?.value || "").trim();
    if (!date || !label || !detail) {
      window.showAlert?.("날짜/단계명/설계 포인트를 입력하세요.");
      return;
    }

    const remindAt = (() => {
      const fp = itemRemindEl?._flatpickr;
      if (fp?.selectedDates?.length) return fp.selectedDates[0];
      return itemRemindEl?.value ? new Date(itemRemindEl.value) : null;
    })();

    const payload = { date, label, detail, draft };
    if (remindAt && !Number.isNaN(remindAt.valueOf())) {
      payload.remind_at = remindAt.toISOString();
    }

    try {
      const headers = await buildAuthHeaders();
      const isEdit = !!editingScheduleId;
      const url = isEdit
        ? `${API_BASE}/api/data/review-schedules/${editingScheduleId}/`
        : `${API_BASE}/api/data/review-schedules/`;
      const method = isEdit ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        window.showAlert?.(isEdit ? "스케줄 수정 실패" : "스케줄 추가 실패");
        return;
      }

      const [y, m] = date.split("-").map((v) => Number(v));
      if (Number.isFinite(y) && Number.isFinite(m)) {
        currentMonthDate = new Date(y, m - 1, 1);
      }
      selectedDate = date;
      clearAllCache();
      closeItemModal();
      await renderCalendar();
      if (hasPlanList) await renderList();
      window.showAlert?.(isEdit ? "스케줄을 수정했습니다." : "스케줄을 추가했습니다.");
    } catch (e) {
      console.error("review schedule save failed", e);
      window.showAlert?.("스케줄 저장 실패");
    }
  });

  openGenerateBtn?.addEventListener("click", openGenerateModal);
  generateConfirmBtn?.addEventListener("click", async () => {
    const planTitle = String(planTitleInputEl?.value || "").trim();
    if (!planTitle) {
      window.showAlert?.("설계안 제목은 필수입니다.");
      return;
    }
    const selectedGroups = Array.from(planGroupsWrapEl?.querySelectorAll(".stage-chip.is-active") || [])
      .map((el) => String(el?.dataset?.group || "").trim())
      .filter((v) => !!v);
    const payload = {
      plan_title: planTitle,
      keywords: String(personaKeywordsInputEl?.value || "").trim(),
      platform_account: String(platformAccountInputEl?.value || "").trim(),
      platform_password: String(platformPasswordInputEl?.value || "").trim(),
      plan_groups: selectedGroups,
      model: "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    };
    try {
      const headers = await buildAuthHeaders();
      const res = await fetch(`${API_BASE}/api/ml/agent/review-plan-generate/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        window.showAlert?.(String(data?.error || "스케줄 생성 실패"));
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (data?.ok !== true) {
        window.showAlert?.(String(data?.error || "스케줄 생성 실패"));
        return;
      }
      clearAllCache();
      closeGenerateModal();
      await renderCalendar();
      if (hasPlanList) await renderList();
      window.showAlert?.("리뷰 스케줄 설계를 생성했습니다.");
    } catch (e) {
      console.error("review schedule generate failed", e);
      window.showAlert?.("스케줄 생성 실패");
    }
  });

  prevBtn?.addEventListener("click", async () => {
    currentMonthDate = new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth() - 1, 1);
    await renderCalendar();
      if (hasPlanList) await renderList();
  });
  nextBtn?.addEventListener("click", async () => {
    currentMonthDate = new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth() + 1, 1);
    await renderCalendar();
      if (hasPlanList) await renderList();
  });

  window.addEventListener("review-schedules-updated", async () => {
    clearAllCache();
    await renderCalendar();
    if (hasPlanList) await renderList();
  });

  renderCalendar();
  if (hasPlanList) renderList();
}

function initMemoPanel() {
  const listEl = document.getElementById("myMemoList");
  const remindEl = document.getElementById("myMemoRemind");
  const titleEl = document.getElementById("myMemoTitle");
  const contentEl = document.getElementById("myMemoContent");
  const saveBtn = document.getElementById("myMemoSave");
  const createBtn = document.getElementById("myMemoCreate");
  const deleteBtn = document.getElementById("myMemoDelete");
  if (!listEl || !contentEl || !titleEl) return;

  const state = {
    items: [],
    selectedId: null,
    selectedDate: toYmd(new Date()),
    isCreating: false,
  };
  let autoSaveTimer = null;
  let isSaving = false;
  let needsResave = false;
  let lastSnapshot = "";
  const toLocalDateTimeInputValue = (value) => {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.valueOf())) return "";
    const local = new Date(d.getTime() - (d.getTimezoneOffset() * 60000));
    return local.toISOString().slice(0, 16);
  };

  const splitMemoContent = (raw) => {
    const text = String(raw || "");
    const lines = text.split("\n");
    const first = String(lines[0] || "").trim();
    const m = first.match(/^제목\s*:\s*(.+)$/i);
    if (m) {
      return {
        title: String(m[1] || "").trim(),
        body: lines.slice(1).join("\n").trim(),
      };
    }
    return { title: "", body: text.trim() };
  };

  const selectMemo = (item) => {
    state.isCreating = false;
    state.selectedId = item?.id || null;
    state.selectedDate = item?.date || toYmd(new Date());
    const parsed = splitMemoContent(item?.content || "");
    titleEl.value = parsed.title || "";
    contentEl.value = parsed.body || "";
    if (remindEl) remindEl.value = toLocalDateTimeInputValue(item?.remind_at);
    const remindKey = item?.remind_at ? new Date(item.remind_at).toISOString() : "";
    lastSnapshot = JSON.stringify({
      id: state.selectedId || 0,
      date: state.selectedDate || "",
      title: titleEl.value,
      content: contentEl.value,
      remind: remindKey,
    });
  };

  const renderMemoList = () => {
    if (!state.items.length) {
      listEl.innerHTML = `<div class="muted">메모가 없습니다.</div>`;
      return;
    }
    const rows = [...state.items].sort((a, b) => {
      const at = new Date(a?.updated_at || a?.created_at || 0).getTime() || 0;
      const bt = new Date(b?.updated_at || b?.created_at || 0).getTime() || 0;
      return bt - at;
    });
    if (!state.isCreating && !rows.some((x) => Number(x.id) === Number(state.selectedId))) {
      state.selectedId = rows[0]?.id || null;
    }
    listEl.innerHTML = rows.map((item) => {
      const parsed = splitMemoContent(item.content);
      const active = Number(item.id) === Number(state.selectedId) ? "active" : "";
      const dt = formatDateTimePartsKst(item.created_at || item.updated_at || item.remind_at);
      return `
        <button type="button" class="my-memo-row ${active}" data-id="${item.id}">
          <div class="my-memo-row-head">
            <div class="my-memo-row-title">${escapeHtml(parsed.title || "새로운 메모")}</div>
            <div class="my-memo-row-time">
              <div class="my-memo-row-date">${dt.date}</div>
              <div class="my-memo-row-clock">${dt.time}</div>
            </div>
          </div>
        </button>
      `;
    }).join("");
    listEl.querySelectorAll(".my-memo-row").forEach((row) => {
      row.addEventListener("click", () => {
        const id = Number(row.dataset.id);
        const item = state.items.find((x) => Number(x.id) === id);
        if (!item) return;
        selectMemo(item);
        renderMemoList();
      });
    });
  };

  const fetchMemos = async () => {
    try {
      const headers = await buildAuthHeaders();
      const res = await fetch(`${API_BASE}/api/data/calendar-memos/?limit=300`, {
        credentials: "include",
        headers,
      });
      if (!res.ok) {
        state.items = [];
        renderMemoList();
        return;
      }
      const data = await res.json();
      state.items = Array.isArray(data?.results) ? data.results : [];
      renderMemoList();
      const selected = state.items.find((x) => Number(x.id) === Number(state.selectedId));
      if (selected) selectMemo(selected);
      else if (state.items[0]) selectMemo(state.items[0]);
      else createNewMemo();
    } catch (e) {
      console.error("memo fetch failed", e);
      state.items = [];
      renderMemoList();
    }
  };

  const createNewMemo = () => {
    state.isCreating = true;
    state.selectedId = null;
    state.selectedDate = toYmd(new Date());
    titleEl.value = "";
    contentEl.value = "";
    if (remindEl) remindEl.value = "";
    lastSnapshot = JSON.stringify({
      id: 0,
      date: state.selectedDate || "",
      title: "",
      content: "",
      remind: "",
    });
    renderMemoList();
  };

  const saveMemo = async ({ force = false } = {}) => {
    const date = state.selectedDate || toYmd(new Date());
    const title = String(titleEl.value || "").trim();
    const content = String(contentEl.value || "").trim();
    if (!title || !content) {
      if (force) window.showAlert?.("메모 제목/내용을 입력하세요.");
      return;
    }

    const remindAt = (() => {
      const raw = String(remindEl?.value || "").trim();
      if (!raw) return null;
      const d = new Date(raw);
      return Number.isNaN(d.valueOf()) ? null : d;
    })();
    const snapshot = JSON.stringify({
      id: Number(state.selectedId) || 0,
      date,
      title,
      content,
      remind: remindAt ? remindAt.toISOString() : "",
    });
    if (!force && snapshot === lastSnapshot) {
      return;
    }
    if (isSaving) {
      needsResave = true;
      return;
    }
    isSaving = true;
    try {
      const headers = await buildAuthHeaders();
      const payload = {
        date,
        content: `제목: ${title}\n${content}`,
      };
      if (remindAt) payload.remind_at = remindAt.toISOString();
      const isEdit = Number.isFinite(Number(state.selectedId)) && Number(state.selectedId) > 0;
      const endpoint = isEdit
        ? `${API_BASE}/api/data/calendar-memos/${state.selectedId}/`
        : `${API_BASE}/api/data/calendar-memos/`;
      const res = await fetch(endpoint, {
        method: isEdit ? "PATCH" : "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        if (force) window.showAlert?.("메모 저장 실패");
        return;
      }
      if (!isEdit) state.isCreating = false;
      lastSnapshot = snapshot;
      await fetchMemos();
    } catch (e) {
      console.error("memo save failed", e);
      if (force) window.showAlert?.("메모 저장 실패");
    } finally {
      isSaving = false;
      if (needsResave) {
        needsResave = false;
        saveMemo({ force: false });
      }
    }
  };

  const scheduleAutoSave = (delay = 500) => {
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(() => {
      saveMemo({ force: false });
    }, delay);
  };

  saveBtn?.addEventListener("click", async () => {
    await saveMemo({ force: true });
  });

  titleEl.addEventListener("input", scheduleAutoSave);
  contentEl.addEventListener("input", scheduleAutoSave);
  const commitReminder = async () => {
    await saveMemo({ force: true });
  };
  remindEl?.addEventListener("change", commitReminder);
  remindEl?.addEventListener("blur", commitReminder);
  remindEl?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    commitReminder();
  });

  createBtn?.addEventListener("click", () => {
    createNewMemo();
  });

  deleteBtn?.addEventListener("click", async () => {
    if (!state.selectedId) {
      window.showAlert?.("삭제할 메모를 선택하세요.");
      return;
    }
    try {
      const headers = await buildAuthHeaders();
      const res = await fetch(`${API_BASE}/api/data/calendar-memos/${state.selectedId}/`, {
        method: "DELETE",
        credentials: "include",
        headers,
      });
      if (!res.ok) {
        window.showAlert?.("메모 삭제 실패");
        return;
      }
      state.selectedId = null;
      await fetchMemos();
    } catch (e) {
      console.error("memo delete failed", e);
      window.showAlert?.("메모 삭제 실패");
    }
  });

  createNewMemo();
  fetchMemos();
}

function initMyMailPanel() {
  const tabsRoot = document.getElementById("myMailTabs");
  const listEl = document.getElementById("myMailList");
  const composeBtn = document.getElementById("myMailComposeBtn");
  const detailEmptyEl = document.getElementById("myMailDetailEmpty");
  const detailBodyEl = document.getElementById("myMailDetailBody");
  const detailTitleEl = document.getElementById("myMailDetailTitle");
  const detailMetaEl = document.getElementById("myMailDetailMeta");
  const detailContentEl = document.getElementById("myMailDetailContent");
  if (!tabsRoot || !listEl || !detailBodyEl) return;

  composeBtn?.addEventListener("click", () => {
    window.location.href = "mail_center.html";
  });

  const state = {
    box: "inbox",
    items: [],
    selectedId: null,
  };

  const setTabs = () => {
    tabsRoot.querySelectorAll("button[data-box]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.box === state.box);
    });
  };

  const renderDetail = () => {
    const item = state.items.find((x) => Number(x.id) === Number(state.selectedId));
    if (!item) {
      detailBodyEl.classList.add("hidden");
      detailEmptyEl?.classList.remove("hidden");
      return;
    }
    if (detailTitleEl) detailTitleEl.textContent = item.subject || "제목 없음";
    if (detailMetaEl) {
      const sender = item.sender_name || "발신자";
      const receiver = item.recipient_name || "수신자";
      detailMetaEl.textContent = `${sender} → ${receiver} · ${formatDateTimeKst(item.created_at)}`;
    }
    if (detailContentEl) {
      detailContentEl.innerHTML = escapeHtml(item.content || "").replaceAll("\n", "<br>");
    }
    detailEmptyEl?.classList.add("hidden");
    detailBodyEl.classList.remove("hidden");
  };

  const renderList = () => {
    if (!Array.isArray(state.items) || !state.items.length) {
      listEl.innerHTML = `<div class="muted">표시할 메일이 없습니다.</div>`;
      state.selectedId = null;
      renderDetail();
      return;
    }
    const rows = [...state.items].sort((a, b) => {
      const at = new Date(a?.created_at || 0).getTime() || 0;
      const bt = new Date(b?.created_at || 0).getTime() || 0;
      return bt - at;
    });
    if (!rows.some((x) => Number(x.id) === Number(state.selectedId))) {
      state.selectedId = rows[0]?.id || null;
    }
    listEl.innerHTML = rows
      .map((item) => {
        const active = Number(item.id) === Number(state.selectedId) ? "active" : "";
        const subject = escapeHtml(item.subject || "제목 없음");
        const preview = escapeHtml((item.content || "").slice(0, 70));
        return `
          <button type="button" class="my-mail-row ${active}" data-id="${item.id}">
            <div class="my-mail-row-title">${subject}</div>
            <div class="my-mail-row-preview">${preview}</div>
            <div class="my-mail-row-meta">${formatDateTimeKst(item.created_at)}</div>
          </button>
        `;
      })
      .join("");

    listEl.querySelectorAll(".my-mail-row").forEach((row) => {
      row.addEventListener("click", () => {
        state.selectedId = Number(row.dataset.id);
        renderList();
        renderDetail();
      });
    });
    renderDetail();
  };

  const fetchBox = async () => {
    try {
      const headers = await buildAuthHeaders();
      const res = await fetch(`${API_BASE}/api/data/messages/?box=${encodeURIComponent(state.box)}&limit=200`, {
        credentials: "include",
        headers,
      });
      if (!res.ok) {
        state.items = [];
        renderList();
        return;
      }
      const data = await res.json();
      state.items = Array.isArray(data?.results) ? data.results : [];
      renderList();
    } catch (e) {
      console.error("mail fetch failed", e);
      state.items = [];
      renderList();
    }
  };

  tabsRoot.querySelectorAll("button[data-box]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      state.box = btn.dataset.box || "inbox";
      state.selectedId = null;
      setTabs();
      await fetchBox();
    });
  });

  setTabs();
  fetchBox();
}


function initMyDashboardPage() {
  if (window.__myDashboardPageInitialized) return;
  window.__myDashboardPageInitialized = true;
  renderMyDashboard();
  initSectionDrag();
  initAttendancePanel();
  initMyWorkspaceNav();
  initReviewSchedulePlanner();
  initMemoPanel();
  initMyMailPanel();

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
      monthOffset -= 1;
      renderMyDashboard();
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      monthOffset += 1;
      renderMyDashboard();
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initMyDashboardPage, { once: true });
} else {
  initMyDashboardPage();
}

function initMyWorkspaceNav() {
  const navRoot = document.getElementById("mySectionNav");
  const sectionRoot = document.getElementById("myDashboardSections");
  if (!navRoot || !sectionRoot) return;
  const storageKey = "myDashboard::sections";
  const getNavButtons = () => Array.from(navRoot.querySelectorAll(".my-section-nav-btn[data-section-key]"));
  const getSections = () => Array.from(sectionRoot.querySelectorAll(".section-block[data-section-key]"));
  if (!getNavButtons().length || !getSections().length) return;

  const animateReorder = (rootEl, selector) => {
    const items = Array.from(rootEl.querySelectorAll(selector));
    const firstRects = new Map(items.map((el) => [el, el.getBoundingClientRect()]));
    return () => {
      items.forEach((el) => {
        const first = firstRects.get(el);
        if (!first) return;
        const last = el.getBoundingClientRect();
        const dx = first.left - last.left;
        const dy = first.top - last.top;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
        el.animate(
          [
            { transform: `translate(${dx}px, ${dy}px)` },
            { transform: "translate(0, 0)" },
          ],
          {
            duration: 190,
            easing: "cubic-bezier(0.22, 1, 0.36, 1)",
          },
        );
      });
    };
  };

  const applyOrderToNavFromStorage = () => {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return;
    try {
      const order = JSON.parse(raw);
      if (!Array.isArray(order)) return;
      order.forEach((key) => {
        const btn = navRoot.querySelector(`.my-section-nav-btn[data-section-key="${key}"]`);
        if (btn) navRoot.appendChild(btn);
      });
    } catch (_e) {
      // ignore parse errors
    }
  };
  applyOrderToNavFromStorage();

  const syncSectionsAndSaveFromNav = () => {
    const playSectionFlip = animateReorder(sectionRoot, ".section-block[data-section-key]");
    const order = getNavButtons().map((btn) => btn.dataset.sectionKey).filter(Boolean);
    order.forEach((key) => {
      const section = sectionRoot.querySelector(`.section-block[data-section-key="${key}"]`);
      if (section) sectionRoot.appendChild(section);
    });
    playSectionFlip();
    try {
      localStorage.setItem(storageKey, JSON.stringify(order));
    } catch (_e) {
      // ignore storage errors
    }
  };

  const setActive = (sectionKey) => {
    const navButtons = getNavButtons();
    const sections = getSections();
    navButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.sectionKey === sectionKey);
    });
    sections.forEach((section) => {
      const isMatch = section.dataset.sectionKey === sectionKey;
      section.classList.toggle("workspace-hidden", !isMatch);
      section.classList.remove("workspace-active");
      if (isMatch) {
        const body = section.querySelector(".section-body");
        const toggle = section.querySelector(".section-toggle");
        if (body) body.classList.add("open");
        if (toggle) toggle.setAttribute("aria-expanded", "true");
        requestAnimationFrame(() => {
          section.classList.add("workspace-active");
        });
      }
    });
  };

  const bindNavClicks = () => {
    const navButtons = getNavButtons();
    navButtons.forEach((btn) => {
      if (btn.dataset.boundClick === "1") return;
      btn.dataset.boundClick = "1";
      btn.addEventListener("click", () => {
        const key = btn.dataset.sectionKey;
        if (!key) return;
        setActive(key);
      });
    });
  };
  bindNavClicks();

  const initNavDrag = () => {
    let dragBtn = null;
    let isDragging = false;
    let dropTarget = null;
    let dropBefore = true;

    const clearHover = () => {
      getNavButtons().forEach((btn) => {
        btn.classList.remove("nav-drag-over-before", "nav-drag-over-after");
      });
    };

    const onMouseMove = (event) => {
      if (!isDragging || !dragBtn) return;
      const element = document.elementFromPoint(event.clientX, event.clientY);
      const target = element?.closest?.(".my-section-nav-btn[data-section-key]");
      if (!target || target === dragBtn) return;
      const rect = target.getBoundingClientRect();
      dropBefore = event.clientY < rect.top + rect.height / 2;
      dropTarget = target;
      clearHover();
      target.classList.add(dropBefore ? "nav-drag-over-before" : "nav-drag-over-after");
    };

    const onMouseUp = () => {
      if (!isDragging) return;
      isDragging = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      if (dragBtn) dragBtn.classList.remove("nav-dragging");
      clearHover();
      if (dragBtn && dropTarget && dragBtn !== dropTarget) {
        const playNavFlip = animateReorder(navRoot, ".my-section-nav-btn[data-section-key]");
        navRoot.insertBefore(dragBtn, dropBefore ? dropTarget : dropTarget.nextSibling);
        playNavFlip();
        syncSectionsAndSaveFromNav();
        bindNavClicks();
      }
      dragBtn = null;
      dropTarget = null;
    };

    navRoot.querySelectorAll(".nav-drag-handle").forEach((handle) => {
      if (handle.dataset.boundDrag === "1") return;
      handle.dataset.boundDrag = "1";
      handle.addEventListener("mousedown", (event) => {
        const btn = event.currentTarget.closest(".my-section-nav-btn[data-section-key]");
        if (!btn) return;
        event.preventDefault();
        event.stopPropagation();
        dragBtn = btn;
        isDragging = true;
        dragBtn.classList.add("nav-dragging");
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      });
      handle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
      });
    });
  };
  initNavDrag();

  const defaultKey = getNavButtons()[0]?.dataset.sectionKey;
  if (defaultKey) setActive(defaultKey);
}

function initSectionDrag() {
  const container = document.getElementById("myDashboardSections");
  if (!container) return;
  const storageKey = "myDashboard::sections";

  const applyStoredOrder = () => {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return;
    try {
      const order = JSON.parse(raw);
      if (!Array.isArray(order)) return;
      order.forEach((key) => {
        const el = container.querySelector(`[data-section-key="${key}"]`);
        if (el) container.appendChild(el);
      });
    } catch (e) {
      console.warn("section order parse failed", e);
    }
  };

  applyStoredOrder();

  let dragItem = null;
  let isDragging = false;
  let ghost = null;
  let dropTarget = null;
  let dropBefore = true;

  const persistOrder = () => {
    const order = Array.from(container.querySelectorAll(".section-block"))
      .map((el) => el.dataset.sectionKey)
      .filter(Boolean);
    localStorage.setItem(storageKey, JSON.stringify(order));
  };

  const clearHover = () => {
    container.querySelectorAll(".section-block").forEach((block) => {
      block.classList.remove("drag-over");
      block.classList.remove("drag-over-before");
      block.classList.remove("drag-over-after");
    });
  };

  const onMouseMove = (event) => {
    if (!isDragging || !dragItem) return;
    if (ghost) {
      ghost.style.top = `${event.clientY - ghost.dataset.offsetY}px`;
      ghost.style.left = `${event.clientX - ghost.dataset.offsetX}px`;
    }

    const element = document.elementFromPoint(event.clientX, event.clientY);
    const target = element?.closest?.(".section-block");
    if (!target || target === dragItem) return;

    const rect = target.getBoundingClientRect();
    dropBefore = event.clientY < rect.top + rect.height / 2;
    dropTarget = target;
    clearHover();
    target.classList.add("drag-over");
    target.classList.add(dropBefore ? "drag-over-before" : "drag-over-after");
  };

  const onMouseUp = () => {
    if (!isDragging) return;
    isDragging = false;
    const movingItem = dragItem;
    if (movingItem) movingItem.classList.remove("dragging");
    clearHover();
    document.body.classList.remove("dragging-sections");
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
    if (ghost) {
      ghost.remove();
      ghost = null;
    }
    if (dropTarget && movingItem) {
      container.insertBefore(movingItem, dropBefore ? dropTarget : dropTarget.nextSibling);
    } else if (dropTarget) {
      const lastDragging = container.querySelector(".section-block.dragging");
      if (lastDragging) {
        container.insertBefore(lastDragging, dropBefore ? dropTarget : dropTarget.nextSibling);
      }
    }
    dropTarget = null;
    dragItem = null;
    persistOrder();
  };

  container.querySelectorAll(".section-drag-handle").forEach((handle) => {
    handle.addEventListener("mousedown", (event) => {
      const target = event.currentTarget.closest(".section-block");
      if (!target) return;
      event.preventDefault();
      isDragging = true;
      dragItem = target;
      dragItem.classList.add("dragging");
      document.body.classList.add("dragging-sections");
      ghost = target.cloneNode(true);
      ghost.classList.add("section-ghost");
      ghost.style.width = `${target.getBoundingClientRect().width}px`;
      const rect = target.getBoundingClientRect();
      const offsetY = event.clientY - rect.top;
      const offsetX = event.clientX - rect.left;
      ghost.dataset.offsetY = offsetY;
      ghost.dataset.offsetX = offsetX;
      ghost.style.top = `${rect.top}px`;
      ghost.style.left = `${rect.left}px`;
      document.body.appendChild(ghost);
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    });
    handle.addEventListener("click", (event) => event.stopPropagation());
  });
}

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





