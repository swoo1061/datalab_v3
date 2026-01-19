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
  const cells = [];
  const total = 42;
  for (let i = 0; i < total; i += 1) {
    const day = i - meta.firstDay + 1;
    const inMonth = day > 0 && day <= meta.daysInMonth;
    const date = inMonth
      ? `${meta.year}-${String(meta.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
      : "";
    cells.push({ day, date, inMonth });
  }
  return cells;
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
}) {
  const calendar = document.getElementById(calendarId);
  const list = document.getElementById(listId);
  if (!calendar || !list) return;

  const grouped = groupByDate(items);
  const cells = buildCalendarCells(yearMonth);
  const labels = ["일", "월", "화", "수", "목", "금", "토"];

  const headerHtml = labels
    .map((l) => `<div class="calendar-head">${l}</div>`)
    .join("");

  const cellHtml = cells
    .map((cell) => {
      if (!cell.inMonth) {
        return `<div class="calendar-cell muted"></div>`;
      }
      const count = grouped.get(cell.date)?.length || 0;
      const clickable = count > 0 ? "clickable" : "";
      return `
        <div class="calendar-cell ${clickable}" data-date="${cell.date}">
          <div class="calendar-day">${cell.day}</div>
          ${count ? `<span class="calendar-count">${count}건</span>` : ""}
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

  const renderList = (filterDate = null) => {
    const filtered = filterDate
      ? items.filter((i) => i.date === filterDate)
      : items;
    if (!filtered.length) {
      list.innerHTML = `<div class="muted">${emptyMessage}</div>`;
      return;
    }
    list.innerHTML = filtered
      .map((item) => {
        const title = item.title || "-";
        const link = item.url
          ? `<a href="${item.url}" target="_blank" rel="noreferrer">${title}</a>`
          : title;
        const clinicLink = item.clinicId
          ? `<a href="clinic_page.html?clinic_id=${item.clinicId}" class="schedule-link">병원 페이지</a>`
          : "";
        const account = item.account
          ? `<span>아이디: ${item.account}</span>`
          : "";
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
        return `
          <div class="schedule-item">
            <div class="schedule-title">${link}</div>
            <div class="schedule-meta">
              <span>${item.date || "-"}</span>
              ${item.clinic ? `<span class="schedule-badge">${item.clinic}</span>` : ""}
              ${item.platform ? `<span>${item.platform}</span>` : ""}
              ${item.status ? `<span>${item.status}</span>` : ""}
              ${item.assignee ? `<span>${item.assignee}</span>` : ""}
              ${account}
              ${views}
              ${comments}
              ${messages}
              ${item.memo ? `<span class="schedule-memo">${item.memo}</span>` : ""}
              ${clinicLink}
            </div>
            ${item.photos?.length ? `
              <div class="schedule-photos">
                ${item.photos.slice(0, 4).map((url) => `<img src="${url}" alt="photo" />`).join("")}
              </div>
            ` : ""}
            ${messageInput ? `<div class="schedule-edit">쪽지 ${messageInput}</div>` : ""}
          </div>
        `;
      })
      .join("");

    bindMessageInputs(list);
  };

  renderList();

  calendar.querySelectorAll(".calendar-cell.clickable").forEach((cell) => {
    cell.addEventListener("click", () => {
      const targetDate = cell.dataset.date;
      renderList(targetDate);
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

async function updateMessageCount(clinicId, postId, messageCount) {
  const url = `http://127.0.0.1:8000/api/data/clinics/${clinicId}/posts/${postId}/`;
  try {
    await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_count: messageCount }),
    });
  } catch (e) {
    console.error("calendar message update failed", e);
  }
}
