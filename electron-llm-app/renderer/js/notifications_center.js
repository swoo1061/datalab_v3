window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";
window.globalSearchIndex = window.globalSearchIndex || {
  pages: [
    { key: "알림", page: "notifications_center" },
    { key: "메모센터", page: "notifications_center" },
    { key: "메일센터", page: "mail_center" },
    { key: "근태 정정요청", page: "attendance_admin" },
    { key: "정정요청", page: "attendance_admin" },
    { key: "메모", page: "notifications_center" },
    { key: "메일", page: "mail_center" },
    { key: "대시보드", page: "my_dashboard" },
    { key: "캘린더", page: "calendar_dashboard" },
  ],
};

function detectInitialMode() {
  const raw = (document.body?.dataset?.notifyMode || "").toLowerCase();
  if (raw === "mail") return "mail";
  return "alert";
}

function detectCenterType() {
  const raw = (document.body?.dataset?.notifyMode || "").toLowerCase();
  if (raw === "mail") return "mail";
  if (raw === "attendance") return "attendance";
  return "memo";
}

const state = {
  center: detectCenterType(), // memo | mail | attendance
  mode: detectInitialMode(), // alert | mail
  search: "",
  selectedId: null,
  selectedItemCache: null,
  checked: new Set(),
  alert: { items: [], folder: "all" },
  mail: {
    items: [],
    trashItems: [],
    folder: "inbox",
    sort: "latest",
    users: [],
    counts: { inbox: 0, unread: 0, sent: 0, trash: 0 },
  },
};

function normalizeRoleFromMe(me) {
  const raw = String(
    me?.position ?? me?.role ?? me?.position_code ?? me?.position_key ?? ""
  )
    .trim()
    .toLowerCase();

  const map = {
    admin: "admin",
    ceo: "ceo",
    manager: "manager",
    leader: "leader",
    "계정": "admin",
    "관리자": "admin",
    "대표": "ceo",
    "대표이사": "ceo",
    "매니저": "manager",
    "팀장": "leader",
  };
  return map[raw] || raw;
}

function buildHeaders() {
  return window.session?.getKey?.().then((key) => (key ? { "X-Sessionid": key } : {}));
}

function classifyAlert(item) {
  const platform = String(item?.platform || "").toLowerCase();
  if (platform === "__attendance_correction__") return "attendance";
  const text = `${item?.content || ""} ${platform}`.toLowerCase();
  if (text.includes("근태") || text.includes("정정요청")) return "attendance";
  return "system";
}

function currentItems() {
  if (state.mode === "alert") {
    let rows = [...state.alert.items];

    if (state.center === "memo") {
      rows = rows.filter((x) => classifyAlert(x) !== "attendance");
    } else if (state.center === "attendance") {
      rows = rows.filter((x) => classifyAlert(x) === "attendance");
    }

    if (state.alert.folder === "unread") rows = rows.filter((x) => !x.is_read);
    if (state.alert.folder === "system") rows = rows.filter((x) => classifyAlert(x) === "system");
    if (state.search) {
      const q = state.search.toLowerCase();
      rows = rows.filter((x) => `${x.content || ""} ${x.date || ""} ${x.user_name || ""}`.toLowerCase().includes(q));
    }
    return rows;
  }

  let mails = state.mail.folder === "trash" ? [...state.mail.trashItems] : [...state.mail.items];
  if (state.mail.folder === "unread") mails = mails.filter((x) => !x.is_read);
  if (state.search) {
    const q = state.search.toLowerCase();
    mails = mails.filter((x) => `${x.subject || ""} ${x.content || ""} ${x.sender_name || ""} ${x.recipient_name || ""}`.toLowerCase().includes(q));
  }
  mails.sort((a, b) => {
    const aTs = new Date(a?.created_at || 0).getTime() || 0;
    const bTs = new Date(b?.created_at || 0).getTime() || 0;
    return state.mail.sort === "oldest" ? aTs - bTs : bTs - aTs;
  });
  return mails;
}

function titleOf(item) {
  if (state.mode === "mail") return (item?.subject || "").trim() || "제목 없음";
  const content = (item?.content || "").trim();
  if (!content) return "메모";
  const lines = content.split("\n");
  const first = (lines[0] || "").trim();
  const m = first.match(/^제목\s*:\s*(.+)$/i);
  if (m) return (m[1] || "").trim() || "메모";
  return first || "메모";
}

