console.log("calendar_dashboard.js loaded");

window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";

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

window.POSITION_LABEL = window.POSITION_LABEL || {
  admin: "계정",
  manager: "매니저",
  leader: "팀장",
  ceo: "대표이사",
};

let calendarItems = [];
let calendarMemos = [];
let calendarSelectedDate = "";
const assigneeCache = new Map();

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

function getMonthValue() {
  const input = document.getElementById("calendarMonth");
  if (!input) return "";
  if (!input.value) {
    const d = new Date();
    input.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }
  return input.value;
}

function getPostDate(post) {
  const raw = post.published_at || post.updated_at || "";
  if (!raw) return "";
  return raw.slice(0, 10);
}

function getSubtypeByPhotos(post) {
  const hasPhotos = Array.isArray(post?.photos) && post.photos.length > 0;
  return hasPhotos ? "photo" : "text";
}

function getDoctorLabel(post) {
  if (!post) return "";
  if (post.doctor_name) return post.doctor_name;
  if (post.doctorName) return post.doctorName;
  if (post.doctor_label) return post.doctor_label;
  if (post.doctor && typeof post.doctor === "object") {
    return post.doctor.name || post.doctor.label || post.doctor.doctor_name || "";
  }
  if (typeof post.doctor === "string") return post.doctor;
  return "";
}

function getAssigneeLabel(post) {
  if (!post) return "";
  if (post.assignee_name) return post.assignee_name;
  if (post.assignee && typeof post.assignee === "object") {
    return post.assignee.name || post.assignee.label || "";
  }
  if (typeof post.assignee === "string") {
    const trimmed = post.assignee.trim();
    if (!trimmed) return "";
    return Number.isNaN(Number(trimmed)) ? trimmed : "";
  }
  return "";
}

async function fetchClinics() {
  try {
    if (window.api?.getClinics) {
      return await window.api.getClinics();
    }
  } catch (e) {
    console.warn("getClinics failed", e);
  }

  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${window.API_BASE}/api/data/clinics/`, {
      credentials: "include",
      headers,
    });
    if (res.ok) {
      const data = await res.json();
      return data.results || [];
    }
  } catch (e) {
    console.warn("fetch clinics fallback failed", e);
  }

  if (Array.isArray(window.clinics)) {
    return window.clinics.map((c) => ({ id: c.id, name: c.name }));
  }

  return [];
}

async function fetchAssignees(clinicId) {
  if (assigneeCache.has(clinicId)) {
    return assigneeCache.get(clinicId);
  }
  const headers = await buildAuthHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/clinics/${clinicId}/assignees/`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) return [];
  const data = await res.json();
  assigneeCache.set(clinicId, data);
  return data;
}

