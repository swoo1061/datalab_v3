console.log("header.js loaded");

window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";

// ================================
// 직급 표시용 매핑
// ================================
const POSITION_LABEL = {
  admin: "계정",
  manager: "매니저",
  leader: "팀장",
  ceo: "대표이사",
};

// ================================
// 헤더 로드
// ================================
async function loadHeader(pageTitle = "") {
  // 로그인 페이지에서는 헤더 로직 스킵
  if (window.location.pathname.includes("login")) {
    return;
  }

  const headerRoot = document.getElementById("appHeader");
  if (!headerRoot) return;

  // ----------------
  // 헤더 HTML 로드
  // ----------------
  if (headerRoot.children.length === 0) {
    const res = await fetch("./components/header.html");
    if (!res.ok) {
      console.error("header.html fetch failed");
      return;
    }
    headerRoot.innerHTML = await res.text();
  }

  // ----------------
  // 페이지 타이틀
  // ----------------
  const titleEl = document.getElementById("pageTitle");
  if (titleEl) titleEl.innerText = pageTitle;

  // ----------------
  // 유저 정보
  // ----------------
  let me;
  try {
    me = await window.api.getMe();
  } catch (e) {
    console.warn("getMe failed");
    return;
  }

  const name = me?.name || me?.username || "사용자";
  const rawPosition = me?.position || "";
  const position = POSITION_LABEL[rawPosition] || rawPosition;
  const email = me?.email || "";

  const userNameEl = document.getElementById("userName");
  if (userNameEl) {
    userNameEl.innerText = position ? `${name} ${position}` : name;
  }

  const profileNameEl = document.getElementById("profileName");
  const profilePositionEl = document.getElementById("profilePosition");
  const profileEmailEl = document.getElementById("profileEmail");

  if (profileNameEl) profileNameEl.innerText = name;
  if (profilePositionEl) profilePositionEl.innerText = position;
  if (profileEmailEl) profileEmailEl.innerText = email;

  // ----------------
  // 이벤트 바인딩
  // ----------------
  document
    .getElementById("userChip")
    ?.addEventListener("click", toggleProfile);

  bindProfileMenu();
  // ⭐ 헤더 전용 기능들
  bindGlobalSearch();
  startLiveClock();
  bindNotifications();
}

// ================================
// 프로필 팝업 토글 (🔥 전역)
// ================================
function toggleProfile() {
  const popup = document.getElementById("profilePopup");
  if (popup) popup.classList.toggle("hidden");
}

function closeProfilePopup() {
  const popup = document.getElementById("profilePopup");
  if (popup) popup.classList.add("hidden");
}

// ================================
// 프로필 메뉴
// ================================
function bindProfileMenu() {
  document.querySelectorAll(".menu-item").forEach((item) => {
    item.onclick = () => {
      const action = item.dataset.action;
      if (action === "profile") openProfileInfo();
      if (action === "attendance") alert("출퇴근 기록 준비중");
      if (action === "my_dashboard") window.nav.go("my_dashboard");
    };
  });
}

function applyTheme(theme) {
  const nextTheme = theme || "classic";
  document.body.dataset.theme = nextTheme;
  localStorage.setItem("appTheme", nextTheme);
  document.querySelectorAll(".theme-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === nextTheme);
  });
}

function bindThemeSelector() {
  const saved = localStorage.getItem("appTheme") || "classic";
  applyTheme(saved);
  document.querySelectorAll(".theme-btn").forEach((btn) => {
    btn.addEventListener("click", () => applyTheme(btn.dataset.theme));
  });
}

// ================================
// 로그아웃
// ================================
async function logout() {
  try {
    await window.api.logout();
  } catch (e) {
    console.error("logout failed", e);
  }
  window.nav.go("login");
}

// ================================
// 프로필 정보 모달
// ================================
async function openProfileInfo() {
  let me;
  try {
    me = await window.api.getMe();
  } catch (e) {
    console.error("getMe failed", e);
    return;
  }

  document.getElementById("infoName").innerText = me.name || "-";
  document.getElementById("infoEmail").innerText = me.email || "-";
  document.getElementById("infoPhone").innerText = me.phone || "-";
  document.getElementById("infoBirth").innerText = me.birth_date || "-";

  document.getElementById("profilePopup")?.classList.add("hidden");
  document.getElementById("profileInfoModal")?.classList.remove("hidden");
}