function previewOf(item) {
  const raw = (item?.content || "").trim();
  if (!raw) return "";
  const lines = raw.split("\n");
  const first = (lines[0] || "").trim();
  const hasTitlePrefix = /^제목\s*:/i.test(first);
  const body = hasTitlePrefix ? lines.slice(1).join("\n").trim() : raw;
  return body.length > 80 ? `${body.slice(0, 80)}...` : body;
}

function timeLabel(item) {
  const raw = state.mode === "mail" ? item?.created_at : item?.remind_at || item?.updated_at || item?.created_at;
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function mailListTimeHtml(item) {
  const raw = item?.created_at;
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return "-";
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hour24 = d.getHours();
  const minute = String(d.getMinutes()).padStart(2, "0");
  const meridiem = hour24 < 12 ? "오전" : "오후";
  const hour12 = String(((hour24 + 11) % 12) + 1).padStart(2, "0");
  return `
    <span class="date">${month}월 ${day}일</span>
    <span class="time">${meridiem} ${hour12}:${minute}</span>
  `;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatSize(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return "";
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${Math.round(n / 102.4) / 10}KB`;
  return `${Math.round(n / (1024 * 102.4)) / 10}MB`;
}

function attachmentCount(item) {
  return Array.isArray(item?.attachments) ? item.attachments.length : 0;
}

function folderIconSvg(key) {
  const icons = {
    inbox: '<svg class="notify-folder-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 3H4.99C3.89 3 3 3.9 3 5l.01 14c0 1.1.89 2 1.99 2H19c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 12h-4c0 1.1-.9 2-2 2s-2-.9-2-2H7v-2h4c0-1.1.9-2 2-2s2 .9 2 2h4v2z"></path></svg>',
    unread: '<svg class="notify-folder-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"></path></svg>',
    sent: '<svg class="notify-folder-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 21l21-9L2 3v7l15 2-15 2z"></path></svg>',
    trash: '<svg class="notify-folder-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7h12l-1 14H7L6 7zm3-3h6l1 2h4v2H4V6h4l1-2z"></path></svg>',
  };
  return icons[key] || "";
}

function buildMailDetailBody(item) {
  const subject = escapeHtml((item?.subject || "").trim() || "제목 없음");
  const attachments = Array.isArray(item?.attachments) ? item.attachments : [];
  const totalSize = attachments.reduce((acc, att) => acc + Number(att?.size || 0), 0);
  const attachmentListHtml = attachments.length
    ? attachments
        .map(
          (att) => `
            <div class="mail-attach-item">
              <a class="notify-detail-file" href="${att.url}" target="_blank" rel="noopener noreferrer">
                <span class="name">${escapeHtml(att.name || "첨부파일")}</span>
                <span class="size">${formatSize(att.size)}</span>
              </a>
            </div>
          `
        )
        .join("")
    : `<div class="notify-detail-no-attach">첨부 없음</div>`;

  return [
    `<div class="mail-detail-title">${subject}</div>`,
    `<div class="mail-detail-date">${timeLabel(item)}</div>`,
    `<div class="mail-detail-divider"></div>`,
    `<div class="mail-detail-attach-summary">`,
    `<div class="left">첨부 ${attachments.length}개 ${attachments.length ? `<span class="sum-size">${formatSize(totalSize)}</span>` : ""}</div>`,
    `</div>`,
    `<div class="notify-detail-files">${attachmentListHtml}</div>`,
    `<div class="mail-detail-divider"></div>`,
    `<div class="mail-detail-body-block">`,
    `<div class="mail-detail-body-text">${escapeHtml(item?.content || "").replaceAll("\n", "<br>")}</div>`,
    `</div>`,
  ].join("");
}

async function fetchAlerts() {
  const headers = await buildHeaders();
  const params = new URLSearchParams({ limit: "200", center: state.center || "memo" });
  const res = await fetch(`${window.API_BASE}/api/data/notifications/?${params.toString()}`, { credentials: "include", headers });
  if (!res.ok) throw new Error("notification_fetch_failed");
  const data = await res.json();
  state.alert.items = data.results || [];
}

async function fetchMails() {
  const headers = await buildHeaders();
  const box = state.mail.folder === "sent" ? "sent" : "inbox";
  const params = new URLSearchParams({ box, limit: "200" });
  if (state.search) params.set("q", state.search);
  const res = await fetch(`${window.API_BASE}/api/data/messages/?${params.toString()}`, { credentials: "include", headers });
  if (!res.ok) throw new Error("mail_fetch_failed");
  const data = await res.json();
  state.mail.items = data.results || [];
  state.mail.counts = {
    inbox: Number(data.inbox_count || 0),
    unread: Number(data.unread_count || 0),
    sent: Number(data.sent_count || 0),
    trash: Number(state.mail.trashItems.length || 0),
  };
}

async function fetchUsers() {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/api/accounts/users/`, { credentials: "include", headers });
  if (!res.ok) throw new Error("users_fetch_failed");
  const data = await res.json();
  state.mail.users = data.results || [];
}

async function markAlertRead(id) {
  const headers = await buildHeaders();
  try {
    await fetch(`${window.API_BASE}/api/data/calendar-memos/${id}/`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ is_read: true }),
    });
  } catch (e) {
    // ignore read sync errors; UI should still open detail
  }
}