async function fetchClinicPosts(clinicId, month, type) {
  const params = new URLSearchParams({
    type,
    platform: "all",
    month,
  });
  const url = `${window.API_BASE}/api/data/clinics/${clinicId}/posts/?${params}`;
  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

async function fetchCalendarMemos(month) {
  const params = new URLSearchParams({ month });
  const headers = await buildAuthHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/calendar-memos/?${params}`, {
    credentials: "include",
    headers,
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function formatMemoTime(remindAt) {
  if (!remindAt) return "";
  const parsed = new Date(remindAt);
  if (Number.isNaN(parsed.valueOf())) return "";
  return parsed.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

function getSelectedClinicId() {
  const clinicSelect = document.getElementById("calendarClinicSelect");
  return clinicSelect?.value || "all";
}

function filterMemosByClinic(memos, clinicId) {
  if (clinicId === "all") return memos;
  return memos.filter((memo) => memo.clinic_id === Number(clinicId) || memo.clinic_id === null);
}

function getPlatformLabel(platformKey) {
  if (!platformKey) return "";
  const match = PLATFORM_PILLS.find((p) => p.key === platformKey);
  return match ? match.label : platformKey;
}

async function loadCalendar({ keepPanelOpen = false } = {}) {
  const clinicSelect = document.getElementById("calendarClinicSelect");
  const month = getMonthValue();
  if (!clinicSelect || !month) return;
  const detailPanel = document.getElementById("calendarDetailPanel");
  if (detailPanel && !keepPanelOpen) detailPanel.classList.remove("open");
  const memoOnly = document.getElementById("calendarMemoToggle")?.classList.contains("active");
  updateMemoMode(memoOnly);

  const clinicId = clinicSelect.value;
  const clinics = clinicSelect.dataset.clinics
    ? JSON.parse(clinicSelect.dataset.clinics)
    : [];

  const targetClinics = clinicId === "all"
    ? clinics
    : clinics.filter((c) => String(c.id) === clinicId);

  const items = [];

  await Promise.all(targetClinics.map(async (clinic) => {
    const [opinions, reviews] = await Promise.all([
      fetchClinicPosts(clinic.id, month, "opinion"),
      fetchClinicPosts(clinic.id, month, "review"),
    ]);

    [...opinions, ...reviews].forEach((post) => {
      const normalizedSubtype = post.review_subtype || getSubtypeByPhotos(post);
      const subtype = normalizedSubtype === "photo" ? "사진" : normalizedSubtype === "text" ? "텍스트" : "";
      const typeLabel = post.type === "review" ? "후기" : "여론";
      const titlePrefix = `[${typeLabel}]`;
      items.push({
        date: getPostDate(post),
        title: post.title,
        title_display: `${titlePrefix} ${post.title}`,
        url: post.url,
        platform: post.platform,
        platform_label: post.platform_label,
        status: post.status,
        account: post.account || post.assignee_name || "",
        account_password: post.account_password || "",
        memo: post.memo || "",
        views: post.views ?? 0,
        comments: post.comments ?? 0,
        message_count: post.message_count ?? 0,
        post_id: post.id,
        type: post.type,
        review_subtype: normalizedSubtype,
        doctor_name: getDoctorLabel(post),
        assignee: getAssigneeLabel(post),
        photos: (post.photos || []).map((p) => p.url),
        clinic: clinic.name,
        clinicId: clinic.id,
      });
    });
  }));

  const memos = await fetchCalendarMemos(month);
  const filteredMemos = filterMemosByClinic(memos, clinicId);
  calendarMemos = filteredMemos;

  const memoItems = filteredMemos.map((memo) => ({
    kind: "memo",
    date: memo.date,
    memo: memo.content,
    remind_at: formatMemoTime(memo.remind_at),
    clinic: memo.clinic_name || "전체",
    clinicId: memo.clinic_id || null,
  }));

  const filteredItems = memoOnly ? memoItems : items;
  calendarItems = filteredItems;
  renderScheduleCalendar({
    calendarId: "calendarBoard",
    listId: "calendarDetailList",
    items: filteredItems,
    yearMonth: month,
    emptyMessage: memoOnly ? "등록된 메모가 없습니다." : "선택된 기간에 작업이 없습니다.",
    allowEmptyClick: memoOnly,
    onDateSelect: memoOnly
      ? (date) => {
          setMemoDate(date);
        }
      : null,
  });

  if (memoOnly && calendarSelectedDate) {
    renderMemoList(calendarSelectedDate);
  }
}

async function initCalendarDashboard() {
  const clinicSelect = document.getElementById("calendarClinicSelect");
  if (!clinicSelect) return;

  const clinics = await fetchClinics();
  clinicSelect.dataset.clinics = JSON.stringify(clinics);
  clinicSelect.innerHTML = clinics.length
    ? `
      <option value="all">전체 병원</option>
      ${clinics.map((c) => `<option value="${c.id}">${c.name}</option>`).join("")}
    `
    : `<option value="">병원 목록 없음</option>`;

  const memoClinicSelect = document.getElementById("calendarMemoClinicSelect");
  if (memoClinicSelect) {
    memoClinicSelect.innerHTML = clinics.length
      ? `
        <option value="all">전체 병원</option>
        ${clinics.map((c) => `<option value="${c.id}">${c.name}</option>`).join("")}
      `
      : `<option value="all">전체 병원</option>`;
    memoClinicSelect.value = clinicSelect.value || "all";
  }

  const memoPlatform = document.getElementById("calendarMemoPlatform");
  if (memoPlatform) {
    memoPlatform.innerHTML = `
      <option value="">플랫폼 선택</option>
      ${PLATFORM_PILLS.map((p) => `<option value="${p.key}">${p.label}</option>`).join("")}
    `;
  }

  clinicSelect.onchange = () => {
    if (memoClinicSelect) {
      memoClinicSelect.value = clinicSelect.value || "all";
    }
    loadCalendar();
  };
  const monthInput = document.getElementById("calendarMonth");
  if (monthInput) {
    monthInput.addEventListener("change", loadCalendar);
  }
  const workToggle = document.getElementById("calendarWorkToggle");
  const memoToggle = document.getElementById("calendarMemoToggle");
  if (workToggle && memoToggle) {
    workToggle.addEventListener("click", () => {
      workToggle.classList.add("active");
      memoToggle.classList.remove("active");
      updateCalendarBoardTitle(false);
      updateMemoMode(false);
      loadCalendar();
    });
    memoToggle.addEventListener("click", () => {
      memoToggle.classList.add("active");
      workToggle.classList.remove("active");
      updateCalendarBoardTitle(true);
      updateMemoMode(true);
      loadCalendar();
    });
  }

  document.getElementById("calendarMemoSave")?.addEventListener("click", saveCalendarMemo);
  document.getElementById("calendarMemoOpen")?.addEventListener("click", openMemoModal);
  initMemoModal();
  setMemoAuthor();

  const detailPanel = document.getElementById("calendarDetailPanel");
  const detailClose = document.getElementById("calendarDetailClose");
  if (detailPanel && detailClose) {
    detailClose.addEventListener("click", () => {
      detailPanel.classList.remove("open");
    });
  }
  document.addEventListener("keydown", (e) => {
    const previewOpen = document.getElementById("photoPreviewModal")?.classList.contains("hidden") === false;
    if (e.key === "Escape" && detailPanel?.classList.contains("open") && !previewOpen) {
      detailPanel.classList.remove("open");
    }
  });
  initPanelResize("calendarDetailPanel");

  const editModal = document.getElementById("calendarEditModal");
  if (editModal) {
    editModal.addEventListener("click", (e) => {
      if (e.target?.dataset?.close) {
        editModal.classList.add("hidden");
      }
    });
  }
  document.getElementById("calendarEditSave")?.addEventListener("click", saveCalendarEdit);
  document.getElementById("calendarEditDelete")?.addEventListener("click", deleteCalendarEdit);

  window.openPostEditor = ({ postId, clinicId }) => {
    const post = calendarItems.find((item) => String(item.post_id) === String(postId));
    if (!post) return;
    openCalendarEditModal(post, clinicId);
  };

  const pendingMemoDate = (() => {
    try {
      return sessionStorage.getItem("openMemoDate") || "";
    } catch (e) {
      return "";
    }
  })();
  const hasPendingMemo = Boolean(pendingMemoDate || (() => {
    try {
      return sessionStorage.getItem("openMemoId");
    } catch (e) {
      return "";
    }
  })());

  if (hasPendingMemo && memoToggle && workToggle) {
    memoToggle.classList.add("active");
    workToggle.classList.remove("active");
  }

  updateCalendarBoardTitle(memoToggle?.classList.contains("active"));
  updateMemoMode(memoToggle?.classList.contains("active"));
  await loadCalendar();

  if (hasPendingMemo) {
    if (pendingMemoDate) {
      setMemoDate(pendingMemoDate);
    }
    document.getElementById("calendarDetailPanel")?.classList.add("open");
    try {
      sessionStorage.removeItem("openMemoDate");
      sessionStorage.removeItem("openMemoId");
    } catch (e) {
      // ignore
    }
  }
}

document.addEventListener("DOMContentLoaded", initCalendarDashboard);

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

function updateCalendarBoardTitle(isMemoOnly) {
  const titleEl = document.getElementById("calendarBoardTitle");
  if (!titleEl) return;
  titleEl.innerText = isMemoOnly ? "메모 캘린더" : "작업 캘린더";
}

function updateMemoMode(isMemoOnly) {
  const panel = document.getElementById("calendarMemoPanel");
  const list = document.getElementById("calendarDetailList");
  const titleEl = document.getElementById("calendarDetailTitle");
  const subEl = document.getElementById("calendarDetailSub");
  if (!panel || !list) return;

  panel.classList.toggle("hidden", !isMemoOnly);
  list.classList.toggle("hidden", isMemoOnly);

  if (titleEl) titleEl.innerText = isMemoOnly ? "메모 상세" : "선택일 상세";
  if (subEl) {
    subEl.innerText = isMemoOnly
      ? "선택한 날짜에 메모를 추가하거나 확인합니다."
      : "선택한 날짜의 작업을 확인합니다.";
  }
}

function initMemoModal() {
  const modal = document.getElementById("calendarMemoModal");
  if (!modal) return;
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) {
      modal.classList.add("hidden");
    }
  });
}

function openMemoModal() {
  const memoOnly = document.getElementById("calendarMemoToggle")?.classList.contains("active");
  const memoPanelVisible = !document.getElementById("calendarMemoPanel")?.classList.contains("hidden");
  if (!memoOnly && !memoPanelVisible) {
    alert("메모 캘린더로 전환하고 작성해 주세요.");
    return;
  }
  if (!calendarSelectedDate) {
    alert("먼저 날짜를 선택하세요.");
    return;
  }
  const modal = document.getElementById("calendarMemoModal");
  if (!modal) return;
  modal.classList.remove("hidden");
}

function setMemoDate(date) {
  calendarSelectedDate = date || "";
  const label = document.getElementById("calendarMemoDate");
  if (label) label.innerText = calendarSelectedDate || "-";
  renderMemoList(calendarSelectedDate);
}

function renderMemoList(date) {
  const list = document.getElementById("calendarMemoList");
  if (!list) return;

  if (!date) {
    list.innerHTML = `<div class="muted">날짜를 선택하세요.</div>`;
    return;
  }

  const clinicId = getSelectedClinicId();
  const memos = filterMemosByClinic(calendarMemos, clinicId)
    .filter((memo) => memo.date === date);

  if (!memos.length) {
    list.innerHTML = `<div class="muted">등록된 메모가 없습니다.</div>`;
    return;
  }

  list.innerHTML = memos
    .map((memo) => {
      const timeLabel = formatMemoTime(memo.remind_at);
      const clinicLabel = memo.clinic_name || "전체";
      const platformLabel = getPlatformLabel(memo.platform);
      const userLabel = memo.user_name || "-";
      const accountLabel = memo.account ? `ID ${memo.account}` : "";
      const passwordLabel = memo.account_password ? `PW ${memo.account_password}` : "";
      const accountLine = [accountLabel, passwordLabel].filter(Boolean).join(" · ");
      return `
        <div class="memo-item" data-id="${memo.id}">
          <div class="memo-meta">
            <span>${clinicLabel}${platformLabel ? ` · ${platformLabel}` : ""}</span>
            <span>${timeLabel || "-"}</span>
          </div>
          ${accountLine ? `<div class="memo-meta"><span>${accountLine}</span><span></span></div>` : ""}
          <div class="memo-meta">
            <span>담당자 ${userLabel}</span>
            <span></span>
          </div>
          <div class="memo-content">${memo.content}</div>
          <div class="memo-actions">
            <button class="memo-delete" data-id="${memo.id}">삭제</button>
          </div>
        </div>
      `;
    })
    .join("");

  list.querySelectorAll(".memo-delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const memoId = btn.dataset.id;
      if (!memoId) return;
      await deleteCalendarMemo(memoId);
    });
  });
}

async function saveCalendarMemo() {
  const memoOnly = document.getElementById("calendarMemoToggle")?.classList.contains("active");
  const memoPanelVisible = !document.getElementById("calendarMemoPanel")?.classList.contains("hidden");
  if (!memoOnly && !memoPanelVisible) {
    alert("메모 캘린더로 전환하고 작성해 주세요.");
    return;
  }
  const date = calendarSelectedDate;
  if (!date) {
    alert("먼저 날짜를 선택하세요.");
    return;
  }

  const contentEl = document.getElementById("calendarMemoContent");
  const remindEl = document.getElementById("calendarMemoRemind");
  const memoClinicSelect = document.getElementById("calendarMemoClinicSelect");
  const memoPlatform = document.getElementById("calendarMemoPlatform");
  const memoAccount = document.getElementById("calendarMemoAccount");
  const memoPassword = document.getElementById("calendarMemoPassword");
  const content = (contentEl?.value || "").trim();
  if (!content) {
    alert("메모 내용을 입력하세요.");
    return;
  }

  const clinicId = memoClinicSelect?.value || getSelectedClinicId();
  const remindAt = remindEl?.value ? new Date(remindEl.value) : null;
  const platform = memoPlatform?.value || "";
  const account = (memoAccount?.value || "").trim();
  const accountPassword = (memoPassword?.value || "").trim();
  const payload = {
    date,
    content,
  };
  if (clinicId !== "all") {
    payload.clinic_id = Number(clinicId);
  }
  if (platform) {
    payload.platform = platform;
  }
  if (account) {
    payload.account = account;
  }
  if (accountPassword) {
    payload.account_password = accountPassword;
  }
  if (remindAt && !Number.isNaN(remindAt.valueOf())) {
    payload.remind_at = remindAt.toISOString();
  }

  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${window.API_BASE}/api/data/calendar-memos/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      alert("메모 저장 실패");
      return;
    }
    if (contentEl) contentEl.value = "";
    if (remindEl) remindEl.value = "";
    if (memoPlatform) memoPlatform.value = "";
    if (memoAccount) memoAccount.value = "";
    if (memoPassword) memoPassword.value = "";
    document.getElementById("calendarMemoModal")?.classList.add("hidden");
    await loadCalendar({ keepPanelOpen: true });
    setMemoDate(date);
  } catch (e) {
    console.error("memo save failed", e);
    alert("메모 저장 실패");
  }
}

async function deleteCalendarMemo(memoId) {
  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${window.API_BASE}/api/data/calendar-memos/${memoId}/`, {
      method: "DELETE",
      credentials: "include",
      headers,
    });
    if (!res.ok) {
      alert("메모 삭제 실패");
      return;
    }
    await loadCalendar({ keepPanelOpen: true });
    setMemoDate(calendarSelectedDate);
  } catch (e) {
    console.error("memo delete failed", e);
    alert("메모 삭제 실패");
  }
}

