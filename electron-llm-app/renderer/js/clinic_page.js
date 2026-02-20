console.log("clinic_page.js loaded");

const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";
const LAST_CLINIC_KEY = "lastClinicId";

// ================================
// 상태
// ================================
let currentClinicId = null;
let currentClinicName = "";
let currentPostMonth = getThisMonth();   // YYYY-MM
let currentCalendarMonth = getThisMonth();   // YYYY-MM
let currentCommentMonth = getThisMonth();   // YYYY-MM
let currentType = "opinion";         // opinion | review
let currentPlatform = "all";         // all | naver | ...
let currentQuery = "";
let currentSort = "latest";          // latest | oldest
let calendarMemoOnly = false;
let calendarMemos = [];
let calendarSelectedDate = "";
let postsCache = new Map();
let editingAll = false;
let assigneeNameMap = new Map();
let commentBundleItemsByUrl = new Map();
let messageLogItemsByUrl = new Map();
let clinicPageInitialized = false;
let currentClinicNotices = [];
let editingNoticeId = null;
let openNoticeId = null;

// ================================
// 플랫폼 정의
// ================================
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

const PLATFORM_URL_MATCHERS = [
  { key: "naver", label: "네이버", match: ["naver.com", "blog.naver.com", "m.blog.naver.com", "cafe.naver.com"] },
  { key: "gangnam", label: "강남언니", match: ["abr.ge", "gangnamunni.com", "gangnamunni", "gangnam"] },
  { key: "gn_jp", label: "JP강남언니", match: ["gnun.link", "gangnamunni.jp", "gn.jp", "gangnam-jp"] },
  { key: "babytok", label: "바비톡", match: ["web.babitalk.com", "babitalk.com", "babytok.com", "babytok"] },
  { key: "todaktok", label: "토닥톡", match: ["todaktok.com", "todaktok"] },
  { key: "yeoshin", label: "여신티켓", match: ["yeoshin.co.kr", "yeoshin.com", "yeoshin", "yeoshin-ticket"] },
  { key: "seongyesa", label: "성예사", match: ["sungyesa.com", "seongyesa.com", "seongyesa"] },
  { key: "dadamo", label: "대다모", match: ["daedamo.com", "dadamo.com", "dadamo"] },
];

// ================================
// 인증 헤더
// ================================
async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

// ================================
// 유틸
// ================================
function getClinicIdFromQuery() {
  return new URLSearchParams(window.location.search).get("clinic_id");
}

function normalizeClinicId(raw) {
  const value = String(raw || "").trim();
  if (!value || value === "null" || value === "undefined") return null;
  return value;
}

function rememberClinicId(clinicId) {
  if (!clinicId) return;
  localStorage.setItem(LAST_CLINIC_KEY, String(clinicId));
}

function getRememberedClinicId() {
  return normalizeClinicId(localStorage.getItem(LAST_CLINIC_KEY));
}

function getThisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthLabel(value) {
  if (!value) return "-";
  const [y, m] = value.split("-").map(Number);
  if (!y || !m) return value;
  return `${y}년 ${m}월`;
}

function formatHoursText(value) {
  const raw = String(value || "").replace(/\r\n?/g, "\n").trim();
  if (!raw) return "-";
  if (raw.includes("\n")) return raw;
  return raw.replace(/\s*,\s*/g, "\n");
}

function fmtDateTime(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", { hour12: false });
}

function fmtDateTimeMinute(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", {
    hour12: false,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDateOnly(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleDateString("ko-KR");
}

function formatMemoTime(remindAt) {
  if (!remindAt) return "";
  const parsed = new Date(remindAt);
  if (Number.isNaN(parsed.valueOf())) return "";
  return parsed.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

function normalizeUrlKey(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    const host = String(parsed.hostname || "")
      .toLowerCase()
      .replace(/^www\./, "")
      .replace(/^m\./, "");
    const pathname = String(parsed.pathname || "").replace(/\/+$/, "");
    return `${host}${pathname}`;
  } catch (_) {
    return raw
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/^www\./, "")
      .replace(/^m\./, "")
      .replace(/\?.*$/, "")
      .replace(/\/+$/, "");
  }
}

function getCountUrlKey(value) {
  return normalizeUrlKey(value);
}

function detectPlatformFromUrl(url) {
  const raw = String(url || "").toLowerCase();
  if (!raw) return null;
  const hit = PLATFORM_URL_MATCHERS.find((c) => c.match.some((m) => raw.includes(m)));
  return hit ? { key: hit.key, label: hit.label } : null;
}

function detectCafeFromUrl(url) {
  const raw = String(url || "").trim();
  if (!raw) return "-";
  const CAFE_ID_NAME_MAP = {
    imsanbu: "맘스홀릭",
    cosmania: "파우더룸",
    parisienlook: "시트먼트",
    geahwa73: "안양군의왕과천맘",
    feko: "여우야",
    fox5282: "A+ 여우야",
    juliett00: "성형위키",
    luxury009: "가야사",
    knife67: "재잘재잘",
    suddes: "여생남정",
    newsmaker: "지살사",
  };

  const matchedCafeId = Object.keys(CAFE_ID_NAME_MAP).find((id) => raw.toLowerCase().includes(id));
  if (matchedCafeId) {
    return CAFE_ID_NAME_MAP[matchedCafeId];
  }

  try {
    const parsed = new URL(raw);
    let host = String(parsed.hostname || "").toLowerCase();
    host = host.replace(/^www\./, "").replace(/^m\./, "");
    if (!host) return "-";
    if (host.includes("cafe.naver.com")) {
      const segments = String(parsed.pathname || "")
        .split("/")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);
      const cafeId = segments[0] || "";
      if (cafeId && CAFE_ID_NAME_MAP[cafeId]) {
        return CAFE_ID_NAME_MAP[cafeId];
      }
      if (cafeId) return cafeId;
      return "네이버 카페";
    }
    if (host.includes("blog.naver.com")) return "네이버 블로그";
    return host;
  } catch (_) {
    return "-";
  }
}

