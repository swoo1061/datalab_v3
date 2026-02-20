const API_BASE = window?.config?.apiBase || "http://127.0.0.1:8000";
const GLOBAL_NOTICE_STORE_KEY = "global_notice_fallback_v1";
const GLOBAL_NOTICE_READ_KEY = "global_notice_reads_v1";

let currentGlobalNotices = [];
let editingNoticeId = null;
let openNoticeId = null;
let useFallbackStore = false;

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function setGlobalNoticeStatus(text, isError = false) {
  const headerStatusEl = document.getElementById("globalNoticeStatus");
  const modalStatusEl = document.getElementById("globalNoticeModalStatus");
  [headerStatusEl, modalStatusEl].forEach((statusEl) => {
    if (!statusEl) return;
    statusEl.textContent = text || "";
    statusEl.style.color = isError ? "#b42318" : "";
  });
}

function getGlobalNoticeFormValues() {
  const titleEl = document.getElementById("globalNoticeTitle");
  const contentEl = document.getElementById("globalNoticeContent");
  const pinnedEl = document.getElementById("globalNoticePinned");
  return {
    title: String(titleEl?.value || "").trim(),
    content: String(contentEl?.value || "").trim(),
    is_pinned: Boolean(pinnedEl?.checked),
  };
}

function openGlobalNoticeModal(notice = null) {
  const titleEl = document.getElementById("globalNoticeTitle");
  const contentEl = document.getElementById("globalNoticeContent");
  const pinnedEl = document.getElementById("globalNoticePinned");
  const modalTitleEl = document.getElementById("globalNoticeModalTitle");
  const modalEl = document.getElementById("globalNoticeModal");

  editingNoticeId = Number(notice?.id || 0) || null;
  if (titleEl) titleEl.value = notice?.title || "";
  if (contentEl) contentEl.value = notice?.content || "";
  if (pinnedEl) pinnedEl.checked = Boolean(notice?.is_pinned);
  if (modalTitleEl) modalTitleEl.textContent = editingNoticeId ? "공지 수정" : "공지 작성";
  setGlobalNoticeStatus("");
  if (modalEl) modalEl.classList.remove("hidden");
}

function closeGlobalNoticeModal() {
  const modalEl = document.getElementById("globalNoticeModal");
  const titleEl = document.getElementById("globalNoticeTitle");
  const contentEl = document.getElementById("globalNoticeContent");
  const pinnedEl = document.getElementById("globalNoticePinned");

  editingNoticeId = null;
  if (titleEl) titleEl.value = "";
  if (contentEl) contentEl.value = "";
  if (pinnedEl) pinnedEl.checked = false;
  setGlobalNoticeStatus("");
  if (modalEl) modalEl.classList.add("hidden");
}

function getFallbackReadSet() {
  try {
    const parsed = JSON.parse(localStorage.getItem(GLOBAL_NOTICE_READ_KEY) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.map((x) => Number(x)).filter(Boolean) : []);
  } catch (_e) {
    return new Set();
  }
}

function saveFallbackReadSet(readSet) {
  localStorage.setItem(GLOBAL_NOTICE_READ_KEY, JSON.stringify(Array.from(readSet)));
}

