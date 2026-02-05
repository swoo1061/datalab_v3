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
      <div class="calendar-cell ${count ? "clickable" : ""}" data-date="${dateStr}">
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

function initMemoCalendar() {
  const listEl = document.getElementById("myMemoList");
  const openBtn = document.getElementById("myMemoOpen");
  const saveBtn = document.getElementById("myMemoSave");
  const modal = document.getElementById("myMemoModal");
  if (!listEl || !openBtn || !saveBtn || !modal) return;

  const platformSelect = document.getElementById("myMemoPlatform");
  if (platformSelect && !platformSelect.options.length) {
    platformSelect.innerHTML = `
      <option value="">플랫폼 선택</option>
      ${PLATFORM_PILLS.map((p) => `<option value="${p.key}">${p.label}</option>`).join("")}
    `;
  }

  const clinicSelect = document.getElementById("myMemoClinicSelect");
  if (clinicSelect) {
    const list = Array.isArray(window.clinics) ? window.clinics : [];
    clinicSelect.innerHTML = list.length
      ? list.map((c) => `<option value="${c.id}">${c.name}</option>`).join("")
      : `<option value="">병원 없음</option>`;
    if (!clinicSelect.value) {
      clinicSelect.value = clinicSelect.options?.[0]?.value || "";
    }
  }

  const today = new Date();
  const toYmd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const currentDate = toYmd(today);
  const getMonthKey = (dateStr) => (dateStr || "").slice(0, 7);
  const currentMonth = getMonthKey(currentDate);
  let memoCache = new Map();

  const fetchCalendarMemos = async (month) => {
    if (!month) return [];
    if (memoCache.has(month)) return memoCache.get(month);
    try {
      const headers = await buildAuthHeaders();
      const params = new URLSearchParams({ month });
      const res = await fetch(`${API_BASE}/api/data/calendar-memos/?${params}`, {
        credentials: "include",
        headers,
      });
      if (!res.ok) return [];
      const data = await res.json();
      const results = data.results || [];
      memoCache.set(month, results);
      return results;
    } catch (e) {
      console.error("memo load failed", e);
      return [];
    }
  };

  const renderList = async () => {
    const memos = await fetchCalendarMemos(currentMonth);
    if (!memos.length) {
      listEl.innerHTML = `<div class="muted">등록된 메모가 없습니다.</div>`;
      return;
    }
    const sorted = memos.slice().sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
    listEl.innerHTML = sorted
      .map((memo) => {
        const timeLabel = memo.remind_at ? new Date(memo.remind_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }) : "";
        const platformLabel = memo.platform ? getPlatformLabel(memo.platform) : "";
        const accountLabel = memo.account ? `ID ${memo.account}` : "";
        const passwordLabel = memo.account_password ? `PW ${memo.account_password}` : "";
        const metaLabel = [platformLabel, timeLabel].filter(Boolean).join(" · ");
        const accountLine = [accountLabel, passwordLabel].filter(Boolean).join(" · ");
        return `
          <div class="memo-item" data-id="${memo.id}">
            <span class="memo-date">${memo.date || "-"}</span>
            <div class="memo-meta">
              <span>${metaLabel || "-"}</span>
              <span></span>
            </div>
            ${accountLine ? `<div class="memo-meta"><span>${accountLine}</span><span></span></div>` : ""}
            <div class="memo-content">${memo.content}</div>
            <div class="memo-actions">
              <button class="memo-delete" data-id="${memo.id}">삭제</button>
            </div>
          </div>
        `;
      })
      .join("");

    listEl.querySelectorAll(".memo-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const memoId = btn.dataset.id;
        if (!memoId) return;
        try {
          const headers = await buildAuthHeaders();
          const res = await fetch(`${API_BASE}/api/data/calendar-memos/${memoId}/`, {
            method: "DELETE",
            credentials: "include",
            headers,
          });
          if (!res.ok) {
            window.showAlert?.("메모 삭제 실패");
            return;
          }
          memoCache.delete(currentMonth);
          renderList();
        } catch (e) {
          console.error("memo delete failed", e);
          window.showAlert?.("메모 삭제 실패");
        }
      });
    });
  };

  const openModal = () => {
    modal.classList.remove("hidden");
  };

  const closeModal = (target) => {
    if (target?.dataset?.close) {
      modal.classList.add("hidden");
    }
  };

  modal.addEventListener("click", (e) => closeModal(e.target));
  openBtn.addEventListener("click", openModal);
  saveBtn.addEventListener("click", () => {
    const contentEl = document.getElementById("myMemoContent");
    const remindEl = document.getElementById("myMemoRemind");
    const platformEl = document.getElementById("myMemoPlatform");
    const clinicSelectEl = document.getElementById("myMemoClinicSelect");
    const accountEl = document.getElementById("myMemoAccount");
    const passwordEl = document.getElementById("myMemoPassword");
    const content = (contentEl?.value || "").trim();
    if (!content) {
      window.showAlert?.("메모 내용을 입력하세요.");
      return;
    }
    const remindAt = remindEl?.value ? new Date(remindEl.value) : null;
    const dateValue = currentDate;
    const payload = {
      date: dateValue,
      content,
    };
    const clinicId = clinicSelectEl?.value;
    if (clinicId) payload.clinic_id = Number(clinicId);
    if (platformEl?.value) payload.platform = platformEl.value;
    if (accountEl?.value) payload.account = (accountEl.value || "").trim();
    if (passwordEl?.value) payload.account_password = (passwordEl.value || "").trim();
    if (remindAt && !Number.isNaN(remindAt.valueOf())) {
      payload.remind_at = remindAt.toISOString();
    }

    (async () => {
      try {
        const headers = await buildAuthHeaders();
        const res = await fetch(`${API_BASE}/api/data/calendar-memos/`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          window.showAlert?.("메모 저장 실패");
          return;
        }
        memoCache.delete(getMonthKey(dateValue));
        if (contentEl) contentEl.value = "";
        if (remindEl) remindEl.value = "";
        if (platformEl) platformEl.value = "";
        if (clinicSelectEl) clinicSelectEl.value = clinicSelectEl.options?.[0]?.value || "";
        if (accountEl) accountEl.value = "";
        if (passwordEl) passwordEl.value = "";
        modal.classList.add("hidden");
        renderList();
      } catch (e) {
        console.error("memo save failed", e);
        window.showAlert?.("메모 저장 실패");
      }
    })();
  });

  renderList();
}


document.addEventListener("DOMContentLoaded", renderMyDashboard);
document.addEventListener("DOMContentLoaded", () => {
  initSectionDrag();
  initMemoCalendar();
  initAttendancePanel();
  initMyWorkspaceNav();

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
});

function initMyWorkspaceNav() {
  const navButtons = document.querySelectorAll("#mySectionNav .my-section-nav-btn");
  const sections = document.querySelectorAll("#myDashboardSections .section-block[data-section-key]");
  if (!navButtons.length || !sections.length) return;

  const setActive = (sectionKey) => {
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

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.sectionKey;
      if (!key) return;
      setActive(key);
    });
  });

  const defaultKey = navButtons[0]?.dataset.sectionKey;
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