function closeProfileInfo() {
  document.getElementById("profileInfoModal")?.classList.add("hidden");
}

function bindGlobalSearch() {
  const input = document.getElementById("globalSearch");
  if (!input) return;

  input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;

    const q = input.value.trim().toLowerCase();
    if (!q) return;

    // ① 페이지 / 기능 검색
    const pageHit = globalSearchIndex.pages.find(p =>
      p.key.toLowerCase().includes(q)
    );

    if (pageHit) {
      window.nav.go(pageHit.page);
      input.value = "";
      return;
    }

    // ② 대시보드면 업체 필터
    if (window.location.pathname.includes("dashboard")) {
      window.filterClinicsByQuery?.(q);
      return;
    }

    alert("검색 결과가 없습니다");
  });
}

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

let notifyPollTimer = null;
let notifyItemsById = new Map();

function bindNotifications() {
  const button = document.getElementById("notifyButton");
  const dropdown = document.getElementById("notifyDropdown");
  const list = document.getElementById("notifyList");
  const empty = document.getElementById("notifyEmpty");
  const detail = document.getElementById("notifyDetail");
  const backBtn = document.getElementById("notifyBack");

  if (!button || !dropdown || !list || !empty || !detail || !backBtn) return;

  const closeDropdown = () => dropdown.classList.add("hidden");

  button.addEventListener("click", async (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("hidden");
    if (!dropdown.classList.contains("hidden")) {
      await refreshNotifications();
    }
  });

  document.addEventListener("click", (e) => {
    if (dropdown.contains(e.target) || button.contains(e.target)) return;
    closeDropdown();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDropdown();
  });

  backBtn.addEventListener("click", () => {
    detail.classList.add("hidden");
    list.classList.remove("hidden");
    empty.classList.toggle("hidden", list.children.length > 0);
  });

  if (notifyPollTimer) clearInterval(notifyPollTimer);
  notifyPollTimer = setInterval(refreshNotifications, 30000);
  refreshNotifications();
}

