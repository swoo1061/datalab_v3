window.API_BASE = window.API_BASE || window?.config?.apiBase || "http://127.0.0.1:8000";

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

function getMonthMeta(yearMonth) {
  const [y, m] = yearMonth.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const last = new Date(y, m, 0);
  return {
    year: y,
    month: m,
    firstDay: first.getDay(),
    daysInMonth: last.getDate(),
  };
}

function buildCalendarCells(yearMonth) {
  const meta = getMonthMeta(yearMonth);
  const weeks = [];
  let week = new Array(5).fill(null);

  for (let day = 1; day <= meta.daysInMonth; day += 1) {
    const dateObj = new Date(meta.year, meta.month - 1, day);
    const dayOfWeek = dateObj.getDay(); // 0=Sun, 1=Mon, ... 6=Sat
    if (dayOfWeek === 0 || dayOfWeek === 6) continue;

    if (dayOfWeek === 1 && week.some(Boolean)) {
      weeks.push(week);
      week = new Array(5).fill(null);
    }

    const date = `${meta.year}-${String(meta.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    week[dayOfWeek - 1] = { day, date, inMonth: true };
  }

  if (week.some(Boolean)) {
    weeks.push(week);
  }

  return weeks.flat().map((cell) => cell || { day: "", date: "", inMonth: false });
}

function groupByDate(items) {
  const map = new Map();
  items.forEach((item) => {
    if (!item.date) return;
    if (!map.has(item.date)) map.set(item.date, []);
    map.get(item.date).push(item);
  });
  return map;
}

function renderScheduleCalendar({
  calendarId,
  listId,
  items,
  yearMonth,
  emptyMessage = "표시할 일정이 없습니다.",
  allowEmptyClick = false,
  onDateSelect = null,
}) {
  const calendar = document.getElementById(calendarId);
  const list = document.getElementById(listId);
  if (!calendar || !list) return;

  const grouped = groupByDate(items);
  const cells = buildCalendarCells(yearMonth);
  const labels = ["월", "화", "수", "목", "금"];

  const cleanAssignee = (value) =>
    String(value || "")
      .replace(/\s*(매니저|팀장|대표이사|대표)\s*$/g, "")
      .trim();

  const getReviewSubtypeLabel = (item) => {
    if (!item) return "";
    if (item.review_subtype === "photo") return "사진";
    if (item.review_subtype === "text") return "텍스트";
    if (item.review_subtype === "consultation") return "상담";
    const titleHint = String(item.title || item.title_display || "").toLowerCase();
    if (titleHint.includes("상담")) return "상담";
    return Array.isArray(item.photos) && item.photos.length ? "사진" : "텍스트";
  };

  const getOpinionSubtypeLabel = (item) => {
    if (!item) return "고민";
    if (item.opinion_subtype === "hand") return "손품";
    if (item.opinion_subtype === "foot") return "발품";
    return "고민";
  };

  const getTypeDisplay = (item) => {
    if (!item) return "";
    if (item.type === "review") return `후기/${getReviewSubtypeLabel(item)}`;
    if (item.type === "opinion") return `여론/${getOpinionSubtypeLabel(item)}`;
    return "";
  };

  const assigneesByDate = new Map();
  const countsByDate = new Map();
  items.forEach((item) => {
    if (!item.date) return;
    if (item.kind === "memo") return;
    const name = cleanAssignee(item.assignee);
    if (!name) return;
    const typeLabel = getTypeDisplay(item);
    const label = typeLabel ? `${name} ${typeLabel}` : name;
    if (!assigneesByDate.has(item.date)) assigneesByDate.set(item.date, []);
    assigneesByDate.get(item.date).push(label);
    countsByDate.set(item.date, (countsByDate.get(item.date) || 0) + 1);
  });

  const headerHtml = labels
    .map((l) => `<div class="calendar-head">${l}</div>`)
    .join("");

  const cellHtml = cells
    .map((cell) => {
      if (!cell.inMonth) {
        return `<div class="calendar-cell muted"></div>`;
      }
      const count = grouped.get(cell.date)?.length || 0;
      const assignees = assigneesByDate.get(cell.date);
      const assigneeList = assignees ? [...assignees] : [];
      const maxNames = 5;
      const displayed = assigneeList.slice(0, maxNames);
      const totalCount = countsByDate.get(cell.date) || assigneeList.length;
      const extraCount = Math.max(totalCount - maxNames, 0);
      const assigneeLabel = assigneeList.length
        ? `${displayed.join("<br>")}${extraCount ? `<br>+${extraCount}` : ""}`
        : "";
      const clickable = (allowEmptyClick || count > 0) ? "clickable" : "";
      return `
        <div class="calendar-cell ${clickable}" data-date="${cell.date}">
          <div class="calendar-day">${cell.day}</div>
          ${count ? `<span class="calendar-count">${count}건</span>` : ""}
          ${assigneeLabel ? `<div class="calendar-assignees" title="${assigneeList.join(" · ")}">${assigneeLabel}</div>` : ""}
        </div>
      `;
    })
    .join("");

  calendar.innerHTML = `
    <div class="calendar-grid">
      ${headerHtml}
      ${cellHtml}
    </div>
  `;

  const renderCompactItem = (item) => {
    if (item.kind === "memo") {
      return `
        <div class="schedule-item compact">
          <div class="schedule-top">
            <div class="schedule-title">메모</div>
          </div>
          <div class="schedule-meta-grid">
            <div class="meta-cell">
              <span class="meta-label">날짜</span>
              <span class="meta-value">${item.date || "-"}</span>
            </div>
            <div class="meta-cell">
              <span class="meta-label">클리닉</span>
              <span class="meta-value">${item.clinic || "전체"}</span>
            </div>
            ${item.remind_at ? `
              <div class="meta-cell">
                <span class="meta-label">알림</span>
                <span class="meta-value">${item.remind_at}</span>
              </div>
            ` : ""}
          </div>
          ${item.memo ? `<div class="schedule-memo">${item.memo}</div>` : ""}
        </div>
      `;
    }

    const title = item.title_display || item.title || "-";
    const link = item.url
      ? `<a href="${item.url}" target="_blank" rel="noreferrer">${title}</a>`
      : title;
    const platformLabel = item.platform_label || item.platform;
    const reviewSubtypeLabel = item.review_subtype === "photo"
      ? "사진"
      : item.review_subtype === "text"
        ? "텍스트"
        : item.review_subtype === "consultation"
          ? "상담"
          : "";
    const opinionSubtypeLabel = item.opinion_subtype === "concern"
      ? "고민"
      : item.opinion_subtype === "hand"
        ? "손품"
        : item.opinion_subtype === "foot"
          ? "발품"
          : "고민";
    const typeLabel = item.type === "review" ? "후기" : item.type === "opinion" ? "여론" : "";
    const titleHint = String(item.title || item.title_display || "").toLowerCase();
    const fallbackReviewSubtype = item.type === "review" && !item.review_subtype
      ? (titleHint.includes("상담") ? "상담"
        : (Array.isArray(item.photos) && item.photos.length ? "사진" : "텍스트"))
      : "";
    const subtypeLabel = item.type === "review"
      ? (reviewSubtypeLabel || fallbackReviewSubtype)
      : item.type === "opinion"
        ? opinionSubtypeLabel
        : "";
    const typeDisplay = typeLabel ? (subtypeLabel ? `${typeLabel}/${subtypeLabel}` : typeLabel) : "";
    let reviewLabel = typeLabel
      ? (subtypeLabel ? `${typeLabel}/${subtypeLabel}` : typeLabel)
      : "";
    if (!reviewLabel && item.title_display?.startsWith("[")) {
      const match = item.title_display.match(/^\[([^\]]+)\]/);
      if (match?.[1]) reviewLabel = match[1];
    }
    const views = Number.isFinite(item.views)
      ? `<span class="metric-chip">조회 ${item.views}</span>`
      : "";
    const comments = Number.isFinite(item.comments)
      ? `<span class="metric-chip">댓글수 ${item.comments}</span>`
      : "";
    const messages = Number.isFinite(item.message_count)
      ? `
        <button
          type="button"
          class="metric-chip schedule-message-work-btn"
          data-url="${item.url || ""}"
        >
          쪽지 ${item.message_count}
        </button>
      `
      : "";
    const commentCount = Number.isFinite(Number(item.comment_work_count)) ? Number(item.comment_work_count) : 0;
    const actions = `
      <div class="schedule-actions">
        <button
          type="button"
          class="metric-chip schedule-comment-work-btn"
          data-url="${item.url || ""}"
        >
          댓글건수 ${commentCount}
        </button>
      </div>
    `;
    const doctorValue = item.doctor_name || item.doctor || item.doctor_label || "-";
    const metaCells = [
      { label: "날짜", value: item.date || "-" },
      { label: "클리닉", value: item.clinic || "" },
      { label: "원장님", value: doctorValue },
      { label: "ID", value: item.account || "" },
      { label: "구분", value: reviewLabel },
      { label: "플랫폼", value: platformLabel || "" },
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
    const metrics = [views, comments, messages].filter(Boolean).join("");

    return `
      <div class="schedule-item compact">
        <div class="schedule-top">
          <div class="schedule-title">${link}</div>
          ${actions}
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
  };

  const renderDefaultItem = (item) => {
    const title = item.title_display || item.title || "-";
    const link = item.url
      ? `<a href="${item.url}" target="_blank" rel="noreferrer">${title}</a>`
      : title;
    const account = item.account
      ? `<span>카페 ID: ${item.account}</span>`
      : "";
    const accountPassword = item.account_password
      ? `<span>PW: ${item.account_password}</span>`
      : "";
    const platformLabel = item.platform_label || item.platform;
    const reviewSubtypeLabel = item.review_subtype === "photo"
      ? "사진"
      : item.review_subtype === "text"
        ? "텍스트"
        : item.review_subtype === "consultation"
          ? "상담"
          : "";
    const opinionSubtypeLabel = item.opinion_subtype === "concern"
      ? "고민"
      : item.opinion_subtype === "hand"
        ? "손품"
        : item.opinion_subtype === "foot"
          ? "발품"
          : "고민";
    const typeLabel = item.type === "review" ? "후기" : item.type === "opinion" ? "여론" : "";
    const titleHint = String(item.title || item.title_display || "").toLowerCase();
    const fallbackReviewSubtype = item.type === "review" && !item.review_subtype
      ? (titleHint.includes("상담") ? "상담"
        : (Array.isArray(item.photos) && item.photos.length ? "사진" : "텍스트"))
      : "";
    const subtypeLabel = item.type === "review"
      ? (reviewSubtypeLabel || fallbackReviewSubtype)
      : item.type === "opinion"
        ? opinionSubtypeLabel
        : "";
    const typeDisplay = typeLabel ? (subtypeLabel ? `${typeLabel}/${subtypeLabel}` : typeLabel) : "";
    const views = Number.isFinite(item.views)
      ? `<span>조회 ${item.views}</span>`
      : "";
    const comments = Number.isFinite(item.comments)
      ? `<span>댓글 ${item.comments}</span>`
      : "";
    const messages = Number.isFinite(item.message_count)
      ? `<span>쪽지 ${item.message_count}</span>`
      : "";
    const messageInput = item.post_id && item.clinicId
      ? `<input class="message-input" type="number" min="0" value="${item.message_count ?? 0}" data-post-id="${item.post_id}" data-clinic-id="${item.clinicId}" />`
      : "";
    const editButton = item.post_id && item.clinicId
      ? `<button class="schedule-edit" data-post-id="${item.post_id}" data-clinic-id="${item.clinicId}">수정하기</button>`
      : "";

    return `
      <div class="schedule-item">
        <div class="schedule-title">${link}</div>
        <div class="schedule-meta">
          <span>${item.date || "-"}</span>
          ${item.clinic ? `<span class="schedule-badge">${item.clinic}</span>` : ""}
          ${platformLabel ? `<span>${platformLabel}</span>` : ""}
          ${typeDisplay ? `<span>${typeDisplay}</span>` : ""}
          ${item.assignee ? `<span>${item.assignee}</span>` : ""}
          ${account}
          ${accountPassword}
          ${views}
          ${comments}
          ${messages}
          ${item.memo ? `<span class="schedule-memo">${item.memo}</span>` : ""}
          ${editButton}
        </div>
        ${item.photos?.length ? `
          <div class="schedule-photos">
            ${item.photos.slice(0, 4).map((url) => `<img src="${url}" alt="photo" />`).join("")}
          </div>
        ` : ""}
        ${messageInput ? `<div class="schedule-edit">쪽지 ${messageInput}</div>` : ""}
      </div>
    `;
  };

  const renderList = (filterDate = null) => {
    const filtered = filterDate
      ? items.filter((i) => i.date === filterDate)
      : items;
    if (!filtered.length) {
      list.innerHTML = `<div class="muted">${emptyMessage}</div>`;
      return;
    }
    const isCompact = list.dataset.variant === "compact";
    list.innerHTML = filtered
      .map((item) => (isCompact ? renderCompactItem(item) : renderDefaultItem(item)))
      .join("");

    bindMessageInputs(list);
    bindEditButtons(list);
    bindCommentWorkButtons(list);
    bindMessageWorkButtons(list);
    bindPhotoPreviews(list);
  };

  const activeDate = list.dataset.activeDate || null;
  renderList(activeDate);

  const openDetailPanel = () => {
    const panelId = list.dataset.panel;
    if (!panelId) return;
    const panel = document.getElementById(panelId);
    if (panel) panel.classList.add("open");
  };

  calendar.querySelectorAll(".calendar-cell.clickable").forEach((cell) => {
    cell.addEventListener("click", () => {
      const targetDate = cell.dataset.date;
      list.dataset.activeDate = targetDate;
      renderList(targetDate);
      openDetailPanel();
      if (typeof onDateSelect === "function") {
        onDateSelect(targetDate);
      }
    });
  });
}