async function setMemoAuthor() {
  const label = document.getElementById("calendarMemoAuthor");
  if (!label) return;
  try {
    const me = await window.api?.getMe?.();
    const name = me?.name || me?.username || "-";
    const position = me?.position || "";
    const positionLabel = window.POSITION_LABEL?.[position] || position;
    label.innerText = positionLabel ? `${name} ${positionLabel}` : name;
  } catch (e) {
    label.innerText = "-";
  }
}

function ensurePlatformOptions(selectEl) {
  if (!selectEl) return;
  if (selectEl.options.length) return;
  selectEl.innerHTML = PLATFORM_PILLS.map((p) => `<option value="${p.key}">${p.label}</option>`).join("");
}

function toggleSubtypeVisibility(typeValue) {
  const subtypeField = document.getElementById("calendarEditSubtype")?.closest(".ai-field");
  if (!subtypeField) return;
  subtypeField.style.display = typeValue === "review" ? "flex" : "none";
}

async function openCalendarEditModal(post, clinicId) {
  const modal = document.getElementById("calendarEditModal");
  if (!modal) return;

  const typeEl = document.getElementById("calendarEditType");
  const subtypeEl = document.getElementById("calendarEditSubtype");
  const platformEl = document.getElementById("calendarEditPlatform");
  const titleEl = document.getElementById("calendarEditTitle");
  const urlEl = document.getElementById("calendarEditUrl");
  const viewsEl = document.getElementById("calendarEditViews");
  const commentsEl = document.getElementById("calendarEditComments");
  const messagesEl = document.getElementById("calendarEditMessages");
  const assigneeEl = document.getElementById("calendarEditAssignee");
  const dateEl = document.getElementById("calendarEditDate");

  ensurePlatformOptions(platformEl);

  if (typeEl) typeEl.value = post.type || "opinion";
  if (subtypeEl) subtypeEl.value = post.review_subtype || "text";
  if (platformEl) platformEl.value = post.platform || "";
  if (titleEl) titleEl.value = post.title || "";
  if (urlEl) urlEl.value = post.url || "";
  if (viewsEl) viewsEl.value = post.views ?? 0;
  if (commentsEl) commentsEl.value = post.comments ?? 0;
  if (messagesEl) messagesEl.value = post.message_count ?? 0;
  if (dateEl) dateEl.value = post.date || "";

  if (assigneeEl) {
    const assignees = await fetchAssignees(clinicId);
    assigneeEl.innerHTML = `
      <option value="">미지정</option>
      ${assignees.map((a) => `<option value="${a.id}">${a.name}</option>`).join("")}
    `;
    assigneeEl.value = post.assignee || "";
  }

  if (typeEl) {
    toggleSubtypeVisibility(typeEl.value);
    typeEl.onchange = () => toggleSubtypeVisibility(typeEl.value);
  }

  modal.dataset.postId = post.post_id;
  modal.dataset.clinicId = clinicId;
  modal.classList.remove("hidden");
}