async function markMailRead(id) {
  const headers = await buildHeaders();
  try {
    await fetch(`${window.API_BASE}/api/data/messages/${id}/`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ is_read: true }),
    });
  } catch (e) {
    // ignore read sync errors; UI should still open detail
  }
}

async function markAllInboxRead() {
  if (state.mode !== "mail") return;
  const unread = (state.mail.items || []).filter((x) => !x.is_read);
  if (!unread.length) return;
  for (const item of unread) {
    await markMailRead(item.id);
  }
}

function renderFolders() {
  const root = document.getElementById("notifyFolders");
  if (!root) return;

  if (state.mode === "alert") {
    let all = [...state.alert.items];
    if (state.center === "memo") {
      all = all.filter((x) => classifyAlert(x) !== "attendance");
    } else if (state.center === "attendance") {
      all = all.filter((x) => classifyAlert(x) === "attendance");
    }

    const counts = {
      all: all.length,
      unread: all.filter((x) => !x.is_read).length,
      system: all.filter((x) => classifyAlert(x) === "system").length,
    };

    const folderDefs = state.center === "attendance"
      ? [
          { key: "all", label: "전체" },
          { key: "unread", label: "미읽음" },
        ]
      : [
          { key: "all", label: "전체" },
          { key: "unread", label: "미읽음" },
          { key: "system", label: "일반메모" },
        ];

    root.innerHTML = folderDefs
      .map((f) => `
        <button class="notify-folder-btn ${state.alert.folder === f.key ? "active" : ""}" data-folder="${f.key}" type="button">
          <span>${f.label}</span><span>${counts[f.key] || 0}</span>
        </button>
      `)
      .join("");
  } else {
    const counts = {
      ...(state.mail.counts || { inbox: 0, unread: 0, sent: 0, trash: 0 }),
      trash: Number(state.mail.trashItems.length || 0),
    };
    const inMyDashboard = Boolean(document.getElementById("myMailCenterSection"));
    const folders = [
      { key: "inbox", label: "받은메일" },
      { key: "sent", label: "보낸메일" },
      { key: "trash", label: "휴지통" },
    ];
    if (!inMyDashboard) {
      folders.splice(1, 0, { key: "unread", label: "안읽은메일" });
    }
    root.innerHTML = folders
      .map((f) => `
        <button class="notify-folder-btn ${state.mail.folder === f.key ? "active" : ""}" data-folder="${f.key}" type="button">
          <span class="notify-folder-label">${folderIconSvg(f.key)}<span>${f.label}</span></span><span>${counts[f.key] || 0}</span>
        </button>
      `)
      .join("");
  }

  root.querySelectorAll(".notify-folder-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.dataset.folder || "";
      state.selectedId = null;
      state.selectedItemCache = null;
      state.checked.clear();
      if (state.mode === "alert") state.alert.folder = key;
      else state.mail.folder = key;
      if (state.mode === "mail" && key !== "trash") {
        await fetchMails();
      }
      renderAll();
    });
  });
}

