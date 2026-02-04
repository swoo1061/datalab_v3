window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";
window.globalSearchIndex = window.globalSearchIndex || {
  pages: [
    { key: "알림", page: "notifications_center" },
    { key: "대시보드", page: "my_dashboard" },
    { key: "캘린더", page: "calendar_dashboard" },
  ],
};

const state = {
  mode: "alert", // alert | mail
  search: "",
  selectedId: null,
  checked: new Set(),
  alert: { items: [], folder: "all" },
  mail: { items: [], folder: "inbox", users: [], counts: { inbox: 0, unread: 0, sent: 0 } },
};

function buildHeaders() {
  return window.session?.getKey?.().then((key) => (key ? { "X-Sessionid": key } : {}));
}

function classifyAlert(item) {
  const text = `${item?.content || ""} ${item?.platform || ""}`.toLowerCase();
  if (text.includes("근태") || text.includes("정정요청")) return "attendance";
  return "system";
}

function currentItems() {
  if (state.mode === "alert") {
    let rows = [...state.alert.items];
    if (state.alert.folder === "unread") rows = rows.filter((x) => !x.is_read);
    if (state.alert.folder === "attendance") rows = rows.filter((x) => classifyAlert(x) === "attendance");
    if (state.alert.folder === "system") rows = rows.filter((x) => classifyAlert(x) === "system");
    if (state.search) {
      const q = state.search.toLowerCase();
      rows = rows.filter((x) => `${x.content || ""} ${x.date || ""} ${x.user_name || ""}`.toLowerCase().includes(q));
    }
    return rows;
  }

  let mails = [...state.mail.items];
  if (state.mail.folder === "unread") mails = mails.filter((x) => !x.is_read);
  if (state.search) {
    const q = state.search.toLowerCase();
    mails = mails.filter((x) => `${x.subject || ""} ${x.content || ""} ${x.sender_name || ""} ${x.recipient_name || ""}`.toLowerCase().includes(q));
  }
  return mails;
}

function titleOf(item) {
  if (state.mode === "mail") return (item?.subject || "").trim() || "제목 없음";
  const content = (item?.content || "").trim();
  if (!content) return "알림";
  const first = content.split("\n")[0].trim();
  return first || "알림";
}

function previewOf(item) {
  const raw = (item?.content || "").trim();
  return raw.length > 80 ? `${raw.slice(0, 80)}...` : raw;
}

function timeLabel(item) {
  const raw = state.mode === "mail" ? item?.created_at : item?.remind_at || item?.updated_at || item?.created_at;
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.valueOf())) return "-";
  return d.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function fetchAlerts() {
  const headers = await buildHeaders();
  const res = await fetch(`${window.API_BASE}/api/data/notifications/?limit=200`, { credentials: "include", headers });
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
  await fetch(`${window.API_BASE}/api/data/calendar-memos/${id}/`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ is_read: true }),
  });
}

async function markMailRead(id) {
  const headers = await buildHeaders();
  await fetch(`${window.API_BASE}/api/data/messages/${id}/`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ is_read: true }),
  });
}