function inferTypeLabelFromPlatformKey(platformKey) {
  const reviewPlatforms = new Set(["gangnam", "babytok", "todaktok", "yeoshin"]);
  return reviewPlatforms.has(String(platformKey || "").toLowerCase()) ? "후기" : "여론";
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function isNumericString(value) {
  if (value === null || value === undefined) return false;
  const trimmed = String(value).trim();
  if (!trimmed) return false;
  return !Number.isNaN(Number(trimmed));
}

function getAssigneeDisplay(post) {
  if (!post) return "-";
  const nameCandidate = post.assignee_name;
  if (nameCandidate && !isNumericString(nameCandidate)) return nameCandidate;
  if (post.assignee && typeof post.assignee === "object") {
    return post.assignee.name || post.assignee.label || "-";
  }
  const assigneeId = post.assignee ? String(post.assignee) : "";
  const mapped = assigneeId ? assigneeNameMap.get(assigneeId) : "";
  if (mapped) return mapped;
  if (typeof post.assignee === "string" && !isNumericString(post.assignee)) {
    return post.assignee;
  }
  return "-";
}

// ================================
// 초기 로드
// ================================
async function initClinicPage() {
  if (clinicPageInitialized) return;
  clinicPageInitialized = true;

  currentClinicId = normalizeClinicId(getClinicIdFromQuery()) || getRememberedClinicId();
  if (!currentClinicId) {
    window.showAlert?.("clinic_id 없음");
    clinicPageInitialized = false;
    return;
  }
  rememberClinicId(currentClinicId);

  await loadClinicInfo();
  await loadAssignees();

  initSectionToggles();
  initClinicWorkspaceNav();
  initClinicNoticesSection();
  initAiIntakeForm();
  initClinicPostsSection();
  initClinicCalendar();
  initCommentMonthNav();
  initCommentBundleModal();
  initMessageLogModal();
  loadCommentBundleList();
  bindPostsDashboardLink();
}

async function loadAssignees() {
  if (!currentClinicId) return;
  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/assignees/`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) return;
    const data = await res.json();
    assigneeNameMap = new Map((data || []).map((item) => [String(item.id), item.name]));
  } catch (e) {
    console.warn("assignee load failed", e);
  }
}

// ================================
// 병원 정보
// ================================
async function loadClinicInfo() {
  if (!currentClinicId) return;
  const data = await window.api.getClinicDetail(currentClinicId);
  const c = data?.clinic || {};

  const titleEl = document.getElementById("clinicTitle");
  const metaEl = document.getElementById("clinicMeta");

  if (titleEl) {
    titleEl.innerText = c.name || "병원";
  }
  currentClinicName = c.name || "";

  if (metaEl) {
    metaEl.innerText = `${c.location || ""} · ${c.hours || ""}`.trim();
  }
  renderClinicGuideSection(data);
}

function renderClinicGuideSection(data) {
  const clinic = data?.clinic || {};
  const doctors = Array.isArray(data?.doctors) ? data.doctors : [];
  const prices = Array.isArray(data?.price_list) ? data.price_list : [];
  const consultants = Array.isArray(data?.consultants) ? data.consultants : [];

  const clinicNameEl = document.getElementById("clinicName");
  const clinicLocationEl = document.getElementById("clinicLocation");
  const clinicHoursEl = document.getElementById("clinicHours");
  const clinicParkingEl = document.getElementById("clinicParking");
  const clinicProcessEl = document.getElementById("clinicProcess");
  const doctorTabsEl = document.getElementById("doctorTabs");
  const doctorTitleEl = document.getElementById("doctorTitle");
  const priceCountEl = document.getElementById("priceCount");
  const priceTbodyEl = document.getElementById("priceTbody");
  const consultantsEl = document.getElementById("consultants");
  const aftercareEl = document.getElementById("aftercare");
  if (
    !clinicNameEl || !clinicLocationEl || !clinicHoursEl || !clinicParkingEl || !clinicProcessEl ||
    !doctorTabsEl || !doctorTitleEl || !priceCountEl || !priceTbodyEl || !consultantsEl || !aftercareEl
  ) return;

  clinicNameEl.textContent = clinic.name || "-";
  clinicLocationEl.textContent = clinic.location || "-";
  clinicHoursEl.textContent = formatHoursText(clinic.hours);
  clinicParkingEl.textContent = clinic.parking || "-";
  clinicProcessEl.textContent = clinic.process || "-";

  doctorTabsEl.innerHTML = "";
  doctors.forEach((doc) => {
    const key = doc.code || doc.name;
    const tab = document.createElement("div");
    tab.className = "nav-item";
    tab.dataset.key = String(key);
    tab.innerHTML = `<span>${escapeHtml(doc.name || String(key))}</span>`;
    tab.addEventListener("click", () => renderGuidePriceTable(data, String(key)));
    doctorTabsEl.appendChild(tab);
  });

  if (prices.some((row) => !row.doctor_code)) {
    const tab = document.createElement("div");
    tab.className = "nav-item";
    tab.dataset.key = "common";
    tab.innerHTML = "<span>공통 수가</span>";
    tab.addEventListener("click", () => renderGuidePriceTable(data, "common"));
    doctorTabsEl.appendChild(tab);
  }

  const initialKey = doctors.length ? String(doctors[0].code || doctors[0].name) : "common";
  renderGuidePriceTable(data, initialKey);

  if (!consultants.length) {
    consultantsEl.textContent = "-";
  } else {
    consultantsEl.innerHTML = consultants
      .map((item) => {
        if (typeof item === "string") {
          return `<div class="consultant-card"><div class="consultant-name">${escapeHtml(item)}</div></div>`;
        }
        const name = item?.name || item?.label || "";
        const style = item?.style || item?.desc || item?.description || "";
        if (!name) return "";
        return `
          <div class="consultant-card">
            <div class="consultant-name">${escapeHtml(name)}</div>
            ${style ? `<div class="consultant-style">${escapeHtml(style)}</div>` : ""}
          </div>
        `;
      })
      .filter(Boolean)
      .join("") || "-";
  }

  const aftercareItems = Array.isArray(data?.aftercare) ? data.aftercare : [];
  aftercareEl.innerHTML = aftercareItems
    .map((item) => `<div class="aftercare-item">${escapeHtml(item)}</div>`)
    .join("") || "-";
}

function renderGuidePriceTable(data, key) {
  const doctorTabsEl = document.getElementById("doctorTabs");
  const doctorTitleEl = document.getElementById("doctorTitle");
  const priceCountEl = document.getElementById("priceCount");
  const priceTbodyEl = document.getElementById("priceTbody");
  if (!doctorTabsEl || !doctorTitleEl || !priceCountEl || !priceTbodyEl) return;

  const doctors = Array.isArray(data?.doctors) ? data.doctors : [];
  const prices = Array.isArray(data?.price_list) ? data.price_list : [];
  const normalizedKey = String(key || "common");

  doctorTabsEl.querySelectorAll(".nav-item").forEach((node) => {
    node.classList.toggle("active", String(node.dataset.key || "") === normalizedKey);
  });

  const filtered = prices.filter((row) => {
    if (normalizedKey === "common") return !row.doctor_code;
    return String(row.doctor_code || "") === normalizedKey;
  });

  const selectedDoctor = doctors.find((doc) => String(doc.code || doc.name) === normalizedKey);
  doctorTitleEl.textContent = normalizedKey === "common" ? "공통 수가" : (selectedDoctor?.name || normalizedKey);
  priceCountEl.textContent = `${filtered.length}개 항목`;

  if (!filtered.length) {
    priceTbodyEl.innerHTML = `
      <tr>
        <td colspan="4" class="muted">표시할 수가 정보가 없습니다.</td>
      </tr>
    `;
    return;
  }

  const rows = [];
  for (let i = 0; i < filtered.length; i += 2) {
    const left = filtered[i];
    const right = filtered[i + 1];
    rows.push(`
      <tr>
        <td class="procedure">${escapeHtml(left?.procedure || "-")}</td>
        <td class="price">${escapeHtml(left?.price_display || "상담 필요")}</td>
        <td class="procedure">${escapeHtml(right?.procedure || "-")}</td>
        <td class="price">${escapeHtml(right?.price_display || (right ? "상담 필요" : "-"))}</td>
      </tr>
    `);
  }
  priceTbodyEl.innerHTML = rows.join("");
}

function initSectionToggles() {
  document.querySelectorAll(".section-toggle").forEach((btn) => {
    const targetId = btn.dataset.target;
    const target = targetId ? document.getElementById(targetId) : null;
    if (target) target.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
  });
}

function initClinicWorkspaceNav() {
  const navButtons = document.querySelectorAll("#clinicSectionNav .clinic-section-nav-btn");
  const sections = document.querySelectorAll(".result-left .section-block[data-section-key]");
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

// ================================
// 병원 공지사항
// ================================
function initClinicNoticesSection() {
  const openBtn = document.getElementById("clinicNoticeOpenBtn");
  const saveBtn = document.getElementById("clinicNoticeSaveBtn");
  const modalCloseBtn = document.getElementById("clinicNoticeModalClose");
  const modalCancelBtn = document.getElementById("clinicNoticeModalCancel");
  const modalEl = document.getElementById("clinicNoticeModal");
  const listEl = document.getElementById("clinicNoticeList");
  if (!openBtn || !saveBtn || !modalCloseBtn || !modalCancelBtn || !modalEl || !listEl) return;

  openBtn.addEventListener("click", () => openClinicNoticeModal());
  saveBtn.addEventListener("click", () => saveClinicNotice());
  modalCloseBtn.addEventListener("click", () => closeClinicNoticeModal());
  modalCancelBtn.addEventListener("click", () => closeClinicNoticeModal());
  modalEl.addEventListener("click", (event) => {
    if (event.target?.matches?.(".modal-backdrop[data-close='true']")) {
      closeClinicNoticeModal();
    }
  });

  listEl.addEventListener("click", async (event) => {
    const toggleBtn = event.target.closest("[data-notice-toggle]");
    const editBtn = event.target.closest("[data-notice-edit]");
    const deleteBtn = event.target.closest("[data-notice-delete]");
    if (toggleBtn) {
      const id = Number(toggleBtn.dataset.noticeToggle || 0);
      if (!id) return;
      const willOpen = Number(openNoticeId) !== id;
      openNoticeId = willOpen ? id : null;
      if (willOpen) await markClinicNoticeRead(id);
      renderClinicNoticeList();
      return;
    }
    if (editBtn) {
      const id = Number(editBtn.dataset.noticeEdit || 0);
      if (!id) return;
      const found = currentClinicNotices.find((row) => Number(row.id) === id);
      if (!found) return;
      openClinicNoticeModal(found);
      return;
    }
    if (deleteBtn) {
      const id = Number(deleteBtn.dataset.noticeDelete || 0);
      if (!id) return;
      const ok = typeof window.appConfirm === "function"
        ? await window.appConfirm("이 공지사항을 삭제할까요?")
        : window.confirm("이 공지사항을 삭제할까요?");
      if (!ok) return;
      await deleteClinicNotice(id);
    }
  });

  loadClinicNotices();
}

function getClinicNoticeFormValues() {
  const titleEl = document.getElementById("clinicNoticeTitle");
  const contentEl = document.getElementById("clinicNoticeContent");
  const pinnedEl = document.getElementById("clinicNoticePinned");
  return {
    title: String(titleEl?.value || "").trim(),
    content: String(contentEl?.value || "").trim(),
    is_pinned: Boolean(pinnedEl?.checked),
  };
}

function setClinicNoticeStatus(text, isError = false) {
  const headerStatusEl = document.getElementById("clinicNoticeStatus");
  const modalStatusEl = document.getElementById("clinicNoticeModalStatus");
  [headerStatusEl, modalStatusEl].forEach((statusEl) => {
    if (!statusEl) return;
    statusEl.textContent = text || "";
    statusEl.style.color = isError ? "#b91c1c" : "";
  });
}

function openClinicNoticeModal(notice = null) {
  const titleEl = document.getElementById("clinicNoticeTitle");
  const contentEl = document.getElementById("clinicNoticeContent");
  const pinnedEl = document.getElementById("clinicNoticePinned");
  const modalTitleEl = document.getElementById("clinicNoticeModalTitle");
  const modalEl = document.getElementById("clinicNoticeModal");

  editingNoticeId = Number(notice?.id || 0) || null;
  if (titleEl) titleEl.value = notice?.title || "";
  if (contentEl) contentEl.value = notice?.content || "";
  if (pinnedEl) pinnedEl.checked = Boolean(notice?.is_pinned);
  if (modalTitleEl) modalTitleEl.textContent = editingNoticeId ? "공지 수정" : "공지 작성";
  setClinicNoticeStatus("");
  if (modalEl) modalEl.classList.remove("hidden");
}

function closeClinicNoticeModal() {
  const modalEl = document.getElementById("clinicNoticeModal");
  editingNoticeId = null;
  const titleEl = document.getElementById("clinicNoticeTitle");
  const contentEl = document.getElementById("clinicNoticeContent");
  const pinnedEl = document.getElementById("clinicNoticePinned");
  if (titleEl) titleEl.value = "";
  if (contentEl) contentEl.value = "";
  if (pinnedEl) pinnedEl.checked = false;
  setClinicNoticeStatus("");
  if (modalEl) modalEl.classList.add("hidden");
}

function renderClinicNoticeList() {
  const listEl = document.getElementById("clinicNoticeList");
  if (!listEl) return;
  if (!currentClinicNotices.length) {
    listEl.innerHTML = `
      <div class="clinic-notice-empty">
        <div class="clinic-notice-empty-title">등록된 공지사항이 없습니다.</div>
      </div>
    `;
    return;
  }

  listEl.innerHTML = currentClinicNotices
    .map((row) => {
      const writer = [row.created_by_name, row.created_by_position].filter(Boolean).join(" ");
      const isOpen = Number(openNoticeId) === Number(row.id);
      return `
        <article class="clinic-notice-row ${isOpen ? "is-open" : ""} ${row.is_pinned ? "is-pinned" : ""}">
          <button class="clinic-notice-line" type="button" data-notice-toggle="${row.id}">
            <div class="clinic-notice-col notice-type">${row.is_pinned ? "중요공지" : "공지"}</div>
            <div class="clinic-notice-col notice-title">
              <div class="notice-title-text">
                ${escapeHtml(row.title || "(제목 없음)")}
                ${row.is_new ? '<span class="notice-new-badge">NEW</span>' : ""}
              </div>
            </div>
            <div class="clinic-notice-col notice-date">
              <div class="notice-writer-text">${escapeHtml(writer || "작성자 미상")}</div>
              <div class="notice-date-text">${fmtDateTimeMinute(row.updated_at || row.created_at)}</div>
            </div>
            <div class="clinic-notice-col notice-icon">${isOpen ? "−" : "+"}</div>
          </button>
          <div class="clinic-notice-detail ${isOpen ? "" : "hidden"}">
            <div class="clinic-notice-detail-body">${escapeHtml(row.content || "").replace(/\n/g, "<br/>") || '<span class="muted">내용 없음</span>'}</div>
            <div class="clinic-notice-detail-foot">
              <span class="clinic-notice-foot-writer">${escapeHtml(writer || "작성자 미상")}</span>
              <div class="clinic-notice-item-actions">
                <button class="btn notice-action-btn" type="button" data-notice-edit="${row.id}">수정</button>
                <button class="btn notice-action-btn" type="button" data-notice-delete="${row.id}">삭제</button>
              </div>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

async function markClinicNoticeRead(noticeId) {
  const target = currentClinicNotices.find((row) => Number(row.id) === Number(noticeId));
  if (!target || !target.is_new) return;
  target.is_new = false;
  try {
    const headers = await buildAuthHeaders();
    await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/notices/${noticeId}/read/`, {
      method: "POST",
      credentials: "include",
      headers,
    });
  } catch (_e) {
    // Ignore mark-read failures; keep UI optimistic.
  }
}

async function loadClinicNotices() {
  if (!currentClinicId) return;
  const listEl = document.getElementById("clinicNoticeList");
  if (listEl) listEl.innerHTML = '<div class="muted">불러오는 중...</div>';
  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/notices/`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    currentClinicNotices = Array.isArray(payload?.results) ? payload.results : [];
    if (!currentClinicNotices.length) openNoticeId = null;
    renderClinicNoticeList();
  } catch (e) {
    console.error("notice load failed", e);
    if (listEl) listEl.innerHTML = '<div class="muted">공지사항을 불러오지 못했습니다.</div>';
  }
}

async function saveClinicNotice() {
  if (!currentClinicId) return;
  const values = getClinicNoticeFormValues();
  const wasEditing = Boolean(editingNoticeId);
  if (!values.title && !values.content) {
    setClinicNoticeStatus("제목 또는 내용을 입력하세요.", true);
    return;
  }

  try {
    setClinicNoticeStatus(wasEditing ? "공지 수정 중..." : "공지 저장 중...");
    const headers = await buildAuthHeaders();
    const method = editingNoticeId ? "PATCH" : "POST";
    const endpoint = editingNoticeId
      ? `${API_BASE}/api/data/clinics/${currentClinicId}/notices/${editingNoticeId}/`
      : `${API_BASE}/api/data/clinics/${currentClinicId}/notices/`;
    const res = await fetch(endpoint, {
      method,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const errPayload = await res.json();
        msg = errPayload?.message || msg;
      } catch (_e) {}
      throw new Error(msg);
    }
    closeClinicNoticeModal();
    setClinicNoticeStatus(wasEditing ? "공지 수정 완료" : "공지 저장 완료");
    await loadClinicNotices();
    setClinicNoticeStatus("저장되었습니다.");
  } catch (e) {
    console.error("notice save failed", e);
    setClinicNoticeStatus(`저장 실패: ${e.message || e}`, true);
  }
}

async function deleteClinicNotice(noticeId) {
  if (!currentClinicId || !noticeId) return;
  try {
    setClinicNoticeStatus("공지 삭제 중...");
    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/notices/${noticeId}/`, {
      method: "DELETE",
      credentials: "include",
      headers,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    if (editingNoticeId && Number(editingNoticeId) === Number(noticeId)) {
      closeClinicNoticeModal();
    }
    await loadClinicNotices();
    setClinicNoticeStatus("삭제되었습니다.");
  } catch (e) {
    console.error("notice delete failed", e);
    setClinicNoticeStatus(`삭제 실패: ${e.message || e}`, true);
  }
}

// ================================
// 플랫폼 / 타입 / 검색
// ================================
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
      currentPlatform = btn.dataset.platform || "all";
      root.querySelectorAll(".platform-pill").forEach((b) => b.classList.toggle("active", b === btn));
      loadPosts();
    });
  });
}

function setPostType(type) {
  currentType = type;

  document.querySelectorAll("#postTypePills .type-pill").forEach(el => {
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

function setPostMonth(value) {
  currentPostMonth = value;
  const monthInput = document.getElementById("postMonth");
  const monthLabel = document.getElementById("postMonthLabel");
  if (monthInput) monthInput.value = value;
  if (monthLabel) monthLabel.textContent = formatMonthLabel(value);
}

function shiftMonth(value, delta) {
  const [y, m] = value.split("-").map(Number);
  if (!y || !m) return value;
  const next = new Date(y, m - 1 + delta, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}

function initMonthNav() {
  const monthInput = document.getElementById("postMonth");
  const monthPrev = document.getElementById("postMonthPrev");
  const monthNext = document.getElementById("postMonthNext");

  setPostMonth(currentPostMonth);
  if (monthInput) {
    monthInput.addEventListener("change", () => {
      setPostMonth(monthInput.value);
      loadPosts();
    });
  }
  if (monthPrev) {
    monthPrev.addEventListener("click", () => {
      setPostMonth(shiftMonth(currentPostMonth, -1));
      loadPosts();
    });
  }
  if (monthNext) {
    monthNext.addEventListener("click", () => {
      setPostMonth(shiftMonth(currentPostMonth, 1));
      loadPosts();
    });
  }
}

function initClinicPostsSection() {
  renderPlatformPills();
  bindSearch();
  initMonthNav();
  bindPostSort();
  bindPostTypePills();
  initPhotoModal();
  bindHeaderEditActions();
  loadPosts();
}

function bindPostTypePills() {
  const root = document.getElementById("postTypePills");
  if (!root) return;
  root.querySelectorAll(".type-pill").forEach((btn) => {
    btn.addEventListener("click", () => setPostType(btn.dataset.type || "opinion"));
  });
}

function bindPostSort() {
  const sortSelect = document.getElementById("postSortSelect");
  const sortChips = document.querySelectorAll("#postSortChips .sort-chip");

  const applySortUi = (value) => {
    if (sortSelect) sortSelect.value = value;
    sortChips.forEach((chip) => {
      chip.classList.toggle("active", (chip.dataset.sort || "latest") === value);
    });
  };

  applySortUi(currentSort);

  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      currentSort = sortSelect.value || "latest";
      applySortUi(currentSort);
      loadPosts();
    });
  }

  sortChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      currentSort = chip.dataset.sort || "latest";
      applySortUi(currentSort);
      loadPosts();
    });
  });
}

function initAiIntakeForm() {
  const urlInput = document.getElementById("aiIntakeUrl");
  const titleInput = document.getElementById("aiIntakeTitle");
  const accountInput = document.getElementById("aiIntakeAccount");
  const accountPasswordInput = document.getElementById("aiIntakeAccountPassword");
  const memoInput = document.getElementById("aiIntakeMemo");
  const doctorInput = document.getElementById("aiIntakeDoctor");
  const platformSelect = document.getElementById("aiIntakePlatform");
  const platformHint = document.getElementById("aiIntakePlatformHint");
  const typePills = document.getElementById("aiIntakeTypePills");
  const intakeSubtype = document.getElementById("aiIntakeSubtype");
  const submitBtn = document.getElementById("aiIntakeSubmit");
  const reviewBtn = document.getElementById("aiIntakeReviewBtn");
  const statusEl = document.getElementById("aiIntakeStatus");
  const photoInput = document.getElementById("aiIntakePhotos");
  const photoHint = document.getElementById("aiIntakePhotoHint");
  const reviewMenu = document.querySelector(".ai-review-menu");
  const commentToggleBtn = document.getElementById("aiCommentToggleBtn");
  const messageToggleBtn = document.getElementById("aiMessageToggleBtn");
  const commentWorkspace = document.getElementById("aiCommentWorkspace");
  const messageWorkspace = document.getElementById("aiMessageWorkspace");
  const intakeContentSection = document.getElementById("aiIntakeContentSection");
  const intakeAccountSection = document.getElementById("aiIntakeAccountSection");
  const intakeAttachSection = document.getElementById("aiIntakeAttachSection");
  const commentUrlInput = document.getElementById("aiCommentUrl");
  const commentImageInput = document.getElementById("aiCommentImage");
  const commentImageHint = document.getElementById("aiCommentImageHint");
  const commentAddBtn = document.getElementById("aiCommentAddBtn");
  const commentAddedCountEl = document.getElementById("aiCommentAddedCount");
  const messageUrlInput = document.getElementById("aiMessageUrl");
  const messageTypeSelect = document.getElementById("aiMessageType");
  const messageQtyInput = document.getElementById("aiMessageQty");

  const confirmModal = document.getElementById("aiConfirmModal");
  const confirmUrl = document.getElementById("aiConfirmUrl");
  const confirmTitle = document.getElementById("aiConfirmTitle");
  const confirmAccount = document.getElementById("aiConfirmAccount");
  const confirmAccountPassword = document.getElementById("aiConfirmAccountPassword");
  const confirmMemo = document.getElementById("aiConfirmMemo");
  const confirmDoctor = document.getElementById("aiConfirmDoctor");
  const confirmPlatform = document.getElementById("aiConfirmPlatform");
  const confirmTypePills = document.getElementById("aiConfirmTypePills");
  const confirmSubtype = document.getElementById("aiConfirmSubtype");
  const confirmPhotos = document.getElementById("aiConfirmPhotos");
  const confirmPhotoHint = document.getElementById("aiConfirmPhotoHint");
  const confirmSummary = document.getElementById("aiConfirmSummary");
  const confirmEdit = document.getElementById("aiConfirmEdit");
  const confirmEditBtn = document.getElementById("aiConfirmEditBtn");
  const confirmTypeText = document.getElementById("aiConfirmTypeText");
  const confirmSubtypeText = document.getElementById("aiConfirmSubtypeText");
  const confirmPlatformText = document.getElementById("aiConfirmPlatformText");
  const confirmUrlText = document.getElementById("aiConfirmUrlText");
  const confirmTitleText = document.getElementById("aiConfirmTitleText");
  const confirmAccountText = document.getElementById("aiConfirmAccountText");
  const confirmAccountPasswordText = document.getElementById("aiConfirmAccountPasswordText");
  const confirmMemoText = document.getElementById("aiConfirmMemoText");
  const confirmDoctorText = document.getElementById("aiConfirmDoctorText");
  const confirmDateText = document.getElementById("aiConfirmDateText");
  const confirmPhotoText = document.getElementById("aiConfirmPhotoText");
  const confirmCommentText = document.getElementById("aiConfirmCommentText");
  const confirmPhotoPreview = document.getElementById("aiConfirmPhotoPreview");
  const photoPreviewModal = document.getElementById("photoPreviewModal");
  const photoPreviewImage = document.getElementById("photoPreviewImage");
  const confirmSave = document.getElementById("aiConfirmSave");
  const confirmCancel = document.getElementById("aiConfirmCancel");

  if (!urlInput || !platformSelect || !submitBtn) return;

  const applyIntakeGridLayout = () => {
    const addFieldClass = (el, className) => {
      const field = el?.closest?.(".ai-field");
      if (field && !field.classList.contains(className)) {
        field.classList.add(className);
      }
    };
    addFieldClass(typePills, "field-type");
    addFieldClass(intakeSubtype, "field-subtype");
    addFieldClass(urlInput, "field-url");
    addFieldClass(titleInput, "field-title");
    addFieldClass(accountInput, "field-id");
    addFieldClass(accountPasswordInput, "field-pw");
    addFieldClass(doctorInput, "field-doctor");
    addFieldClass(platformSelect, "field-platform");
    addFieldClass(photoInput, "field-photo");
  };

  applyIntakeGridLayout();

  let currentIntakeType = "opinion";
  let platformManual = false;
  let currentReviewSubtype = "text";
  let currentOpinionSubtype = "concern";
  let intakeSubtypeManual = false;
  let intakeFiles = [];
  let confirmFiles = [];
  let commentBundles = [];
  let pendingCommentImage = null;
  let isCommentMode = false;
  let isMessageMode = false;

  const REVIEW_SUBTYPE_OPTIONS = [
    { value: "text", label: "텍스트 후기" },
    { value: "photo", label: "사진 후기" },
    { value: "consultation", label: "상담 후기" },
  ];

  const OPINION_SUBTYPE_OPTIONS = [
    { value: "concern", label: "고민" },
    { value: "hand", label: "손품" },
    { value: "foot", label: "발품" },
  ];

  const renderSubtypeOptions = (selectEl, type, selectedValue) => {
    if (!selectEl) return;
    const options = type === "review" ? REVIEW_SUBTYPE_OPTIONS : OPINION_SUBTYPE_OPTIONS;
    selectEl.innerHTML = options
      .map((opt) => `<option value="${opt.value}">${opt.label}</option>`)
      .join("");
    if (selectedValue) selectEl.value = selectedValue;
  };

  const getSubtypeLabel = (type, value) => {
    const options = type === "review" ? REVIEW_SUBTYPE_OPTIONS : OPINION_SUBTYPE_OPTIONS;
    return options.find((opt) => opt.value === value)?.label || "-";
  };

  const classifyOpinionSubtype = (title, url) => {
    const text = `${title || ""} ${url || ""}`.toLowerCase();
    const footKeywords = ["방문", "내원", "다녀", "갔다", "직접", "현장", "실제", "후기", "시술", "수술", "경과"];
    const handKeywords = ["상담", "문의", "가격", "비용", "견적", "정보", "비교", "검색", "추천"];
    const has = (keywords) => keywords.some((k) => text.includes(k));
    if (has(footKeywords)) return "foot";
    if (has(handKeywords)) return "hand";
    return "concern";
  };

  const classifyReviewSubtype = (title, photoCount) => {
    const text = `${title || ""}`.toLowerCase();
    if (photoCount > 0) return "photo";
    if (["상담", "문의", "견적"].some((k) => text.includes(k))) return "consultation";
    return "text";
  };

  const autoSetIntakeSubtype = () => {
    if (!intakeSubtype || intakeSubtypeManual) return;
    const title = titleInput?.value || "";
    const url = urlInput?.value || "";
    if (currentIntakeType === "review") {
      currentReviewSubtype = classifyReviewSubtype(title, photoInput?.files?.length || 0);
      renderSubtypeOptions(intakeSubtype, "review", currentReviewSubtype);
    } else {
      currentOpinionSubtype = classifyOpinionSubtype(title, url);
      renderSubtypeOptions(intakeSubtype, "opinion", currentOpinionSubtype);
    }
  };

  const fileKey = (file) => `${file.name}|${file.size}|${file.lastModified}`;

  const addFiles = (targetList, files) => {
    const existing = new Set(targetList.map(fileKey));
    Array.from(files || []).forEach((file) => {
      if (!existing.has(fileKey(file))) {
        targetList.push(file);
        existing.add(fileKey(file));
      }
    });
  };

  const updateFileHint = (hintEl, list) => {
    if (!hintEl) return;
    hintEl.textContent = list.length ? `${list.length}개 파일 선택됨` : "선택된 파일 없음";
  };

  const syncPlatformAuto = () => {
    const info = detectPlatformFromUrl(urlInput.value);
    if (info) {
      platformSelect.value = info.key;
      platformManual = false;
    } else if (!platformManual) {
      platformSelect.value = "";
    }
    if (platformHint) {
      platformHint.textContent = info
        ? `자동 선택 (${info.label})`
        : "자동 선택 실패 (직접 선택)";
    }
  };

  if (!platformSelect.options.length) {
    platformSelect.innerHTML = `
      <option value="">플랫폼</option>
      ${PLATFORM_PILLS.filter(p => p.key !== "all")
        .map(p => `<option value="${p.key}">${p.label}</option>`)
        .join("")}
    `;
  }

  const renderCommentCount = () => {
    if (!commentAddedCountEl) return;
    commentAddedCountEl.textContent = `${commentBundles.length}개 추가됨`;
  };

  const resetCommentEditor = () => {
    if (commentUrlInput) commentUrlInput.value = "";
    if (commentImageInput) commentImageInput.value = "";
    pendingCommentImage = null;
    if (commentImageHint) commentImageHint.textContent = "선택된 파일 없음";
  };

  const applyModeVisibility = () => {
    if (commentWorkspace) commentWorkspace.classList.toggle("hidden", !isCommentMode);
    if (messageWorkspace) messageWorkspace.classList.toggle("hidden", !isMessageMode);
    if (commentToggleBtn) commentToggleBtn.classList.toggle("active", isCommentMode);
    if (messageToggleBtn) messageToggleBtn.classList.toggle("active", isMessageMode);
    if (typePills) {
      const typeButtons = Array.from(typePills.querySelectorAll(".seg-tab[data-type]"));
      typeButtons.forEach((btn) => {
        if (isCommentMode || isMessageMode) {
          btn.classList.remove("active");
        } else {
          btn.classList.toggle("active", (btn.dataset.type || "") === currentIntakeType);
        }
      });
    }
    const hideDefault = isCommentMode || isMessageMode;
    if (intakeContentSection) intakeContentSection.classList.toggle("hidden", hideDefault);
    if (intakeAccountSection) intakeAccountSection.classList.toggle("hidden", hideDefault);
    if (intakeAttachSection) intakeAttachSection.classList.toggle("hidden", hideDefault);
  };

  const setCommentMode = (enabled) => {
    isCommentMode = Boolean(enabled);
    if (isCommentMode) isMessageMode = false;
    applyModeVisibility();
  };

  const setMessageMode = (enabled) => {
    isMessageMode = Boolean(enabled);
    if (isMessageMode) isCommentMode = false;
    applyModeVisibility();
  };

  if (typePills) {
    typePills.querySelectorAll(".seg-tab[data-type]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (isCommentMode) setCommentMode(false);
        if (isMessageMode) setMessageMode(false);
        currentIntakeType = btn.dataset.type || "opinion";
        typePills.querySelectorAll(".seg-tab[data-type]").forEach((b) => b.classList.toggle("active", b === btn));
        if (intakeSubtype) {
          if (currentIntakeType === "review") {
            renderSubtypeOptions(intakeSubtype, "review", currentReviewSubtype);
          } else {
            renderSubtypeOptions(intakeSubtype, "opinion", currentOpinionSubtype);
          }
        }
        autoSetIntakeSubtype();
      });
    });
  }

  if (commentToggleBtn && commentWorkspace) {
    commentToggleBtn.addEventListener("click", () => {
      setCommentMode(true);
    });
  }

  if (messageToggleBtn && messageWorkspace) {
    messageToggleBtn.addEventListener("click", () => {
      setMessageMode(true);
    });
  }

  if (commentImageInput && commentImageHint) {
    commentImageInput.addEventListener("change", () => {
      pendingCommentImage = commentImageInput.files?.[0] || null;
      commentImageHint.textContent = pendingCommentImage ? pendingCommentImage.name : "선택된 파일 없음";
    });
  }

  if (commentAddBtn) {
    commentAddBtn.addEventListener("click", () => {
      const url = String(commentUrlInput?.value || "").trim();
      if (!url) {
        if (statusEl) statusEl.textContent = "댓글 URL을 입력하세요.";
        return;
      }
      if (!pendingCommentImage) {
        if (statusEl) statusEl.textContent = "댓글 이미지를 선택하세요.";
        return;
      }
      commentBundles.push({
        id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        url,
        imageFile: pendingCommentImage,
        previewUrl: URL.createObjectURL(pendingCommentImage),
      });
      renderCommentCount();
      resetCommentEditor();
      if (statusEl) statusEl.textContent = "댓글 묶음이 추가되었습니다.";
    });
  }

  if (platformSelect) {
    platformSelect.addEventListener("change", () => {
      platformManual = true;
    });
  }

  if (confirmSubtype && !confirmSubtype.options.length) {
    renderSubtypeOptions(confirmSubtype, "review", currentReviewSubtype);
  }

  if (intakeSubtype && !intakeSubtype.options.length) {
    renderSubtypeOptions(intakeSubtype, "opinion", currentOpinionSubtype);
  }

  urlInput.addEventListener("input", syncPlatformAuto);
  urlInput.addEventListener("input", autoSetIntakeSubtype);
  if (titleInput) titleInput.addEventListener("input", autoSetIntakeSubtype);

  const closeConfirmModal = () => {
    if (confirmModal) confirmModal.classList.add("hidden");
  };

  const toggleConfirmEdit = (editing) => {
    if (confirmSummary) confirmSummary.classList.toggle("hidden", editing);
    if (confirmEdit) confirmEdit.classList.toggle("hidden", !editing);
    if (confirmEditBtn) confirmEditBtn.classList.toggle("hidden", editing);
  };

  const syncSubtypeVisibility = () => {
    const activeType = confirmTypePills?.querySelector(".seg-tab.active")?.dataset?.type || currentIntakeType;
    if (confirmSubtype) {
      confirmSubtype.closest(".ai-field")?.classList.remove("hidden");
    }
    const nextValue = activeType === "review" ? currentReviewSubtype : currentOpinionSubtype;
    renderSubtypeOptions(confirmSubtype, activeType, nextValue);
    if (confirmSubtypeText) {
      confirmSubtypeText.textContent = getSubtypeLabel(activeType, confirmSubtype?.value);
    }
  };

  const openConfirmModal = () => {
    if (!confirmModal) return;
    confirmFiles = [];
    if (confirmPlatform && !confirmPlatform.options.length) {
      confirmPlatform.innerHTML = platformSelect.innerHTML;
    }
    if (confirmUrl) confirmUrl.value = urlInput.value.trim();
    if (confirmTitle) confirmTitle.value = (titleInput?.value || "").trim();
    if (confirmAccount) confirmAccount.value = (accountInput?.value || "").trim();
    if (confirmAccountPassword) confirmAccountPassword.value = (accountPasswordInput?.value || "").trim();
    if (confirmMemo) confirmMemo.value = (memoInput?.value || "").trim();
    if (confirmDoctor) confirmDoctor.value = (doctorInput?.value || "").trim();
    if (confirmPlatform) confirmPlatform.value = platformSelect.value;
    if (confirmTypePills) {
      confirmTypePills.querySelectorAll(".seg-tab").forEach((b) => {
        b.classList.toggle("active", b.dataset.type === currentIntakeType);
      });
    }
    if (confirmSubtype) {
      if (currentIntakeType === "review") {
        const selected = intakeSubtype?.value;
        const photoCount = photoInput?.files?.length || 0;
        currentReviewSubtype = selected || (photoCount ? "photo" : "text");
        renderSubtypeOptions(confirmSubtype, "review", currentReviewSubtype);
      } else {
        const selected = intakeSubtype?.value;
        currentOpinionSubtype = selected || "concern";
        renderSubtypeOptions(confirmSubtype, "opinion", currentOpinionSubtype);
      }
    }
    updateFileHint(confirmPhotoHint, intakeFiles);
    if (confirmTypeText) {
      confirmTypeText.textContent = currentIntakeType === "review" ? "후기" : "여론";
    }
    if (confirmSubtypeText) {
      const subtypeValue = confirmSubtype?.value;
      confirmSubtypeText.textContent = getSubtypeLabel(currentIntakeType, subtypeValue);
    }
    if (confirmPlatformText) {
      const label = platformSelect?.selectedOptions?.[0]?.textContent || "-";
      confirmPlatformText.textContent = label;
    }
    if (confirmUrlText) confirmUrlText.textContent = confirmUrl?.value || "-";
    if (confirmTitleText) confirmTitleText.textContent = confirmTitle?.value || "-";
    if (confirmAccountText) confirmAccountText.textContent = confirmAccount?.value || "-";
    if (confirmAccountPasswordText) confirmAccountPasswordText.textContent = confirmAccountPassword?.value || "-";
    if (confirmMemoText) confirmMemoText.textContent = confirmMemo?.value || "-";
    if (confirmDoctorText) confirmDoctorText.textContent = confirmDoctor?.value || "-";
    if (confirmDateText) {
      const now = new Date();
      confirmDateText.textContent = now.toLocaleDateString("ko-KR");
    }
    if (confirmPhotoText) {
      confirmPhotoText.textContent = intakeFiles.length ? `${intakeFiles.length}개` : "없음";
    }
    if (confirmCommentText) {
      confirmCommentText.textContent = `${commentBundles.length}개`;
    }
    if (confirmPhotoPreview) {
      const files = intakeFiles;
      if (!files.length) {
        confirmPhotoPreview.innerHTML = "<span class='muted'>없음</span>";
      } else {
        confirmPhotoPreview.innerHTML = files
          .slice(0, 4)
          .map((file) => {
            const url = URL.createObjectURL(file);
            return `<img src="${url}" alt="preview" data-preview="${url}" />`;
          })
          .join("");
        confirmPhotoPreview.querySelectorAll("img").forEach((img) => {
          img.addEventListener("click", (e) => {
            e.stopPropagation();
            if (!photoPreviewModal || !photoPreviewImage) return;
            photoPreviewImage.src = img.dataset.preview || img.src;
            photoPreviewModal.classList.remove("hidden");
          });
        });
      }
    }
    syncSubtypeVisibility();
    toggleConfirmEdit(false);
    confirmModal.classList.remove("hidden");
  };

  const bindConfirmTypePills = () => {
    if (!confirmTypePills) return;
    confirmTypePills.querySelectorAll(".seg-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        confirmTypePills.querySelectorAll(".seg-tab").forEach((b) => b.classList.toggle("active", b === btn));
        const activeType = btn.dataset.type || currentIntakeType;
        if (activeType === "review") {
          renderSubtypeOptions(confirmSubtype, "review", currentReviewSubtype);
        } else {
          renderSubtypeOptions(confirmSubtype, "opinion", currentOpinionSubtype);
        }
        syncSubtypeVisibility();
      });
    });
  };

  bindConfirmTypePills();

  if (confirmModal) {
    confirmModal.addEventListener("click", (e) => {
      const target = e.target;
      if (target?.dataset?.close) {
        closeConfirmModal();
      }
    });
  }

  if (photoPreviewModal) {
    photoPreviewModal.addEventListener("click", (e) => {
      const target = e.target;
      if (target?.dataset?.close) {
        photoPreviewModal.classList.add("hidden");
      }
    });
  }

  if (confirmEditBtn) {
    confirmEditBtn.addEventListener("click", () => toggleConfirmEdit(true));
  }

  if (confirmSubtype) {
    confirmSubtype.addEventListener("change", () => {
      const activeType = confirmTypePills?.querySelector(".seg-tab.active")?.dataset?.type || currentIntakeType;
      if (activeType === "review") {
        currentReviewSubtype = confirmSubtype.value;
      } else {
        currentOpinionSubtype = confirmSubtype.value;
      }
      if (confirmSubtypeText) {
        confirmSubtypeText.textContent = getSubtypeLabel(activeType, confirmSubtype.value);
      }
    });
  }

  if (intakeSubtype) {
    intakeSubtype.addEventListener("change", () => {
      intakeSubtypeManual = true;
      if (currentIntakeType === "review") {
        currentReviewSubtype = intakeSubtype.value;
      } else {
        currentOpinionSubtype = intakeSubtype.value;
      }
    });
  }

  if (confirmPhotos && confirmPhotoHint) {
    confirmPhotos.addEventListener("change", () => {
      addFiles(confirmFiles, confirmPhotos.files);
      updateFileHint(confirmPhotoHint, confirmFiles);
      confirmPhotos.value = "";
    });
  }

  const submitIntake = async () => {
      const messageUrl = (messageUrlInput?.value || "").trim();
      const url = isMessageMode ? messageUrl : (confirmUrl?.value.trim() || "");
      const title = isMessageMode ? "쪽지 작업" : (confirmTitle?.value || "").trim();
      const account = (confirmAccount?.value || "").trim();
      const accountPassword = (confirmAccountPassword?.value || "").trim();
      const memo = (confirmMemo?.value || "").trim();
      const doctor = (confirmDoctor?.value || "").trim();
      const platform = isMessageMode ? (detectPlatformFromUrl(url)?.key || "") : (confirmPlatform?.value || "");
      const type = isMessageMode ? "opinion" : (confirmTypePills?.querySelector(".seg-tab.active")?.dataset?.type || currentIntakeType);
      const subtype = confirmSubtype?.value || "text";
      const messageType = String(messageTypeSelect?.value || "").trim();
      const messageQty = Number(messageQtyInput?.value || 1);

      if (!isCommentMode) {
        if (!url) {
          if (statusEl) statusEl.textContent = "URL을 입력하세요.";
          return;
        }
        if (!platform) {
          if (statusEl) statusEl.textContent = isMessageMode ? "URL에서 플랫폼을 찾지 못했습니다." : "플랫폼을 선택하세요.";
          return;
        }
        if (isMessageMode && !messageType) {
          if (statusEl) statusEl.textContent = "쪽지구분을 선택하세요.";
          return;
        }
        if (isMessageMode && (!Number.isFinite(messageQty) || messageQty < 1)) {
          if (statusEl) statusEl.textContent = "쪽지수량은 1 이상이어야 합니다.";
          return;
        }
      }

      const form = new FormData();
      if (isCommentMode) {
        form.append(
          "comment_urls",
          JSON.stringify(commentBundles.map((x) => ({ url: String(x?.url || "").trim() })).filter((x) => x.url))
        );
        commentBundles.forEach((bundle) => {
          if (bundle?.imageFile) {
            form.append("comment_images", bundle.imageFile);
          }
        });
      } else if (isMessageMode) {
        form.append("url", url);
        form.append("platform", platform);
        form.append("message_type", messageType);
        form.append("message_count", String(Number.isFinite(messageQty) ? messageQty : 1));
      } else {
        form.append("url", url);
        form.append("platform", platform);
        form.append("title", title);
        if (doctor) form.append("doctor_name", doctor);
        if (account) form.append("account", account);
        if (accountPassword) form.append("account_password", accountPassword);
        if (memo) form.append("memo", memo);
        form.append("type", type);
        if (type === "review") {
          form.append("review_subtype", subtype);
        } else if (type === "opinion") {
          form.append("opinion_subtype", subtype);
        }
      }

      if (!isCommentMode && !isMessageMode) {
        const sourceFiles = confirmFiles.length ? confirmFiles : intakeFiles;
        sourceFiles.forEach((file) => {
          form.append("photos", file);
        });
      }

      if (statusEl) statusEl.textContent = "처리 중...";
      confirmSave.disabled = true;
      submitBtn.disabled = true;
      try {
        const headers = await buildAuthHeaders();
        const endpoint = isCommentMode
          ? `${API_BASE}/api/data/clinics/${currentClinicId}/comment-bundles/`
          : (isMessageMode
              ? `${API_BASE}/api/data/clinics/${currentClinicId}/message-logs/`
              : `${API_BASE}/api/data/clinics/${currentClinicId}/posts/`);
        const res = await fetch(
          endpoint,
          {
            method: "POST",
            credentials: "include",
            headers,
            body: form,
          }
        );

        if (!res.ok) {
          let failMessage = "저장 실패";
          try {
            const errorBody = await res.json();
            if (errorBody?.message) {
              failMessage = String(errorBody.message);
            }
          } catch (_) {
            // ignore parse error
          }
          if (statusEl) statusEl.textContent = failMessage;
          return;
        }

        if (statusEl) statusEl.textContent = "저장 완료";
        urlInput.value = "";
        if (titleInput) titleInput.value = "";
        if (accountInput) accountInput.value = "";
        if (accountPasswordInput) accountPasswordInput.value = "";
        if (memoInput) memoInput.value = "";
        if (doctorInput) doctorInput.value = "";
        if (messageUrlInput) messageUrlInput.value = "";
        if (messageTypeSelect) messageTypeSelect.value = "";
        if (messageQtyInput) messageQtyInput.value = "1";
        if (photoInput) photoInput.value = "";
        if (confirmPhotos) confirmPhotos.value = "";
        intakeFiles = [];
        confirmFiles = [];
        commentBundles.forEach((item) => {
          if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
        });
        commentBundles = [];
        updateFileHint(photoHint, intakeFiles);
        updateFileHint(confirmPhotoHint, confirmFiles);
        renderCommentCount();
        resetCommentEditor();
        if (confirmPhotoPreview) confirmPhotoPreview.innerHTML = "";
        platformSelect.value = "";
        platformManual = false;
        closeConfirmModal();
        await Promise.all([
          loadCommentBundleList(),
          loadPosts(),
          refreshClinicCalendar(),
        ]);
      } catch (e) {
        console.error("ai intake error", e);
        if (statusEl) statusEl.textContent = "저장 실패";
      } finally {
        confirmSave.disabled = false;
        submitBtn.disabled = false;
      }
  };

  submitBtn.onclick = () => {
    if (isCommentMode) {
      if (!commentBundles.length) {
        if (statusEl) statusEl.textContent = "댓글 묶음을 1개 이상 추가하세요.";
        return;
      }
      submitIntake();
      return;
    }
    if (isMessageMode) {
      submitIntake();
      return;
    }

    const url = urlInput.value.trim();
    if (!url) {
      if (statusEl) statusEl.textContent = "URL을 입력하세요.";
      return;
    }
    syncPlatformAuto();
    openConfirmModal();
  };

  if (confirmSave) {
    confirmSave.onclick = submitIntake;
  }

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
        if (type === "todaktok") {
          window.location.href = `review.html?clinic_id=${currentClinicId}&platform=todaktok`;
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
      addFiles(intakeFiles, photoInput.files);
      updateFileHint(photoHint, intakeFiles);
      photoInput.value = "";
      autoSetIntakeSubtype();
    });
  }

  renderCommentCount();
  setCommentMode(false);
}

function initCommentMonthNav() {
  const monthInput = document.getElementById("commentMonth");
  const monthLabel = document.getElementById("commentMonthLabel");
  const monthPrev = document.getElementById("commentMonthPrev");
  const monthNext = document.getElementById("commentMonthNext");

  const setCommentMonth = (value) => {
    currentCommentMonth = value || getThisMonth();
    if (monthInput) monthInput.value = currentCommentMonth;
    if (monthLabel) monthLabel.textContent = formatMonthLabel(currentCommentMonth);
  };

  setCommentMonth(currentCommentMonth);

  if (monthInput) {
    monthInput.addEventListener("change", () => {
      setCommentMonth(monthInput.value);
      loadCommentBundleList();
    });
  }
  if (monthPrev) {
    monthPrev.addEventListener("click", () => {
      setCommentMonth(shiftMonth(currentCommentMonth, -1));
      loadCommentBundleList();
    });
  }
  if (monthNext) {
    monthNext.addEventListener("click", () => {
      setCommentMonth(shiftMonth(currentCommentMonth, 1));
      loadCommentBundleList();
    });
  }
}

function bindPostsDashboardLink() {
  const btn = document.getElementById("goPostsDashboard");
  if (!btn) return;
  btn.addEventListener("click", () => {
    window.nav.go(`posts_dashboard?clinic_id=${currentClinicId}`);
  });
}

// ================================
// 캘린더
// ================================
function initClinicCalendar() {
  const prevBtn = document.getElementById("calendarPrevMonth");
  const nextBtn = document.getElementById("calendarNextMonth");
  const monthInput = document.getElementById("calendarMonth");
  const workToggle = document.getElementById("clinicCalendarWorkToggle");

  if (prevBtn) {
    prevBtn.addEventListener("click", () => shiftCalendarMonth(-1));
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => shiftCalendarMonth(1));
  }
  if (monthInput) {
    monthInput.value = currentCalendarMonth;
    monthInput.addEventListener("change", () => {
      currentCalendarMonth = monthInput.value || getThisMonth();
      updateCalendarLabel();
      refreshClinicCalendar();
    });
  }
  if (workToggle) {
    workToggle.addEventListener("click", () => {
      workToggle.classList.add("active");
      calendarMemoOnly = false;
      updateCalendarBoardTitle(false);
      refreshClinicCalendar();
    });
  }

  updateCalendarLabel();
  initCalendarDetailPanel();
  updateCalendarBoardTitle(calendarMemoOnly);
  initCalendarEditModal();
  refreshClinicCalendar();
}

function initCalendarEditModal() {
  const modal = document.getElementById("calendarEditModal");
  if (!modal) return;
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) {
      modal.classList.add("hidden");
    }
  });
  document.getElementById("calendarEditCancel")?.addEventListener("click", () => {
    modal.classList.add("hidden");
  });
  document.getElementById("calendarEditSave")?.addEventListener("click", saveCalendarEdit);
  document.getElementById("calendarEditDelete")?.addEventListener("click", deleteCalendarEdit);

  const typeEl = document.getElementById("calendarEditType");
  typeEl?.addEventListener("change", () => {
    toggleCalendarSubtypeFields(typeEl.value);
  });

  window.openPostEditor = openCalendarPostEditor;
}

function toggleCalendarSubtypeFields(type) {
  const reviewField = document.getElementById("calendarEditSubtypeField");
  const opinionField = document.getElementById("calendarEditOpinionSubtypeField");
  if (reviewField) reviewField.style.display = type === "review" ? "block" : "none";
  if (opinionField) opinionField.style.display = type === "opinion" ? "block" : "none";
}

let currentCalendarEdit = { postId: null, clinicId: null };

async function openCalendarPostEditor({ postId, clinicId }) {
  if (!postId || !clinicId) return;
  currentCalendarEdit = { postId, clinicId };
  const modal = document.getElementById("calendarEditModal");
  if (!modal) return;

  let post = postsCache.get(String(postId));
  if (!post) {
    try {
      const headers = await buildAuthHeaders();
      const res = await fetch(`${API_BASE}/api/data/clinics/${clinicId}/posts/${postId}/`, {
        credentials: "include",
        headers,
      });
      if (res.ok) {
        post = await res.json();
      }
    } catch (e) {
      console.warn("post fetch failed", e);
    }
  }
  if (!post) return;

  const platformEl = document.getElementById("calendarEditPlatform");
  if (platformEl && !platformEl.options.length) {
    platformEl.innerHTML = PLATFORM_PILLS.filter((p) => p.key !== "all")
      .map((p) => `<option value="${p.key}">${p.label}</option>`)
      .join("");
  }

  if (!assigneeNameMap.size) {
    await loadAssignees();
  }
  const assigneeEl = document.getElementById("calendarEditAssignee");
  if (assigneeEl) {
    assigneeEl.innerHTML = `
      <option value="">담당자 없음</option>
      ${Array.from(assigneeNameMap.entries()).map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}
    `;
  }

  document.getElementById("calendarEditDate").value = (post.published_at || post.updated_at || "").slice(0, 10);
  document.getElementById("calendarEditType").value = post.type || "opinion";
  document.getElementById("calendarEditSubtype").value = post.review_subtype || "text";
  document.getElementById("calendarEditOpinionSubtype").value = post.opinion_subtype || "concern";
  if (platformEl) platformEl.value = post.platform || "";
  document.getElementById("calendarEditTitle").value = post.title || "";
  document.getElementById("calendarEditUrl").value = post.url || "";
  document.getElementById("calendarEditViews").value = post.views ?? 0;
  document.getElementById("calendarEditComments").value = post.comments ?? 0;
  document.getElementById("calendarEditMessages").value = post.message_count ?? 0;
  if (assigneeEl) assigneeEl.value = post.assignee || "";

  toggleCalendarSubtypeFields(post.type || "opinion");
  modal.classList.remove("hidden");
}

async function saveCalendarEdit() {
  const { postId, clinicId } = currentCalendarEdit;
  if (!postId || !clinicId) return;
  const payload = {
    type: document.getElementById("calendarEditType")?.value || "opinion",
    review_subtype: document.getElementById("calendarEditSubtype")?.value || null,
    opinion_subtype: document.getElementById("calendarEditOpinionSubtype")?.value || null,
    platform: document.getElementById("calendarEditPlatform")?.value || "",
    title: document.getElementById("calendarEditTitle")?.value || "",
    url: document.getElementById("calendarEditUrl")?.value || "",
    views: Number(document.getElementById("calendarEditViews")?.value || 0),
    comments: Number(document.getElementById("calendarEditComments")?.value || 0),
    message_count: Number(document.getElementById("calendarEditMessages")?.value || 0),
    assignee: document.getElementById("calendarEditAssignee")?.value || "",
    published_at: document.getElementById("calendarEditDate")?.value || "",
  };
  if (payload.type !== "review") payload.review_subtype = null;
  if (payload.type !== "opinion") payload.opinion_subtype = null;

  const headers = await buildAuthHeaders();
  const res = await fetch(`${API_BASE}/api/data/clinics/${clinicId}/posts/${postId}/`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    window.showAlert?.("수정 실패");
    return;
  }
  document.getElementById("calendarEditModal")?.classList.add("hidden");
  refreshClinicCalendar();
}

async function deleteCalendarEdit() {
  const { postId, clinicId } = currentCalendarEdit;
  if (!postId || !clinicId) return;
  const ok = await window.appConfirm?.("게시글을 삭제할까요?") ?? confirm("게시글을 삭제할까요?");
  if (!ok) return;
  const headers = await buildAuthHeaders();
  const res = await fetch(`${API_BASE}/api/data/clinics/${clinicId}/posts/${postId}/`, {
    method: "DELETE",
    credentials: "include",
    headers,
  });
  if (!res.ok) {
    window.showAlert?.("삭제 실패");
    return;
  }
  document.getElementById("calendarEditModal")?.classList.add("hidden");
  refreshClinicCalendar();
}

function updateCalendarLabel() {
  const label = document.getElementById("calendarMonthLabel");
  if (!label) return;
  const [year, month] = currentCalendarMonth.split("-");
  if (!year || !month) return;
  label.textContent = `${year}년 ${month}월`;
}

function shiftCalendarMonth(delta) {
  const [year, month] = currentCalendarMonth.split("-").map(Number);
  if (!year || !month) return;
  const date = new Date(year, month - 1 + delta, 1);
  currentCalendarMonth = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  const monthInput = document.getElementById("calendarMonth");
  if (monthInput) monthInput.value = currentCalendarMonth;
  updateCalendarLabel();
  refreshClinicCalendar();
}

function updateCalendarBoardTitle(isMemoOnly) {
  const titleEl = document.getElementById("calendarBoardTitle");
  if (!titleEl) return;
  titleEl.innerText = "작업 캘린더";
}

function getPlatformLabel(platformKey) {
  if (!platformKey) return "";
  const match = PLATFORM_PILLS.find((p) => p.key === platformKey);
  return match ? match.label : platformKey;
}

function formatCommentBundleDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleDateString("ko-KR");
}

async function loadCommentBundleList() {
  const root = document.getElementById("clinicCommentBundleList");
  if (!root || !currentClinicId) return;
  root.innerHTML = `<div class="muted">불러오는 중...</div>`;
  try {
    const headers = await buildAuthHeaders();
    const buildParams = (type) => {
      const params = new URLSearchParams({
        type,
        platform: "all",
        month: currentCommentMonth,
      });
      return params;
    };

    const [opinionRes, reviewRes, commentFetch, messageFetch] = await Promise.all([
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${buildParams("opinion")}`, {
        credentials: "include",
        headers,
      }),
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${buildParams("review")}`, {
        credentials: "include",
        headers,
      }),
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/comment-bundles/`, {
        credentials: "include",
        headers,
      }),
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/message-logs/`, {
        credentials: "include",
        headers,
      }),
    ]);

    if (!opinionRes.ok || !reviewRes.ok) {
      root.innerHTML = `<div class="muted">댓글/쪽지 리스트를 불러오지 못했습니다.</div>`;
      return;
    }

    let commentData = { results: [] };
    let messageData = { results: [] };
    if (commentFetch?.ok) {
      try {
        commentData = await commentFetch.json();
      } catch (_) {}
    }
    if (messageFetch?.ok) {
      try {
        messageData = await messageFetch.json();
      } catch (_) {}
    }

    const [opinionData, reviewData] = await Promise.all([
      opinionRes.json(),
      reviewRes.json(),
    ]);
    const posts = [
      ...(Array.isArray(opinionData?.results) ? opinionData.results : []),
      ...(Array.isArray(reviewData?.results) ? reviewData.results : []),
    ];
    if (!posts.length) {
      root.innerHTML = `<div class="muted">등록된 댓글이 없습니다.</div>`;
      return;
    }

    const commentCountByUrl = new Map();
    commentBundleItemsByUrl = new Map();
    (Array.isArray(commentData?.results) ? commentData.results : [])
      .forEach((row) => {
        const key = getCountUrlKey(row?.url);
        if (!key) return;
        commentCountByUrl.set(key, (commentCountByUrl.get(key) || 0) + 1);
        const list = commentBundleItemsByUrl.get(key) || [];
        list.push({
          id: row?.id,
          url: String(row?.url || "").trim(),
          image_url: String(row?.image_url || "").trim(),
          created_at: row?.created_at,
          created_by_name: row?.created_by_name || "-",
        });
        commentBundleItemsByUrl.set(key, list);
      });

    const messageCountByUrl = new Map();
    messageLogItemsByUrl = new Map();
    (Array.isArray(messageData?.results) ? messageData.results : [])
      .forEach((row) => {
        const key = getCountUrlKey(row?.url);
        if (!key) return;
        const count = Number(row?.message_count || 0);
        messageCountByUrl.set(key, (messageCountByUrl.get(key) || 0) + count);
        const list = messageLogItemsByUrl.get(key) || [];
        list.push({
          id: row?.id,
          message_type: String(row?.message_type || ""),
          message_count: Number(row?.message_count || 0),
          created_at: row?.created_at,
          cafe: detectCafeFromUrl(row?.url || ""),
        });
        messageLogItemsByUrl.set(key, list);
      });

    const rows = posts
      .map((post) => {
        const date = getPostDate(post) || "-";
        const url = String(post?.url || "").trim();
        const assignee = getAssigneeDisplay(post);
        const typeLabel = post?.type === "review" ? "후기" : "여론";
        const platform = getPlatformLabel(post?.platform) || "-";
        const cafe = detectCafeFromUrl(post?.url || "");
        const postUrlKey = getCountUrlKey(post?.url);
        const comment_count = Number(commentCountByUrl.get(postUrlKey) || 0);
        const message_count = Number(messageCountByUrl.get(postUrlKey) || 0);
        return { date, url, urlKey: postUrlKey, assignee, typeLabel, platform, cafe, comment_count, message_count };
      });

    const tableRows = rows.sort((a, b) => {
      if (a.date === b.date) return String(a.assignee).localeCompare(String(b.assignee), "ko");
      return String(b.date).localeCompare(String(a.date));
    });

    root.innerHTML = `
      <div class="comment-row comment-row-head">
        <div>날짜</div>
        <div>URL</div>
        <div>작업자</div>
        <div>댓글건수</div>
        <div>쪽지건수</div>
        <div>유형</div>
        <div>플랫폼</div>
        <div>카페</div>
      </div>
      ${tableRows
        .map((row) => `
          <div class="comment-row">
            <div>${escapeHtml(row.date)}</div>
            <div class="comment-url-cell" title="${escapeHtml(row.url)}">${escapeHtml(row.url)}</div>
            <div>${escapeHtml(row.assignee)}</div>
            <div>
              <button
                type="button"
                class="comment-count-btn"
                data-url-key="${escapeHtml(row.urlKey)}"
                data-url="${escapeHtml(row.url)}"
                ${row.comment_count > 0 ? "" : "disabled"}
              >
                ${row.comment_count}
              </button>
            </div>
            <div>
              <button
                type="button"
                class="message-count-btn"
                data-url-key="${escapeHtml(row.urlKey)}"
                data-url="${escapeHtml(row.url)}"
                ${row.message_count > 0 ? "" : "disabled"}
              >
                ${row.message_count}
              </button>
            </div>
            <div>${escapeHtml(row.typeLabel)}</div>
            <div>${escapeHtml(row.platform)}</div>
            <div>${escapeHtml(row.cafe)}</div>
          </div>
        `)
        .join("")}
    `;

    root.querySelectorAll(".comment-count-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const urlKey = String(btn.dataset.urlKey || "");
        const url = String(btn.dataset.url || "");
        if (!urlKey) return;
        openCommentBundleModal(urlKey, url);
      });
    });
    root.querySelectorAll(".message-count-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const urlKey = String(btn.dataset.urlKey || "");
        const url = String(btn.dataset.url || "");
        if (!urlKey) return;
        openMessageLogModal(urlKey, url);
      });
    });
  } catch (e) {
    console.error("comment bundle list load failed", e);
    root.innerHTML = `<div class="muted">댓글 리스트를 불러오지 못했습니다.</div>`;
  }
}

function initCommentBundleModal() {
  const modal = document.getElementById("commentBundleModal");
  const closeBtn = document.getElementById("commentBundleModalClose");
  if (!modal) return;
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.classList.add("hidden");
    });
  }
}

function openCommentBundleModal(urlKey, displayUrl) {
  const modal = document.getElementById("commentBundleModal");
  const urlEl = document.getElementById("commentBundleModalUrl");
  const listEl = document.getElementById("commentBundleModalList");
  if (!modal || !urlEl || !listEl) return;

  const items = commentBundleItemsByUrl.get(urlKey) || [];
  urlEl.textContent = displayUrl || "-";
  if (!items.length) {
    listEl.innerHTML = `<div class="muted">해당 URL의 댓글 작성 내역이 없습니다.</div>`;
  } else {
    const sorted = [...items].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    listEl.innerHTML = sorted
      .map((item) => `
        <article class="comment-bundle-item">
          ${
            item.image_url
              ? `<a class="comment-bundle-item-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">
                  <img class="comment-bundle-item-img" src="${escapeHtml(item.image_url)}" alt="comment-bundle" />
                </a>`
              : `<a class="comment-bundle-item-url" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.url)}</a>`
          }
        </article>
      `)
      .join("");
  }
  modal.classList.remove("hidden");
}

window.openCommentBundleModalByUrl = (url) => {
  const normalizedUrl = String(url || "").trim();
  if (!normalizedUrl) return;
  const urlKey = getCountUrlKey(normalizedUrl);
  if (!urlKey) return;
  openCommentBundleModal(urlKey, normalizedUrl);
};

function initMessageLogModal() {
  const modal = document.getElementById("messageLogModal");
  const closeBtn = document.getElementById("messageLogModalClose");
  if (!modal) return;
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.classList.add("hidden");
    });
  }
}

function getMessageTypeLabel(value) {
  if (value === "prev_opinion") return "지난여론쪽지";
  if (value === "comment_work") return "댓글작업쪽지";
  return "-";
}

function openMessageLogModal(urlKey, displayUrl) {
  const modal = document.getElementById("messageLogModal");
  const urlEl = document.getElementById("messageLogModalUrl");
  const listEl = document.getElementById("messageLogModalList");
  if (!modal || !urlEl || !listEl) return;

  const items = messageLogItemsByUrl.get(urlKey) || [];
  urlEl.textContent = displayUrl || "-";
  if (!items.length) {
    listEl.innerHTML = `<div class="muted">해당 URL의 쪽지 내역이 없습니다.</div>`;
  } else {
    const sorted = [...items].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    listEl.innerHTML = `
      <div class="message-log-head">
        <div>작성일</div>
        <div>쪽지구분</div>
        <div>수량</div>
        <div>카페</div>
      </div>
      ${sorted
        .map((item) => `
          <div class="message-log-row">
            <div>${escapeHtml(fmtDateOnly(item.created_at))}</div>
            <div>${escapeHtml(getMessageTypeLabel(item.message_type))}</div>
            <div>${Number(item.message_count || 0)}</div>
            <div>${escapeHtml(item.cafe || "-")}</div>
          </div>
        `)
        .join("")}
    `;
  }
  modal.classList.remove("hidden");
}

window.openMessageLogModalByUrl = (url) => {
  const normalizedUrl = String(url || "").trim();
  if (!normalizedUrl) return;
  const urlKey = getCountUrlKey(normalizedUrl);
  if (!urlKey) return;
  openMessageLogModal(urlKey, normalizedUrl);
};

async function refreshClinicCalendar() {
  const calendarId = "clinicCalendarBoard";
  const listId = "clinicCalendarList";
  const calendar = document.getElementById(calendarId);
  const list = document.getElementById(listId);
  if (!calendar || !list) return;

  const headers = await buildAuthHeaders();
  const [opinions, reviews, commentBundleRes] = await Promise.all([
    fetchPostsByMonth("opinion"),
    fetchPostsByMonth("review"),
    fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/comment-bundles/`, {
      credentials: "include",
      headers,
    }),
  ]);

  let commentBundleRows = [];
  if (commentBundleRes?.ok) {
    try {
      const commentBundleData = await commentBundleRes.json();
      commentBundleRows = Array.isArray(commentBundleData?.results) ? commentBundleData.results : [];
    } catch (_) {
      commentBundleRows = [];
    }
  }

  const commentCountByUrl = new Map();
  commentBundleRows.forEach((row) => {
    const key = getCountUrlKey(row?.url);
    if (!key) return;
    commentCountByUrl.set(key, (commentCountByUrl.get(key) || 0) + 1);
  });

  const mapPost = (post, type) => ({
    kind: "post",
    date: getPostDate(post),
    title: post.title,
    title_display: post.title_display,
    url: post.url,
    platform: post.platform,
    platform_label: post.platform_label,
    type,
    review_subtype: post.review_subtype,
    opinion_subtype: post.opinion_subtype,
    views: post.views,
    comments: post.comments,
    comment_work_count: Number(commentCountByUrl.get(getCountUrlKey(post.url)) || 0),
    message_count: post.message_count,
    account: post.account,
    account_password: post.account_password,
    doctor_name: post.doctor_name,
    assignee: getAssigneeDisplay(post),
    photos: Array.isArray(post.photos)
      ? post.photos.map((p) => (p?.url ? p.url : p)).filter(Boolean)
      : [],
    post_id: post.id,
    clinicId: currentClinicId,
    clinic: currentClinicName,
  });

  const items = [
    ...opinions.map((post) => mapPost(post, "opinion")),
    ...reviews.map((post) => mapPost(post, "review")),
  ].filter((item) => item.date);

  renderScheduleCalendar({
    calendarId,
    listId,
    items,
    yearMonth: currentCalendarMonth,
    emptyMessage: "선택한 날짜의 일정이 없습니다.",
    allowEmptyClick: false,
    onDateSelect: null,
  });
}