function renderList() {
  const root = document.getElementById("notifyMailList");
  if (!root) return;
  const rows = currentItems();
  if (!rows.length) {
    root.innerHTML = `<div class="muted">표시할 항목이 없습니다.</div>`;
    root.onclick = null;
    root.onchange = null;
    return;
  }
  root.innerHTML = rows
    .map((item) => {
      const isRead = item?.is_read === true || item?.is_read === 1 || item?.is_read === "true";
      const rowStateClass = isRead ? "is-read" : "unread";
      if (state.mode === "mail") {
        const sender = escapeHtml(item.sender_name || "-");
        const title = escapeHtml(titleOf(item));
        const preview = escapeHtml(previewOf(item));
        const attCount = attachmentCount(item);
        const attBadge = attCount ? `<span class="notify-mail-attach">📎 ${attCount}</span>` : "";
        return `
          <div class="notify-mail-row ${rowStateClass}" data-id="${item.id}">
            <input class="notify-check" type="checkbox" data-id="${item.id}" ${state.checked.has(item.id) ? "checked" : ""} />
            <div class="notify-mail-sender">${sender}</div>
            <div class="notify-mail-main">
              <div class="notify-mail-title-line">
                <span class="notify-mail-title">${title}</span>
                ${attBadge}
              </div>
              <div class="notify-mail-preview">${preview}</div>
            </div>
            <div class="notify-mail-time">${mailListTimeHtml(item)}</div>
          </div>
        `;
      }
      return `
        <div class="notify-mail-row ${rowStateClass}" data-id="${item.id}">
          <div class="notify-mail-main">
            <div class="notify-mail-title">${titleOf(item)}</div>
          </div>
          <div class="notify-mail-time">${timeLabel(item)}</div>
        </div>
      `;
    })
    .join("");

  root.onclick = async (e) => {
    const target = e.target;
    if (!target) return;
    if (target.classList?.contains("notify-check")) return;

    const rowEl = target.closest?.(".notify-mail-row");
    if (!rowEl) return;
    const id = Number(rowEl.dataset.id);
    if (!id) return;

    state.selectedId = id;
    const item = rows.find((x) => Number(x.id) === Number(id));
    state.selectedItemCache = item || null;
    if (state.mode === "mail" && item) renderMailDetailItem(item);
    else renderAll();

    if (item && !item.is_read) {
      if (state.mode === "alert") await markAlertRead(id);
      else if (state.mail.folder !== "sent") await markMailRead(id);
      item.is_read = true;
      renderAll();
    }
  };

  root.onchange = (e) => {
    const input = e.target;
    if (!input?.classList?.contains("notify-check")) return;
    const id = Number(input.dataset.id);
    if (!id) return;
    if (input.checked) state.checked.add(id);
    else state.checked.delete(id);
  };
}