function getFallbackNotices() {
  try {
    const parsed = JSON.parse(localStorage.getItem(GLOBAL_NOTICE_STORE_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.sort((a, b) => {
      const pinnedGap = Number(Boolean(b.is_pinned)) - Number(Boolean(a.is_pinned));
      if (pinnedGap !== 0) return pinnedGap;
      return new Date(b.updated_at || b.created_at).valueOf() - new Date(a.updated_at || a.created_at).valueOf();
    });
  } catch (_e) {
    return [];
  }
}

function setFallbackNotices(rows) {
  localStorage.setItem(GLOBAL_NOTICE_STORE_KEY, JSON.stringify(rows || []));
}

function renderGlobalNoticeList() {
  const listEl = document.getElementById("globalNoticeList");
  if (!listEl) return;

  if (!currentGlobalNotices.length) {
    listEl.innerHTML = `
      <div class="clinic-notice-empty">
        <div class="clinic-notice-empty-title">등록된 공지사항이 없습니다.</div>
      </div>
    `;
    return;
  }

  listEl.innerHTML = currentGlobalNotices
    .map((row) => {
      const isOpen = Number(openNoticeId) === Number(row.id);
      const writer = row.writer_name || row.created_by_name || row.updated_by_name || "작성자 미상";
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
              <div class="notice-writer-text">${escapeHtml(writer)}</div>
              <div class="notice-date-text">${fmtDateTimeMinute(row.updated_at || row.created_at)}</div>
            </div>
            <div class="clinic-notice-col notice-icon">${isOpen ? "−" : "+"}</div>
          </button>
          <div class="clinic-notice-detail ${isOpen ? "" : "hidden"}">
            <div class="clinic-notice-detail-body">${escapeHtml(row.content || "").replace(/\n/g, "<br/>") || '<span class="muted">내용 없음</span>'}</div>
            <div class="clinic-notice-detail-foot">
              <span class="clinic-notice-foot-writer">${escapeHtml(writer)}</span>
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

async function markGlobalNoticeRead(noticeId) {
  const target = currentGlobalNotices.find((row) => Number(row.id) === Number(noticeId));
  if (!target || !target.is_new) return;

  if (useFallbackStore) {
    const readSet = getFallbackReadSet();
    readSet.add(Number(noticeId));
    saveFallbackReadSet(readSet);
    target.is_new = false;
    return;
  }

  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/global-notices/${noticeId}/read/`, {
      method: "POST",
      credentials: "include",
      headers,
    });
    if (!res.ok) return;
    target.is_new = false;
  } catch (_e) {
  }
}

async function loadGlobalNotices() {
  const listEl = document.getElementById("globalNoticeList");
  if (!listEl) return;

  try {
    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/global-notices/`, {
      credentials: "include",
      headers,
    });

    if (!res.ok) {
      if (res.status === 404 || res.status === 405) {
        useFallbackStore = true;
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    }

    if (useFallbackStore) {
      const readSet = getFallbackReadSet();
      currentGlobalNotices = getFallbackNotices().map((row) => ({
        ...row,
        is_new: !readSet.has(Number(row.id)),
      }));
      if (!currentGlobalNotices.length) openNoticeId = null;
      renderGlobalNoticeList();
      return;
    }

    const payload = await res.json();
    currentGlobalNotices = Array.isArray(payload?.results) ? payload.results : [];
    if (!currentGlobalNotices.length) openNoticeId = null;
    renderGlobalNoticeList();
  } catch (e) {
    console.error("global notice load failed", e);
    if (listEl) listEl.innerHTML = '<div class="muted">공지사항을 불러오지 못했습니다.</div>';
  }
}

async function saveGlobalNotice() {
  const values = getGlobalNoticeFormValues();
  if (!values.title && !values.content) {
    setGlobalNoticeStatus("제목 또는 내용을 입력하세요.", true);
    return;
  }

  const wasEditing = Boolean(editingNoticeId);

  try {
    setGlobalNoticeStatus(wasEditing ? "공지 수정 중..." : "공지 저장 중...");

    if (useFallbackStore) {
      const rows = getFallbackNotices();
      const now = new Date().toISOString();
      if (wasEditing) {
        const idx = rows.findIndex((x) => Number(x.id) === Number(editingNoticeId));
        if (idx >= 0) {
          rows[idx] = {
            ...rows[idx],
            ...values,
            updated_at: now,
          };
        }
      } else {
        const nextId = rows.length ? Math.max(...rows.map((x) => Number(x.id) || 0)) + 1 : 1;
        rows.push({
          id: nextId,
          ...values,
          writer_name: "관리자",
          created_at: now,
          updated_at: now,
        });
      }
      setFallbackNotices(rows);
      closeGlobalNoticeModal();
      await loadGlobalNotices();
      setGlobalNoticeStatus("저장되었습니다.");
      return;
    }

    const headers = await buildAuthHeaders();
    headers["Content-Type"] = "application/json";

    const url = wasEditing
      ? `${API_BASE}/api/data/global-notices/${editingNoticeId}/`
      : `${API_BASE}/api/data/global-notices/`;
    const method = wasEditing ? "PATCH" : "POST";

    const res = await fetch(url, {
      method,
      credentials: "include",
      headers,
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      if (res.status === 403) {
        await window.showAlert?.("수정 권한이 없습니다. 본인 작성 공지 또는 관리자만 수정할 수 있습니다.");
        setGlobalNoticeStatus("");
        return;
      }
      throw new Error(`HTTP ${res.status}`);
    }

    closeGlobalNoticeModal();
    await loadGlobalNotices();
    setGlobalNoticeStatus("저장되었습니다.");
  } catch (e) {
    console.error("global notice save failed", e);
    await window.showAlert?.("공지 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    setGlobalNoticeStatus("");
  }
}

async function deleteGlobalNotice(noticeId) {
  if (!noticeId) return;

  try {
    setGlobalNoticeStatus("공지 삭제 중...");

    if (useFallbackStore) {
      const rows = getFallbackNotices().filter((row) => Number(row.id) !== Number(noticeId));
      setFallbackNotices(rows);
      if (editingNoticeId && Number(editingNoticeId) === Number(noticeId)) {
        closeGlobalNoticeModal();
      }
      if (Number(openNoticeId) === Number(noticeId)) {
        openNoticeId = null;
      }
      await loadGlobalNotices();
      setGlobalNoticeStatus("삭제되었습니다.");
      return;
    }

    const headers = await buildAuthHeaders();
    const res = await fetch(`${API_BASE}/api/data/global-notices/${noticeId}/`, {
      method: "DELETE",
      credentials: "include",
      headers,
    });
    if (!res.ok) {
      if (res.status === 403) {
        await window.showAlert?.("삭제 권한이 없습니다. 본인 작성 공지 또는 관리자만 삭제할 수 있습니다.");
        setGlobalNoticeStatus("");
        return;
      }
      throw new Error(`HTTP ${res.status}`);
    }

    if (editingNoticeId && Number(editingNoticeId) === Number(noticeId)) {
      closeGlobalNoticeModal();
    }
    if (Number(openNoticeId) === Number(noticeId)) {
      openNoticeId = null;
    }
    await loadGlobalNotices();
    setGlobalNoticeStatus("삭제되었습니다.");
  } catch (e) {
    console.error("global notice delete failed", e);
    await window.showAlert?.("공지 삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    setGlobalNoticeStatus("");
  }
}

function initGlobalNoticesPage() {
  const openBtn = document.getElementById("globalNoticeOpenBtn");
  const saveBtn = document.getElementById("globalNoticeSaveBtn");
  const modalCloseBtn = document.getElementById("globalNoticeModalClose");
  const modalCancelBtn = document.getElementById("globalNoticeModalCancel");
  const modalEl = document.getElementById("globalNoticeModal");
  const listEl = document.getElementById("globalNoticeList");
  if (!openBtn || !saveBtn || !modalCloseBtn || !modalCancelBtn || !modalEl || !listEl) return;

  openBtn.addEventListener("click", () => openGlobalNoticeModal());
  saveBtn.addEventListener("click", () => saveGlobalNotice());
  modalCloseBtn.addEventListener("click", () => closeGlobalNoticeModal());
  modalCancelBtn.addEventListener("click", () => closeGlobalNoticeModal());
  modalEl.addEventListener("click", (event) => {
    if (event.target?.matches?.(".modal-backdrop[data-close='true']")) {
      closeGlobalNoticeModal();
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
      if (willOpen) await markGlobalNoticeRead(id);
      renderGlobalNoticeList();
      return;
    }

    if (editBtn) {
      const id = Number(editBtn.dataset.noticeEdit || 0);
      if (!id) return;
      const found = currentGlobalNotices.find((row) => Number(row.id) === id);
      if (!found) return;
      if (found.can_edit === false) {
        await window.showAlert?.("수정 권한이 없습니다. 본인 작성 공지 또는 관리자만 수정할 수 있습니다.");
        return;
      }
      openGlobalNoticeModal(found);
      return;
    }

    if (deleteBtn) {
      const id = Number(deleteBtn.dataset.noticeDelete || 0);
      if (!id) return;
      const found = currentGlobalNotices.find((row) => Number(row.id) === id);
      if (found && found.can_delete === false) {
        await window.showAlert?.("삭제 권한이 없습니다. 본인 작성 공지 또는 관리자만 삭제할 수 있습니다.");
        return;
      }
      const ok = typeof window.appConfirm === "function"
        ? await window.appConfirm("이 공지사항을 삭제할까요?")
        : window.confirm("이 공지사항을 삭제할까요?");
      if (!ok) return;
      await deleteGlobalNotice(id);
    }
  });

  loadGlobalNotices();
}

window.addEventListener("DOMContentLoaded", initGlobalNoticesPage);