async function saveCalendarEdit() {
  const modal = document.getElementById("calendarEditModal");
  if (!modal) return;
  const postId = modal.dataset.postId;
  const clinicId = modal.dataset.clinicId;
  if (!postId || !clinicId) return;

  const payload = {
    type: document.getElementById("calendarEditType")?.value || "opinion",
    review_subtype: document.getElementById("calendarEditSubtype")?.value || null,
    platform: document.getElementById("calendarEditPlatform")?.value || "",
    title: document.getElementById("calendarEditTitle")?.value || "",
    url: document.getElementById("calendarEditUrl")?.value || "",
    views: Number(document.getElementById("calendarEditViews")?.value || 0),
    comments: Number(document.getElementById("calendarEditComments")?.value || 0),
    message_count: Number(document.getElementById("calendarEditMessages")?.value || 0),
    assignee: document.getElementById("calendarEditAssignee")?.value || "",
    published_at: document.getElementById("calendarEditDate")?.value || "",
  };

  if (payload.type !== "review") {
    payload.review_subtype = null;
  }

  const headers = await buildAuthHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/clinics/${clinicId}/posts/${postId}/`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    alert("저장 실패");
    return;
  }

  modal.classList.add("hidden");
  loadCalendar();
}

async function deleteCalendarEdit() {
  const modal = document.getElementById("calendarEditModal");
  if (!modal) return;
  const postId = modal.dataset.postId;
  const clinicId = modal.dataset.clinicId;
  if (!postId || !clinicId) return;
  if (!confirm("게시글을 삭제할까요?")) return;

  const headers = await buildAuthHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/clinics/${clinicId}/posts/${postId}/`, {
    method: "DELETE",
    credentials: "include",
    headers,
  });

  if (!res.ok) {
    alert("삭제 실패");
    return;
  }

  modal.classList.add("hidden");
  loadCalendar();
}