function renderDetail() {
  const empty = document.getElementById("notifyDetailEmpty");
  const pane = document.getElementById("notifyDetailPane");
  const titleEl = pane?.querySelector("#notifyDetailTitle");
  const metaEl = pane?.querySelector("#notifyDetailMeta");
  const bodyEl = pane?.querySelector("#notifyDetailBody");
  const readBtn = pane?.querySelector("#notifyDetailMarkReadBtn");
  const openBtn = pane?.querySelector("#notifyDetailOpenCalendarBtn");
  if (!empty || !pane || !titleEl || !metaEl || !bodyEl || !readBtn || !openBtn) return;

  const pool = state.mode === "alert"
    ? state.alert.items
    : (state.mail.folder === "trash" ? state.mail.trashItems : state.mail.items);
  let item = pool.find((x) => Number(x.id) === Number(state.selectedId));
  if (!item && state.mode === "mail" && state.selectedItemCache) {
    const cached = state.selectedItemCache;
    if (Number(cached.id) === Number(state.selectedId)) item = cached;
  }
  if (!item) {
    pane.classList.add("hidden");
    empty.classList.remove("hidden");
    return;
  }

  empty.classList.add("hidden");
  pane.classList.remove("hidden");
  titleEl.textContent = titleOf(item);

  if (state.mode === "mail") {
    const subject = (item.subject || "").trim() || "제목 없음";
    titleEl.textContent = subject;
    metaEl.innerHTML = "";
    bodyEl.innerHTML = buildMailDetailBody(item);
    openBtn.textContent = "보낸함/받은함 보기";
    openBtn.onclick = () => {};
  } else {
    metaEl.innerHTML = `
      <div>분류: ${classifyAlert(item) === "attendance" ? "정정요청" : "시스템"}</div>
      <div>일시: ${timeLabel(item)}</div>
      <div>작성자: ${item.user_name || "-"}</div>
      <div>대상일: ${item.date || "-"}</div>
    `;
    openBtn.textContent = classifyAlert(item) === "attendance" ? "근태 캘린더 열기" : "메모 캘린더 열기";
    openBtn.onclick = () => {
      try {
        sessionStorage.setItem("openMemoId", String(item.id));
        if (item.date) sessionStorage.setItem("openMemoDate", item.date);
      } catch (e) {
        // ignore
      }
      if (window.nav?.go) window.nav.go("calendar_dashboard");
      else window.location.href = "calendar_dashboard.html";
    };
  }

  if (state.mode !== "mail") {
    const raw = String(item.content || "").trim();
    const lines = raw.split("\n");
    const first = (lines[0] || "").trim();
    const hasTitlePrefix = /^제목\s*:/i.test(first);
    const bodyOnly = hasTitlePrefix ? lines.slice(1).join("\n").trim() : raw;
    bodyEl.textContent = bodyOnly || "-";
  }

  readBtn.onclick = async () => {
    if (item.is_read) return;
    if (state.mode === "alert") await markAlertRead(item.id);
    else if (state.mail.folder !== "sent") await markMailRead(item.id);
    item.is_read = true;
    renderAll();
  };
}

function renderMailDetailItem(item) {
  const empty = document.getElementById("notifyDetailEmpty");
  const pane = document.getElementById("notifyDetailPane");
  const titleEl = pane?.querySelector("#notifyDetailTitle");
  const metaEl = pane?.querySelector("#notifyDetailMeta");
  const bodyEl = pane?.querySelector("#notifyDetailBody");
  if (!empty || !pane || !titleEl || !metaEl || !bodyEl || !item) return;

  empty.classList.add("hidden");
  pane.classList.remove("hidden");
  titleEl.textContent = (item.subject || "").trim() || "제목 없음";
  metaEl.innerHTML = "";
  bodyEl.innerHTML = buildMailDetailBody(item);
}

function renderModeUi() {
  const alertBtn = document.getElementById("modeAlertBtn");
  const mailBtn = document.getElementById("modeMailBtn");
  const composeBtn = document.getElementById("notifyComposeBtn");
  const openBtn = document.getElementById("notifyDetailOpenCalendarBtn");
  if (alertBtn) alertBtn.classList.toggle("active", state.mode === "alert");
  if (mailBtn) mailBtn.classList.toggle("active", state.mode === "mail");
  if (composeBtn) composeBtn.classList.toggle("hidden", state.mode !== "mail");
  if (openBtn) openBtn.classList.toggle("hidden", state.mode === "mail");
}

function renderAll() {
  renderModeUi();
  renderFolders();
  renderList();
  renderDetail();
}

function applyPendingOpenFromHeader() {
  let pendingId = "";
  try {
    pendingId = (sessionStorage.getItem("openNotifyId") || "").trim();
    sessionStorage.removeItem("openNotifyId");
    sessionStorage.removeItem("openNotifyType");
    sessionStorage.removeItem("openNotifyDate");
  } catch (e) {
    return;
  }
  if (!pendingId) return;
  const idNum = Number(pendingId);
  if (!Number.isFinite(idNum)) return;
  const rows = currentItems();
  const found = rows.find((x) => Number(x.id) === idNum);
  if (!found) return;
  state.selectedId = idNum;
  state.selectedItemCache = found;
}