function bindMessageInputs(listEl) {
  const inputs = listEl.querySelectorAll(".message-input");
  if (!inputs.length) return;

  inputs.forEach((input) => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        input.blur();
      }
    });
    input.addEventListener("blur", async () => {
      const postId = input.dataset.postId;
      const clinicId = input.dataset.clinicId;
      const value = Number(input.value || 0);
      if (!postId || !clinicId) return;
      await updateMessageCount(clinicId, postId, value);
    });
  });
}

function bindEditButtons(listEl) {
  const buttons = listEl.querySelectorAll(".schedule-edit");
  if (!buttons.length) return;

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const postId = btn.dataset.postId;
      const clinicId = btn.dataset.clinicId;
      if (!postId || !clinicId) return;
      if (typeof window.openPostEditor === "function") {
        window.openPostEditor({ postId, clinicId });
      }
    });
  });
}

function bindCommentWorkButtons(listEl) {
  const buttons = listEl.querySelectorAll(".schedule-comment-work-btn");
  if (!buttons.length) return;

  buttons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const now = Date.now();
      const prev = Number(btn.dataset.lastClickTs || 0);
      if (now - prev < 300) return;
      btn.dataset.lastClickTs = String(now);
      const url = String(btn.dataset.url || "").trim();
      if (!url) return;
      if (typeof window.openCommentBundleModalByUrl === "function") {
        window.openCommentBundleModalByUrl(url);
      }
    });
  });
}

function bindMessageWorkButtons(listEl) {
  const buttons = listEl.querySelectorAll(".schedule-message-work-btn");
  if (!buttons.length) return;

  buttons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const now = Date.now();
      const prev = Number(btn.dataset.lastClickTs || 0);
      if (now - prev < 300) return;
      btn.dataset.lastClickTs = String(now);
      const url = String(btn.dataset.url || "").trim();
      if (!url) return;
      if (typeof window.openMessageLogModalByUrl === "function") {
        window.openMessageLogModalByUrl(url);
      }
    });
  });
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

async function updateMessageCount(clinicId, postId, messageCount) {
  const url = `${window.API_BASE}/api/data/clinics/${clinicId}/posts/${postId}/`;
  try {
    const headers = await buildAuthHeaders();
    await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ message_count: messageCount }),
    });
  } catch (e) {
    console.error("calendar message update failed", e);
  }
}