function renderFolders() {
  const root = document.getElementById("notifyFolders");
  if (!root) return;

  if (state.mode === "alert") {
    const all = state.alert.items;
    const counts = {
      all: all.length,
      unread: all.filter((x) => !x.is_read).length,
      attendance: all.filter((x) => classifyAlert(x) === "attendance").length,
      system: all.filter((x) => classifyAlert(x) === "system").length,
    };
    root.innerHTML = [
      { key: "all", label: "전체" },
      { key: "unread", label: "미읽음" },
      { key: "attendance", label: "정정요청" },
      { key: "system", label: "시스템" },
    ]
      .map((f) => `
        <button class="notify-folder-btn ${state.alert.folder === f.key ? "active" : ""}" data-folder="${f.key}" type="button">
          <span>${f.label}</span><span>${counts[f.key] || 0}</span>
        </button>
      `)
      .join("");
  } else {
    const counts = state.mail.counts || { inbox: 0, unread: 0, sent: 0 };
    root.innerHTML = [
      { key: "inbox", label: "받은메일" },
      { key: "unread", label: "안읽은메일" },
      { key: "sent", label: "보낸메일" },
    ]
      .map((f) => `
        <button class="notify-folder-btn ${state.mail.folder === f.key ? "active" : ""}" data-folder="${f.key}" type="button">
          <span>${f.label}</span><span>${counts[f.key] || 0}</span>
        </button>
      `)
      .join("");
  }

  root.querySelectorAll(".notify-folder-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.dataset.folder || "";
      state.selectedId = null;
      state.checked.clear();
      if (state.mode === "alert") state.alert.folder = key;
      else state.mail.folder = key;
      if (state.mode === "mail") {
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
    return;
  }
  root.innerHTML = rows
    .map((item) => `
      <div class="notify-mail-row ${item.is_read ? "" : "unread"}" data-id="${item.id}">
        <input class="notify-check" type="checkbox" data-id="${item.id}" ${state.checked.has(item.id) ? "checked" : ""} />
        <div class="notify-mail-main">
          <div class="notify-mail-title">${titleOf(item)}</div>
          <div class="notify-mail-preview">${previewOf(item)}</div>
        </div>
        <div class="notify-mail-time">${timeLabel(item)}</div>
      </div>
    `)
    .join("");

  root.querySelectorAll(".notify-mail-row").forEach((rowEl) => {
    rowEl.addEventListener("click", async (e) => {
      const id = Number(rowEl.dataset.id);
      if (!id) return;
      if (e.target?.classList?.contains("notify-check")) return;
      state.selectedId = id;
      const item = rows.find((x) => x.id === id);
      if (item && !item.is_read) {
        if (state.mode === "alert") await markAlertRead(id);
        else if (state.mail.folder !== "sent") await markMailRead(id);
        item.is_read = true;
      }
      renderAll();
    });
  });

  root.querySelectorAll(".notify-check").forEach((input) => {
    input.addEventListener("click", (e) => e.stopPropagation());
    input.addEventListener("change", () => {
      const id = Number(input.dataset.id);
      if (!id) return;
      if (input.checked) state.checked.add(id);
      else state.checked.delete(id);
    });
  });
}

function renderDetail() {
  const empty = document.getElementById("notifyDetailEmpty");
  const pane = document.getElementById("notifyDetailPane");
  const titleEl = document.getElementById("notifyDetailTitle");
  const metaEl = document.getElementById("notifyDetailMeta");
  const bodyEl = document.getElementById("notifyDetailBody");
  const readBtn = document.getElementById("notifyDetailMarkReadBtn");
  const openBtn = document.getElementById("notifyDetailOpenCalendarBtn");
  if (!empty || !pane || !titleEl || !metaEl || !bodyEl || !readBtn || !openBtn) return;

  const pool = state.mode === "alert" ? state.alert.items : state.mail.items;
  const item = pool.find((x) => x.id === state.selectedId);
  if (!item) {
    pane.classList.add("hidden");
    empty.classList.remove("hidden");
    return;
  }

  empty.classList.add("hidden");
  pane.classList.remove("hidden");
  titleEl.textContent = titleOf(item);

  if (state.mode === "mail") {
    metaEl.innerHTML = `
      <div>보낸사람: ${item.sender_name || "-"}</div>
      <div>받는사람: ${item.recipient_name || "-"}</div>
      <div>일시: ${timeLabel(item)}</div>
    `;
    openBtn.textContent = "보낸함/받은함 보기";
    openBtn.onclick = () => {};
  } else {
    metaEl.innerHTML = `
      <div>분류: ${classifyAlert(item) === "attendance" ? "정정요청" : "시스템"}</div>
      <div>일시: ${timeLabel(item)}</div>
      <div>작성자: ${item.user_name || "-"}</div>
      <div>대상일: ${item.date || "-"}</div>
    `;
    openBtn.textContent = "캘린더 열기";
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

  bodyEl.textContent = item.content || "";

  readBtn.onclick = async () => {
    if (item.is_read) return;
    if (state.mode === "alert") await markAlertRead(item.id);
    else if (state.mail.folder !== "sent") await markMailRead(item.id);
    item.is_read = true;
    renderAll();
  };
}

function renderModeUi() {
  const alertBtn = document.getElementById("modeAlertBtn");
  const mailBtn = document.getElementById("modeMailBtn");
  const composeBtn = document.getElementById("notifyComposeBtn");
  const openBtn = document.getElementById("notifyDetailOpenCalendarBtn");
  if (alertBtn) alertBtn.classList.toggle("active", state.mode === "alert");
  if (mailBtn) mailBtn.classList.toggle("active", state.mode === "mail");
  if (composeBtn) composeBtn.classList.remove("hidden");
  if (openBtn) openBtn.classList.toggle("hidden", state.mode === "mail");
}

function renderAll() {
  renderModeUi();
  renderFolders();
  renderList();
  renderDetail();
}

function bindComposeModal() {
  const openBtn = document.getElementById("notifyComposeBtn");
  const modal = document.getElementById("mailComposeModal");
  const sendBtn = document.getElementById("mailSendBtn");
  const recipient = document.getElementById("mailRecipientSelect");
  const subject = document.getElementById("mailSubjectInput");
  const content = document.getElementById("mailContentInput");
  if (!openBtn || !modal || !sendBtn || !recipient || !subject || !content) return;

  const close = () => modal.classList.add("hidden");
  modal.addEventListener("click", (e) => {
    if (e.target?.dataset?.close) close();
  });

  openBtn.addEventListener("click", async () => {
    modal.classList.remove("hidden");
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

  sendBtn.addEventListener("click", async () => {
    const recipientId = recipient.value;
    const title = (subject.value || "").trim();
    const body = (content.value || "").trim();
    if (!recipientId) return window.showAlert?.("받는 사람을 선택하세요.");
    if (!title) return window.showAlert?.("제목을 입력하세요.");
    if (!body) return window.showAlert?.("본문을 입력하세요.");

    const headers = await buildHeaders();
    const res = await fetch(`${window.API_BASE}/api/data/messages/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        recipient_id: Number(recipientId),
        subject: title,
        content: body,
      }),
    });
    if (!res.ok) return window.showAlert?.("메일 전송 실패");

    subject.value = "";
    content.value = "";
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

  modeAlert?.addEventListener("click", async () => {
    state.mode = "alert";
    state.selectedId = null;
    state.checked.clear();
    await fetchAlerts();
    renderAll();
  });

  modeMail?.addEventListener("click", async () => {
    state.mode = "mail";
    state.selectedId = null;
    state.checked.clear();
    state.mail.folder = "inbox";
    await Promise.all([fetchMails(), fetchUsers()]);
    renderAll();
  });

  bindComposeModal();
}

document.addEventListener("DOMContentLoaded", async () => {
  bindUi();
  try {
    await fetchAlerts();
    renderAll();
  } catch (e) {
    const root = document.getElementById("notifyMailList");
    if (root) root.innerHTML = `<div class="muted">데이터를 불러오지 못했습니다.</div>`;
  }
});