function bindComposeModal() {
  const openBtn = document.getElementById("notifyComposeBtn");
  const modal = document.getElementById("mailComposeModal");
  const sendBtn = document.getElementById("mailSendBtn");
  const recipient = document.getElementById("mailRecipientSelect");
  const subject = document.getElementById("mailSubjectInput");
  const content = document.getElementById("mailContentInput");
  const attachmentInput = document.getElementById("mailAttachmentInput");
  const attachmentList = document.getElementById("mailAttachmentList");
  if (!openBtn || !modal || !sendBtn || !recipient || !subject || !content || !attachmentInput || !attachmentList) return;

  let composeFiles = [];
  const fileKey = (f) => `${f.name}|${f.size}|${f.lastModified}`;

  const renderComposeFiles = () => {
    if (!composeFiles.length) {
      attachmentList.innerHTML = `<div class="mail-attachment-empty">첨부 파일 없음</div>`;
      return;
    }
    attachmentList.innerHTML = composeFiles
      .map(
        (f, idx) => `
          <div class="mail-attachment-item">
            <span class="name">${escapeHtml(f.name)}</span>
            <span class="size">${formatSize(f.size)}</span>
            <button type="button" class="mail-attachment-remove" data-index="${idx}">삭제</button>
          </div>
        `
      )
      .join("");
    attachmentList.querySelectorAll(".mail-attachment-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.index);
        if (!Number.isFinite(idx)) return;
        composeFiles.splice(idx, 1);
        renderComposeFiles();
      });
    });
  };

  const close = () => modal.classList.add("hidden");
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) close();
  });

  openBtn.addEventListener("click", async () => {
    modal.classList.remove("hidden");
    composeFiles = [];
    attachmentInput.value = "";
    renderComposeFiles();
    try {
      if (!state.mail.users.length) {
        await fetchUsers();
      }
      recipient.innerHTML = state.mail.users
        .map((u) => `<option value="${u.id}">${u.name}</option>`)
        .join("");
      if (!state.mail.users.length) {
        window.showAlert?.("선택 가능한 사용자가 없습니다.");
      }
    } catch (e) {
      recipient.innerHTML = "";
      window.showAlert?.("사용자 목록을 불러오지 못했습니다. 서버를 확인해 주세요.");
    }
  });

  attachmentInput.addEventListener("change", () => {
    const incoming = Array.from(attachmentInput.files || []);
    const existing = new Set(composeFiles.map(fileKey));
    incoming.forEach((f) => {
      const key = fileKey(f);
      if (!existing.has(key)) {
        composeFiles.push(f);
        existing.add(key);
      }
    });
    if (composeFiles.length > 10) {
      composeFiles = composeFiles.slice(0, 10);
      window.showAlert?.("첨부파일은 최대 10개까지 가능합니다.");
    }
    attachmentInput.value = "";
    renderComposeFiles();
  });

  sendBtn.addEventListener("click", async () => {
    const recipientId = recipient.value;
    const title = (subject.value || "").trim();
    const body = (content.value || "").trim();
    if (!recipientId) return window.showAlert?.("받는 사람을 선택하세요.");
    if (!title) return window.showAlert?.("제목을 입력하세요.");
    if (!body) return window.showAlert?.("본문을 입력하세요.");
    if (composeFiles.length > 10) return window.showAlert?.("첨부파일은 최대 10개까지 가능합니다.");

    const headers = await buildHeaders();
    const form = new FormData();
    form.append("recipient_id", String(Number(recipientId)));
    form.append("subject", title);
    form.append("content", body);
    composeFiles.forEach((f) => form.append("attachments", f));

    const res = await fetch(`${window.API_BASE}/api/data/messages/`, {
      method: "POST",
      credentials: "include",
      headers,
      body: form,
    });
    if (!res.ok) return window.showAlert?.("메일 전송 실패");

    subject.value = "";
    content.value = "";
    composeFiles = [];
    attachmentInput.value = "";
    renderComposeFiles();
    close();
    if (state.mode === "mail") {
      await fetchMails();
      renderAll();
    }
    window.showAlert?.("메일을 보냈습니다.");
  });
}