function initCalendarDetailPanel() {
  const panel = document.getElementById("clinicCalendarDetailPanel");
  const closeBtn = document.getElementById("clinicCalendarDetailClose");
  if (!panel || !closeBtn) return;
  closeBtn.addEventListener("click", () => {
    panel.classList.remove("open");
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.classList.contains("open")) {
      panel.classList.remove("open");
    }
  });
  initPanelResize("clinicCalendarDetailPanel");
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

function initMemoModal() {
  const modal = document.getElementById("clinicCalendarMemoModal");
  if (!modal) return;
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) {
      modal.classList.add("hidden");
    }
  });
}

function openMemoModal() {
  if (!calendarMemoOnly) {
    window.showAlert?.("메모 캘린더로 전환하고 작성해 주세요.");
    return;
  }
  if (!calendarSelectedDate) {
    window.showAlert?.("먼저 날짜를 선택하세요.");
    return;
  }
  document.getElementById("clinicCalendarMemoModal")?.classList.remove("hidden");
}

function setMemoDate(date) {
  calendarSelectedDate = date || "";
  const label = document.getElementById("clinicCalendarMemoDate");
  if (label) label.innerText = calendarSelectedDate || "-";
  renderMemoList(calendarSelectedDate);
}

function renderMemoList(date) {
  const list = document.getElementById("clinicCalendarMemoList");
  if (!list) return;

  if (!date) {
    list.innerHTML = `<div class="muted">날짜를 선택하세요.</div>`;
    return;
  }

  const memos = calendarMemos.filter((memo) => memo.date === date);
  if (!memos.length) {
    list.innerHTML = `<div class="muted">등록된 메모가 없습니다.</div>`;
    return;
  }

  list.innerHTML = memos
    .map((memo) => {
      const timeLabel = formatMemoTime(memo.remind_at);
      const metaLabel = [timeLabel].filter(Boolean).join(" · ");
      return `
        <div class="memo-item" data-id="${memo.id}">
          <div class="memo-meta">
            <span>${metaLabel || "-"}</span>
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
  if (!calendarSelectedDate) {
    window.showAlert?.("먼저 날짜를 선택하세요.");
    return;
  }
  const contentEl = document.getElementById("clinicCalendarMemoContent");
  const remindEl = document.getElementById("clinicCalendarMemoRemind");
  const content = (contentEl?.value || "").trim();
  if (!content) {
    window.showAlert?.("메모 내용을 입력하세요.");
    return;
  }

  const remindAt = remindEl?.value ? new Date(remindEl.value) : null;
  const payload = {
    date: calendarSelectedDate,
    content,
    clinic_id: Number(currentClinicId),
  };
  if (remindAt && !Number.isNaN(remindAt.valueOf())) {
    payload.remind_at = remindAt.toISOString();
  }

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
    if (contentEl) contentEl.value = "";
    if (remindEl) remindEl.value = "";
    document.getElementById("clinicCalendarMemoModal")?.classList.add("hidden");
    await refreshClinicCalendar();
    setMemoDate(calendarSelectedDate);
  } catch (e) {
    console.error("memo save failed", e);
    window.showAlert?.("메모 저장 실패");
  }
}

async function deleteCalendarMemo(memoId) {
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
    await refreshClinicCalendar();
    setMemoDate(calendarSelectedDate);
  } catch (e) {
    console.error("memo delete failed", e);
    window.showAlert?.("메모 삭제 실패");
  }
}

async function setMemoAuthor() {
  const label = document.getElementById("clinicCalendarMemoAuthor");
  if (!label) return;
  try {
    const me = await window.api?.getMe?.();
    label.innerText = me?.name || me?.username || "-";
  } catch (e) {
    label.innerText = "-";
  }
}

// ================================
// 게시글 로드
// ================================
async function loadPosts() {
  if (!currentClinicId) return;
  const root = document.getElementById("postList");
  if (!root) return;

  root.innerHTML = `<div class="muted">불러오는 중...</div>`;

  const buildParams = (type, monthValue) => {
    const params = new URLSearchParams({
      type,
      platform: currentPlatform,
    });
    if (monthValue) params.set("month", monthValue);
    if (currentQuery) params.set("q", currentQuery);
    return params;
  };

  try {
    const headers = await buildAuthHeaders();
    const [opinionRes, reviewRes, opinionTotalRes, reviewTotalRes] = await Promise.all([
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${buildParams("opinion", currentPostMonth)}`, { credentials: "include", headers }),
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${buildParams("review", currentPostMonth)}`, { credentials: "include", headers }),
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${buildParams("opinion", null)}`, { credentials: "include", headers }),
      fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${buildParams("review", null)}`, { credentials: "include", headers }),
    ]);

    const responses = [opinionRes, reviewRes, opinionTotalRes, reviewTotalRes];
    const notOk = responses.find((res) => !res.ok);
    if (notOk) {
      let failMessage = "게시글을 불러오지 못했습니다.";
      try {
        const body = await notOk.json();
        if (body?.message) failMessage = String(body.message);
      } catch (_) {
        // ignore
      }
      root.innerHTML = `<div class="muted">${escapeHtml(failMessage)}</div>`;
      return;
    }

    const opinionData = await opinionRes.json();
    const reviewData = await reviewRes.json();
    const opinionTotalData = await opinionTotalRes.json();
    const reviewTotalData = await reviewTotalRes.json();

    const opinionCountEl = document.getElementById("opinionCount");
    const reviewCountEl = document.getElementById("reviewCount");
    const opinionTotalEl = document.getElementById("opinionTotalCount");
    const reviewTotalEl = document.getElementById("reviewTotalCount");

    if (opinionCountEl) opinionCountEl.textContent = opinionData.count ?? (opinionData.results ? opinionData.results.length : 0);
    if (reviewCountEl) reviewCountEl.textContent = reviewData.count ?? (reviewData.results ? reviewData.results.length : 0);
    if (opinionTotalEl) opinionTotalEl.textContent = opinionTotalData.count ?? (opinionTotalData.results ? opinionTotalData.results.length : 0);
    if (reviewTotalEl) reviewTotalEl.textContent = reviewTotalData.count ?? (reviewTotalData.results ? reviewTotalData.results.length : 0);

    const results = currentType === "review" ? reviewData.results : opinionData.results;
    const filtered = [...(results || [])].filter((post) => {
      const title = String(post?.title || "").trim();
      const memo = String(post?.memo || "").trim();
      return !(title === "쪽지 작업" || memo.startsWith("쪽지구분:"));
    });
    const sortedResults = sortPosts(filtered);
    if (!assigneeNameMap.size) {
      await loadAssignees();
    }
    sortedResults.forEach((post) => {
      if (!post.assignee_name && post.assignee) {
        const mapped = assigneeNameMap.get(String(post.assignee));
        if (mapped) post.assignee_name = mapped;
      }
    });
    postsCache = new Map(sortedResults.map((post) => [String(post.id), post]));
    if (!sortedResults.length) {
      root.innerHTML = `<div class="muted">표시할 게시글이 없습니다.</div>`;
      return;
    }

    root.innerHTML = sortedResults.map((post) => (
      editingAll ? renderEditRow(post) : renderViewRow(post)
    )).join("");

    bindPhotoButtons();
    if (editingAll) {
      bindEditRowHandlers();
      bindSelectionHandlers();
    }
  } catch (e) {
    console.error("load posts failed", e);
    root.innerHTML = `<div class="muted">게시글을 불러오지 못했습니다.</div>`;
  }
}

function bindSelectionHandlers() {
  const selectAll = document.getElementById("postSelectAll");
  const rows = Array.from(document.querySelectorAll(".row-select"));
  const deleteBtn = document.getElementById("postDeleteSelectedBtn");

  const syncDeleteState = () => {
    if (!deleteBtn) return;
    const anyChecked = rows.some((cb) => cb.checked);
    deleteBtn.disabled = !anyChecked;
  };

  if (selectAll) {
    selectAll.checked = false;
    selectAll.addEventListener("change", () => {
      rows.forEach((cb) => {
        cb.checked = selectAll.checked;
      });
      syncDeleteState();
    });
  }

  rows.forEach((cb) => {
    cb.addEventListener("change", syncDeleteState);
  });

  syncDeleteState();
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

function bindPhotoButtons() {
  const root = document.getElementById("postList");
  if (!root) return;
  root.querySelectorAll(".post-photo-btn").forEach((btn) => {
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

function renderViewRow(post) {
  const dateLabel = (post.published_at || post.updated_at || "").slice(0, 10) || "-";
  const assignee = getAssigneeDisplay(post);

  const hasUrl = !!(post.url && post.url.trim());

  let displayPlatform = "-";

  if (hasUrl) {
    // URL이 있을 때만 플랫폼을 계산한다
    if (post.platform && post.platform !== "all") {
      displayPlatform =
        post.platform_label ||
        getPlatformLabel(post.platform) ||
        post.platform;
    } else {
      const detected = detectPlatformFromUrl(post.url);
      displayPlatform = detected?.label || "-";
    }
  }

  const rawPhotos = Array.isArray(post.photos) ? post.photos : [];
  const photos = rawPhotos
    .map((photo) => (photo?.url ? photo.url : photo))
    .filter(Boolean);

  const photoAttr = photos.length
    ? `data-photos="${encodeURIComponent(JSON.stringify(photos))}"`
    : "";

  const photoButton = photos.length
    ? `<button class="post-photo-btn" ${photoAttr}>사진</button>`
    : "-";

  return `
    <div class="post-row">
      <div class="post-select"></div>
      <div>${dateLabel}</div>
      <div class="post-title">
        ${
          hasUrl
            ? `<a href="${post.url}" target="_blank">${escapeHtml(post.title)}</a>`
            : `<span class="muted">${escapeHtml(post.title || "-")}</span>`
        }
      </div>
      <div class="post-num">${post.views ?? 0}</div>
      <div class="post-num">${post.comments ?? 0}</div>
      <div class="post-num">${post.message_count ?? 0}</div>
      <div class="post-assignee">${escapeHtml(assignee)}</div>
      <div class="post-platform">${displayPlatform}</div>
      <div class="post-photo">${photoButton}</div>
    </div>
  `;
}

function renderEditRow(post) {
  const dateValue = (post.published_at || post.updated_at || "").slice(0, 10);
  const platformOptions = PLATFORM_PILLS.filter((p) => p.key !== "all")
    .map((p) => `<option value="${p.key}">${p.label}</option>`)
    .join("");
  const reviewSubtypeOptions = `
    <option value="text">텍스트</option>
    <option value="photo">사진</option>
    <option value="consultation">상담</option>
  `;
  const opinionSubtypeOptions = `
    <option value="concern">고민</option>
    <option value="hand">손품</option>
    <option value="foot">발품</option>
  `;
  const subtypeOptions = post.type === "review" ? reviewSubtypeOptions : opinionSubtypeOptions;
  const subtypeValue = post.type === "review" ? (post.review_subtype || "text") : (post.opinion_subtype || "concern");

  return `
    <div class="post-row editing" data-post-id="${post.id}">
      <div class="post-select"><input type="checkbox" class="row-select" data-post-id="${post.id}" /></div>
      <div class="post-date-edit">
        <input class="inline-input edit-date" type="date" value="${dateValue}" />
      </div>
      <div class="cell-title">
        <input class="inline-input edit-title" value="${escapeHtml(post.title || "")}" />
        <input class="inline-input edit-url" value="${escapeHtml(post.url || "")}" />
        <div class="edit-meta-inline">
          <select class="inline-select edit-type">
            <option value="opinion" ${post.type === "opinion" ? "selected" : ""}>여론</option>
            <option value="review" ${post.type === "review" ? "selected" : ""}>후기</option>
          </select>
          <select class="inline-select edit-subtype-common" data-type="${post.type}" data-initial-value="${subtypeValue}">
            ${subtypeOptions}
          </select>
        </div>
      </div>
      <div class="post-num"><input class="inline-input edit-views" type="number" min="0" value="${post.views ?? 0}" /></div>
      <div class="post-num"><input class="inline-input edit-comments" type="number" min="0" value="${post.comments ?? 0}" /></div>
      <div class="post-num"><input class="inline-input edit-messages" type="number" min="0" value="${post.message_count ?? 0}" /></div>
      <div class="post-assignee">${escapeHtml(getAssigneeDisplay(post))}</div>
      <div class="post-platform">
        <select class="inline-select edit-platform">
          ${platformOptions}
        </select>
      </div>
      <div>-</div>
    </div>
  `;
}

function bindEditRowHandlers() {
  const root = document.getElementById("postList");
  if (!root) return;
  root.querySelectorAll(".edit-platform").forEach((selectEl) => {
    const row = selectEl.closest(".post-row");
    const postId = row?.dataset?.postId;
    const post = postsCache.get(String(postId));
    if (post) {
      const detected = (!post.platform || post.platform === "all")
        ? detectPlatformFromUrl(post.url || post.title || "")
        : null;
      selectEl.value = detected?.key || post.platform || "";
    }
  });
  root.querySelectorAll(".edit-subtype-common").forEach((subtypeSelect) => {
    const initialValue = subtypeSelect.dataset.initialValue || "";
    if (initialValue) subtypeSelect.value = initialValue;
  });
  root.querySelectorAll(".edit-type").forEach((typeSelect) => {
    typeSelect.addEventListener("change", () => {
      const row = typeSelect.closest(".post-row");
      const subtypeSelect = row?.querySelector(".edit-subtype-common");
      if (subtypeSelect) {
        if (typeSelect.value === "review") {
          subtypeSelect.innerHTML = `
            <option value="text">텍스트</option>
            <option value="photo">사진</option>
            <option value="consultation">상담</option>
          `;
          subtypeSelect.value = "text";
        } else {
          subtypeSelect.innerHTML = `
            <option value="concern">고민</option>
            <option value="hand">손품</option>
            <option value="foot">발품</option>
          `;
          subtypeSelect.value = "concern";
        }
      }
    });
  });
}

function bindHeaderEditActions() {
  const editBtn = document.getElementById("clinicPostEditBtn");
  const deleteBtn = document.getElementById("postDeleteSelectedBtn");
  const saveBtn = document.getElementById("clinicPostSaveBtn");
  const cancelBtn = document.getElementById("clinicPostCancelBtn");
  const selectAll = document.getElementById("postSelectAll");
  const selectHead = selectAll?.closest(".post-select-head");
  const table = document.querySelector(".post-table");

  const toggleButtons = (editing) => {
    if (table) table.classList.toggle("editing", editing);
    if (editBtn) editBtn.classList.toggle("hidden", editing);
    if (deleteBtn) deleteBtn.classList.toggle("hidden", !editing);
    if (deleteBtn) deleteBtn.disabled = true;
    if (saveBtn) saveBtn.classList.toggle("hidden", !editing);
    if (cancelBtn) cancelBtn.classList.toggle("hidden", !editing);
    if (selectAll) {
      selectAll.checked = false;
      if (selectHead) selectHead.classList.toggle("hidden", !editing);
    }
  };

  editBtn?.addEventListener("click", () => {
    editingAll = true;
    toggleButtons(true);
    loadPosts();
  });

  cancelBtn?.addEventListener("click", () => {
    editingAll = false;
    toggleButtons(false);
    loadPosts();
  });

  deleteBtn?.addEventListener("click", async () => {
    const list = document.getElementById("postList");
    if (!list) return;
    const checked = Array.from(list.querySelectorAll(".row-select:checked"));
    if (!checked.length) {
      window.showAlert?.("삭제할 게시글을 선택하세요.");
      return;
    }
    const ok = await window.appConfirm?.("선택한 게시글을 삭제할까요?") ?? confirm("선택한 게시글을 삭제할까요?");
    if (!ok) return;
    const headers = await buildAuthHeaders();
    await Promise.all(
      checked.map((cb) =>
        fetch(`${API_BASE}/api/data/clinics/${currentClinicId}/posts/${cb.dataset.postId}/`, {
          method: "DELETE",
          credentials: "include",
          headers,
        })
      )
    );
    loadPosts();
  });

  saveBtn?.addEventListener("click", async () => {
    const list = document.getElementById("postList");
    if (!list) return;
    const rows = Array.from(list.querySelectorAll(".post-row.editing"));
    const headers = await buildAuthHeaders();
    const results = await Promise.all(rows.map(async (row) => {
      const postId = row.dataset.postId;
      const selectedType = row.querySelector(".edit-type")?.value || "opinion";
      const subtypeValue = row.querySelector(".edit-subtype-common")?.value || null;
      const payload = {
        type: selectedType,
        review_subtype: selectedType === "review" ? subtypeValue : null,
        opinion_subtype: selectedType === "opinion" ? subtypeValue : null,
        platform: row.querySelector(".edit-platform")?.value || "",
        title: row.querySelector(".edit-title")?.value || "",
        url: row.querySelector(".edit-url")?.value || "",
        views: Number(row.querySelector(".edit-views")?.value || 0),
        comments: Number(row.querySelector(".edit-comments")?.value || 0),
        message_count: Number(row.querySelector(".edit-messages")?.value || 0),
        published_at: row.querySelector(".edit-date")?.value || "",
      };
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
    toggleButtons(false);
    loadPosts();
  });
}

async function updatePostMessageCount(postId, messageCount) {
  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/${postId}/`;
  try {
    const headers = await buildAuthHeaders();
    await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
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

function sortPosts(list) {
  if (currentSort === "oldest") {
    return list.sort((a, b) => getPostDate(a).localeCompare(getPostDate(b)));
  }
  return list.sort((a, b) => getPostDate(b).localeCompare(getPostDate(a)));
}

async function fetchPostsByMonth(type) {
    const params = new URLSearchParams({
      type,
      platform: "all",
      month: currentCalendarMonth,
    });

  const url = `${API_BASE}/api/data/clinics/${currentClinicId}/posts/?${params}`;
  const headers = await buildAuthHeaders();
  const res = await fetch(url, { credentials: "include", headers });
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