async function refreshNotifications() {
  const badge = document.getElementById("notifyBadge");
  const list = document.getElementById("notifyList");
  const empty = document.getElementById("notifyEmpty");
  if (!badge || !list || !empty) return;

  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${window.API_BASE}/api/data/notifications/`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) throw new Error("notification fetch failed");
    const data = await res.json();
    const items = data.results || [];
    const unreadCount = Number.isFinite(data.unread_count) ? data.unread_count : items.filter((i) => !i.is_read).length;
    renderNotifications(items);

    if (unreadCount > 0) {
      badge.classList.remove("hidden");
      badge.innerText = String(unreadCount);
      empty.classList.add("hidden");
    } else {
      badge.classList.add("hidden");
      empty.classList.toggle("hidden", items.length > 0);
    }
  } catch (e) {
    console.warn("notifications fetch failed", e);
  }
}

function renderNotifications(items) {
  const list = document.getElementById("notifyList");
  const empty = document.getElementById("notifyEmpty");
  const detail = document.getElementById("notifyDetail");
  if (!list) return;

  if (!items.length) {
    list.innerHTML = "";
    if (detail) detail.classList.add("hidden");
    if (empty) empty.classList.remove("hidden");
    return;
  }

  notifyItemsById = new Map(items.map((item) => [String(item.id), item]));
  if (detail) detail.classList.add("hidden");
  if (empty) empty.classList.add("hidden");
  list.classList.remove("hidden");

  list.innerHTML = items
    .map((item) => {
      const title = (item.content || "").trim() || "메모";
      const dateLabel = item.date || "-";

      return `
        <div class="notify-item ${item.is_read ? "is-read" : ""}" data-id="${item.id}" data-date="${dateLabel}">
          <div class="notify-summary">${dateLabel} · ${title}</div>
        </div>
      `;
    })
    .join("");

  list.querySelectorAll(".notify-item").forEach((itemEl) => {
    itemEl.addEventListener("click", () => {
      const memoId = itemEl.dataset.id;
      if (!memoId) return;
      openNotificationDetail(memoId);
    });
  });
}

async function markNotificationRead(memoId) {
  try {
    const headers = await buildAuthHeaders();
    await fetch(`${window.API_BASE}/api/data/calendar-memos/${memoId}/`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ is_read: true }),
    });
  } catch (e) {
    console.warn("mark notification read failed", e);
  }
}

async function deleteNotificationMemo(memoId) {
  try {
    const headers = await buildAuthHeaders();
    await fetch(`${window.API_BASE}/api/data/calendar-memos/${memoId}/`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ is_read: true }),
    });
  } catch (e) {
    console.warn("delete notification memo failed", e);
  }
}

function openMemoFromNotification({ id, date }) {
  try {
    sessionStorage.setItem("openMemoId", String(id));
    if (date) {
      sessionStorage.setItem("openMemoDate", date);
    }
  } catch (e) {
    console.warn("sessionStorage unavailable", e);
  }

  if (window.nav?.go) {
    window.nav.go("calendar_dashboard");
  } else {
    window.location.href = "calendar_dashboard.html";
  }
}

function openNotificationDetail(memoId) {
  const detail = document.getElementById("notifyDetail");
  const list = document.getElementById("notifyList");
  const empty = document.getElementById("notifyEmpty");
  const titleEl = document.getElementById("notifyDetailTitle");
  const metaEl = document.getElementById("notifyDetailMeta");
  const contentEl = document.getElementById("notifyDetailContent");
  const deleteBtn = document.getElementById("notifyDetailDelete");
  const openBtn = document.getElementById("notifyDetailOpen");

  if (!detail || !list || !metaEl || !contentEl || !deleteBtn || !openBtn) return;

  const item = notifyItemsById.get(String(memoId));
  if (!item) return;

  const clinic = item.clinic_name || "전체";
  const dateLabel = item.date || "-";
  const remindAt = item.remind_at ? new Date(item.remind_at) : null;
  const timeLabel = remindAt && !Number.isNaN(remindAt.valueOf())
    ? remindAt.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
    : "-";
  const platform = item.platform_label || item.platform || "";
  const account = item.account || "";
  const password = item.account_password || "";
  const author = item.user_name || "-";

  if (titleEl) titleEl.innerText = `${dateLabel} 메모`;
  metaEl.innerHTML = `
    <div class="meta-row"><span>병원</span><span>${clinic}</span></div>
    <div class="meta-row"><span>알림</span><span>${dateLabel} ${timeLabel}</span></div>
    ${platform ? `<div class="meta-row"><span>플랫폼</span><span>${platform}</span></div>` : ""}
    ${account ? `<div class="meta-row"><span>ID</span><span>${account}</span></div>` : ""}
    ${password ? `<div class="meta-row"><span>PW</span><span>${password}</span></div>` : ""}
    <div class="meta-row"><span>담당자</span><span>${author}</span></div>
  `;
  contentEl.innerText = item.content || "";

  if (!item.is_read) {
    markNotificationRead(memoId);
  }

  deleteBtn.onclick = async (e) => {
    e.stopPropagation();
    await deleteNotificationMemo(memoId);
    refreshNotifications();
  };

  openBtn.onclick = (e) => {
    e.stopPropagation();
    openMemoFromNotification({ id: memoId, date: item.date });
  };

  list.classList.add("hidden");
  if (empty) empty.classList.add("hidden");
  detail.classList.remove("hidden");
}

function startLiveClock() {
  const timeEl = document.getElementById("liveClock");
  const dateEl = document.getElementById("liveDate");

  if (!timeEl || !dateEl) return;

  function update() {
    const now = new Date();

    // 시간
    timeEl.innerText = now.toLocaleTimeString("ko-KR", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

    // 날짜
    dateEl.innerText = now.toLocaleDateString("ko-KR", {
      month: "long",
      day: "numeric",
      weekday: "short",
    });
  }

  update();
  setInterval(update, 1000);
}

// ================================
// 전역 바인딩 (🔥 중요)
// ================================
window.loadHeader = loadHeader;
window.toggleProfile = toggleProfile;
window.closeProfilePopup = closeProfilePopup;
window.logout = logout;
window.openProfileInfo = openProfileInfo;
window.closeProfileInfo = closeProfileInfo;
window.quitApp = () => window.api?.quitApp?.();