function bindUi() {
  const search = document.getElementById("notifySearchInput");
  const refresh = document.getElementById("notifyRefreshBtn");
  const bulkRead = document.getElementById("notifyBulkReadBtn");
  const modeAlert = document.getElementById("modeAlertBtn");
  const modeMail = document.getElementById("modeMailBtn");
  const mailDeleteBtn = document.getElementById("mailDeleteBtn");
  const mailSortSelect = document.getElementById("mailSortSelect");

  search?.addEventListener("input", async () => {
    state.search = (search.value || "").trim();
    if (state.mode === "mail") await fetchMails();
    renderList();
    renderDetail();
  });

  refresh?.addEventListener("click", async () => {
    if (state.mode === "mail") await fetchMails();
    else await fetchAlerts();
    renderAll();
  });

  bulkRead?.addEventListener("click", async () => {
    const ids = [...state.checked];
    if (!ids.length) return window.showAlert?.("선택된 항목이 없습니다.");
    for (const id of ids) {
      if (state.mode === "alert") await markAlertRead(id);
      else if (state.mail.folder !== "sent") await markMailRead(id);
      const item = (state.mode === "alert" ? state.alert.items : state.mail.items).find((x) => x.id === id);
      if (item) item.is_read = true;
    }
    state.checked.clear();
    renderAll();
  });

  mailDeleteBtn?.addEventListener("click", () => {
    if (state.mode !== "mail") return;
    const ids = state.checked.size
      ? [...state.checked]
      : state.selectedId
        ? [state.selectedId]
        : [];
    if (!ids.length) {
      window.showAlert?.("삭제할 메일을 선택하세요.");
      return;
    }

    if (state.mail.folder === "trash") {
      state.mail.trashItems = state.mail.trashItems.filter((x) => !ids.includes(Number(x.id)));
    } else {
      const moveTargets = [];
      state.mail.items = state.mail.items.filter((x) => {
        const hit = ids.includes(Number(x.id));
        if (hit) moveTargets.push(x);
        return !hit;
      });

      const existing = new Set(state.mail.trashItems.map((x) => Number(x.id)));
      moveTargets.forEach((x) => {
        if (!existing.has(Number(x.id))) state.mail.trashItems.unshift(x);
      });
    }

    state.checked.clear();
    if (ids.includes(Number(state.selectedId || 0))) {
      state.selectedId = null;
      state.selectedItemCache = null;
    }
    state.mail.counts.trash = state.mail.trashItems.length;
    renderAll();
  });

  mailSortSelect?.addEventListener("change", () => {
    const v = String(mailSortSelect.value || "latest");
    state.mail.sort = v === "oldest" ? "oldest" : "latest";
    renderList();
    renderDetail();
  });

  modeAlert?.addEventListener("click", async () => {
    state.mode = "alert";
    state.selectedId = null;
    state.selectedItemCache = null;
    state.checked.clear();
    await fetchAlerts();
    renderAll();
  });

  modeMail?.addEventListener("click", async () => {
    state.mode = "mail";
    state.selectedId = null;
    state.selectedItemCache = null;
    state.checked.clear();
    state.mail.folder = "inbox";
    await Promise.all([fetchMails(), fetchUsers()]);
    renderAll();
  });

  bindComposeModal();
}

async function ensureAttendanceAccess() {
  if (state.center !== "attendance") return true;
  const contentShell = document.getElementById("attendanceRequestsShell");
  const deniedModal = document.getElementById("attendanceDeniedModal");
  const closeDeniedModal = () => deniedModal?.classList.add("hidden");

  deniedModal?.addEventListener("click", (e) => {
    if (e.target?.classList?.contains("modal-backdrop")) closeDeniedModal();
  });

  try {
    const headers = await buildHeaders();
    const res = await fetch(`${window.API_BASE}/api/data/system-permissions/me/?key=attendance_requests_access`, {
      credentials: "include",
      headers,
    });
    if (res.ok) {
      const data = await res.json();
      if (data?.enabled) {
        contentShell?.classList.remove("hidden");
        deniedModal?.classList.add("hidden");
        return true;
      }
    }
  } catch (e) {
    // ignore
  }
  contentShell?.classList.add("hidden");
  deniedModal?.classList.remove("hidden");
  return false;
}

document.addEventListener("DOMContentLoaded", async () => {
  bindUi();
  try {
    const allowed = await ensureAttendanceAccess();
    if (!allowed) return;

    if (state.mode === "mail") {
      await Promise.all([fetchMails(), fetchUsers()]);
    } else {
      await fetchAlerts();
      if (state.center === "attendance") state.alert.folder = "all";
    }
    applyPendingOpenFromHeader();
    renderAll();
  } catch (e) {
    const root = document.getElementById("notifyMailList");
    if (root) root.innerHTML = `<div class="muted">데이터를 불러오지 못했습니다.</div>`;
  }
});
