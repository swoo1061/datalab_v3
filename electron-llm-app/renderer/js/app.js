// js/app.js

async function loadComponent(targetId, url) {
  const root = document.getElementById(targetId);
  if (!root) {
    console.warn(`❗ target not found: ${targetId}`);
    return;
  }

  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} fetch failed`);
  root.innerHTML = await res.text();
}

function setActiveNav(key) {
  document.querySelectorAll(".sidebar .nav a").forEach(a => {
    a.classList.toggle("active", a.dataset.nav === key);
  });
}

function navigate(page) {
  if (window.nav?.go) {
    window.nav.go(page); // Electron
  } else {
    window.location.href = `${page}.html`; // Web
  }
}

async function loadLayout() {
  // header는 header.js에서 처리하므로 여기선 sidebar만
  await loadComponent("appSidebar", "./components/sidebar.html");
}

function goMyDashboard() {
  window.location.href = "my_dashboard.html";
}

window.navigate = navigate;
window.loadLayout = loadLayout;

// Fallback: close known overlays if they get stuck open.
function releaseBlockingLayers() {
  const overlays = [
    ".modal:not(.hidden)",
    ".modal-backdrop:not(.hidden)",
    ".profile-popup:not(.hidden)",
    ".profile-info-modal:not(.hidden)",
    ".notify-dropdown:not(.hidden)",
    ".post-filters-panel:not(.hidden)",
  ];

  overlays.forEach((selector) => {
    document.querySelectorAll(selector).forEach((el) => {
      const style = getComputedStyle(el);
      if (style.position !== "fixed" && style.position !== "absolute") return;

      const rect = el.getBoundingClientRect();
      const covers =
        rect.width >= window.innerWidth - 2 &&
        rect.height >= window.innerHeight - 2;

      if (!covers) return;
      el.classList.add("hidden");
    });
  });
}

// Removed auto-close interval to avoid closing active modals unexpectedly.

// If a drag/resize state gets stuck, clear it when focusing inputs.
function closeStuckOverlays(exceptTarget) {
  const keep = exceptTarget?.closest?.(".modal, .profile-info-modal, .notify-dropdown, .profile-popup");
  if (keep) return;

  document.querySelectorAll(".modal:not(.hidden)").forEach((el) => el.classList.add("hidden"));
  document.querySelectorAll(".profile-popup:not(.hidden)").forEach((el) => el.classList.add("hidden"));
  document.querySelectorAll(".profile-info-modal:not(.hidden)").forEach((el) => el.classList.add("hidden"));
  document.querySelectorAll(".notify-dropdown:not(.hidden)").forEach((el) => el.classList.add("hidden"));
  document.querySelectorAll(".post-filters-panel:not(.hidden)").forEach((el) => el.classList.add("hidden"));
}

// Hide orphaned backdrops that can block all inputs.
function hideOrphanedBackdrops() {
  document
    .querySelectorAll(".modal-backdrop, .photo-preview-backdrop, .review-loading-backdrop")
    .forEach((backdrop) => {
      const modal = backdrop.closest(".modal, .photo-preview-modal");
      const modalVisible =
        modal &&
        !modal.classList.contains("hidden") &&
        getComputedStyle(modal).display !== "none";

      if (modalVisible) return;
      if (modal) modal.classList.add("hidden");
      backdrop.classList.add("hidden");
      backdrop.style.display = "none";
    });
}

document.addEventListener("focusin", (e) => {
  if (!e.target?.closest("input, textarea, select")) return;
  closeStuckOverlays(e.target);
  hideOrphanedBackdrops();
  document.body.classList.remove("drag-scroll-active");
  document.body.classList.remove("resizing-panel");
  document.querySelectorAll(".dragging").forEach((el) => el.classList.remove("dragging"));
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  closeStuckOverlays(null);
});

function clearStuckInteractionState() {
  closeStuckOverlays(null);
  hideOrphanedBackdrops();
  document.body.classList.remove("drag-scroll-active");
  document.body.classList.remove("resizing-panel");
  document.querySelectorAll(".dragging").forEach((el) => el.classList.remove("dragging"));
}

window.addEventListener("blur", clearStuckInteractionState);
window.addEventListener("resize", clearStuckInteractionState);

window.resetInteractionState = clearStuckInteractionState;

function ensureAppConfirmModal() {
  let modal = document.getElementById("appConfirmModal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "appConfirmModal";
  modal.className = "app-confirm hidden";
  modal.innerHTML = `
    <div class="app-confirm-backdrop" data-close="true"></div>
    <div class="app-confirm-card" role="dialog" aria-modal="true">
      <div class="app-confirm-message" id="appConfirmMessage"></div>
      <div class="app-confirm-actions">
        <button class="app-confirm-btn" data-cancel="true">취소</button>
        <button class="app-confirm-btn primary" data-ok="true">확인</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  return modal;
}

window.appConfirm = (message) =>
  new Promise((resolve) => {
    const modal = ensureAppConfirmModal();
    const msg = modal.querySelector("#appConfirmMessage");
    const okBtn = modal.querySelector("[data-ok]");
    const cancelBtn = modal.querySelector("[data-cancel]");
    const backdrop = modal.querySelector("[data-close]");
    const prevActive = document.activeElement;

    if (msg) msg.textContent = message || "확인하시겠습니까?";
    modal.classList.remove("hidden");

    const cleanup = (result) => {
      modal.classList.add("hidden");
      okBtn?.removeEventListener("click", onOk);
      cancelBtn?.removeEventListener("click", onCancel);
      backdrop?.removeEventListener("click", onCancel);
      document.removeEventListener("keydown", onKeydown, true);
      if (prevActive instanceof HTMLElement) {
        prevActive.focus({ preventScroll: true });
      }
      resolve(result);
    };

    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onKeydown = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        cleanup(false);
      }
    };

    okBtn?.addEventListener("click", onOk);
    cancelBtn?.addEventListener("click", onCancel);
    backdrop?.addEventListener("click", onCancel);
    document.addEventListener("keydown", onKeydown, true);
    okBtn?.focus();
  });

function ensureAppAlertModal() {
  let modal = document.getElementById("appAlertModal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "appAlertModal";
  modal.className = "app-confirm hidden";
  modal.innerHTML = `
    <div class="app-confirm-backdrop" data-close="true"></div>
    <div class="app-confirm-card" role="alertdialog" aria-modal="true">
      <div class="app-confirm-message" id="appAlertMessage"></div>
      <div class="app-confirm-actions">
        <button class="app-confirm-btn primary" data-ok="true">확인</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  return modal;
}

window.appAlert = (message) =>
  new Promise((resolve) => {
    const modal = ensureAppAlertModal();
    const msg = modal.querySelector("#appAlertMessage");
    const okBtn = modal.querySelector("[data-ok]");
    const backdrop = modal.querySelector("[data-close]");
    const prevActive = document.activeElement;

    if (msg) msg.textContent = message || "";
    modal.classList.remove("hidden");

    const cleanup = () => {
      modal.classList.add("hidden");
      okBtn?.removeEventListener("click", onOk);
      backdrop?.removeEventListener("click", onOk);
      document.removeEventListener("keydown", onKeydown, true);
      if (prevActive instanceof HTMLElement) {
        prevActive.focus({ preventScroll: true });
      }
      resolve(true);
    };

    const onOk = () => cleanup();
    const onKeydown = (e) => {
      if (e.key === "Escape" || e.key === "Enter") {
        e.stopPropagation();
        cleanup();
      }
    };

    okBtn?.addEventListener("click", onOk);
    backdrop?.addEventListener("click", onOk);
    document.addEventListener("keydown", onKeydown, true);
    okBtn?.focus();
  });

window.showAlert = window.showAlert || ((message) => {
  if (typeof window.appAlert === "function") {
    return window.appAlert(message);
  }
  alert(message);
  return Promise.resolve(true);
});

function hexToRgbString(hex) {
  const cleaned = String(hex || "").trim().replace("#", "");
  if (cleaned.length !== 6) return null;
  const r = Number.parseInt(cleaned.slice(0, 2), 16);
  const g = Number.parseInt(cleaned.slice(2, 4), 16);
  const b = Number.parseInt(cleaned.slice(4, 6), 16);
  if ([r, g, b].some((v) => Number.isNaN(v))) return null;
  return `${r}, ${g}, ${b}`;
}

function getUserStorageKey(suffix) {
  const userKey = localStorage.getItem("currentUserKey");
  if (!userKey) return suffix;
  return `${userKey}:${suffix}`;
}

function readUserStorage(suffix) {
  const userKey = localStorage.getItem("currentUserKey");
  const scopedKey = getUserStorageKey(suffix);
  const scopedValue = localStorage.getItem(scopedKey);
  if (scopedValue !== null) return scopedValue;
  if (userKey) return null;
  return localStorage.getItem(suffix);
}

function writeUserStorage(suffix, value) {
  const scopedKey = getUserStorageKey(suffix);
  localStorage.setItem(scopedKey, value);
}

function removeUserStorage(suffix) {
  const scopedKey = getUserStorageKey(suffix);
  localStorage.removeItem(scopedKey);
}

function migrateUserStorage(suffix) {
  const userKey = localStorage.getItem("currentUserKey");
  if (!userKey) return;
  const scopedKey = getUserStorageKey(suffix);
  if (localStorage.getItem(scopedKey) !== null) return;
  const legacyValue = localStorage.getItem(suffix);
  if (legacyValue === null) return;
  localStorage.setItem(scopedKey, legacyValue);
  localStorage.removeItem(suffix);
}

function applyCustomThemeVars() {
  const root = document.body;
  if (!root) return;
  const primary = readUserStorage("themePrimary") || "#4f46e5";
  const accent = readUserStorage("themeAccent") || "#0e7490";
  const primaryRgb = hexToRgbString(primary) || "79, 70, 229";
  const accentRgb = hexToRgbString(accent) || "14, 116, 144";

  root.style.setProperty("--theme-primary", primary);
  root.style.setProperty("--theme-accent", accent);
  root.style.setProperty("--theme-primary-rgb", primaryRgb);
  root.style.setProperty("--theme-accent-rgb", accentRgb);

  const isNearWhite = (hex) => {
    const cleaned = String(hex || "").trim().replace("#", "");
    if (cleaned.length !== 6) return false;
    const r = Number.parseInt(cleaned.slice(0, 2), 16);
    const g = Number.parseInt(cleaned.slice(2, 4), 16);
    const b = Number.parseInt(cleaned.slice(4, 6), 16);
    if ([r, g, b].some((v) => Number.isNaN(v))) return false;
    return r > 235 && g > 235 && b > 235;
  };

  root.classList.toggle(
    "theme-flat",
    isNearWhite(primary) && isNearWhite(accent)
  );
}

window.setCustomThemeColors = (primary, accent) => {
  if (primary) writeUserStorage("themePrimary", primary);
  if (accent) writeUserStorage("themeAccent", accent);
  applyCustomThemeVars();
};

window.resetCustomThemeColors = () => {
  removeUserStorage("themePrimary");
  removeUserStorage("themeAccent");
  applyCustomThemeVars();
};

applyCustomThemeVars();

window.getUserStorageKey = getUserStorageKey;
window.readUserStorage = readUserStorage;
window.writeUserStorage = writeUserStorage;
window.removeUserStorage = removeUserStorage;
window.migrateUserStorage = migrateUserStorage;
window.applyCustomThemeVars = applyCustomThemeVars;

// If a global key handler is blocking typing, cut it off for text inputs.
document.addEventListener(
  "keydown",
  (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.isContentEditable || target.matches("input, textarea")) {
      e.stopImmediatePropagation();
    }
  },
  true
);

// If a hidden backdrop is still catching clicks, remove it and focus the real target.
document.addEventListener(
  "pointerdown",
  (e) => {
    const target = e.target;
    if (!(target instanceof Element)) return;
    const backdrop = target.closest(
      ".modal-backdrop, .photo-preview-backdrop, .review-loading-backdrop"
    );
    if (!backdrop) return;

    const modal = backdrop.closest(".modal, .photo-preview-modal");
    const modalVisible =
      modal &&
      !modal.classList.contains("hidden") &&
      getComputedStyle(modal).display !== "none";

    if (modalVisible) return;

    hideOrphanedBackdrops();
    closeStuckOverlays(null);

    const candidates = document.elementsFromPoint(e.clientX, e.clientY);
    const focusEl = candidates.find((el) => el.matches?.("input, textarea, select"));
    if (focusEl) {
      e.preventDefault();
      e.stopPropagation();
      focusEl.focus();
    }
  },
  true
);

// Force-focus inputs even if a parent layer intercepts the pointer event.
document.addEventListener(
  "pointerdown",
  (e) => {
    const elements = document.elementsFromPoint(e.clientX, e.clientY);
    const top = elements[0];
    if (top?.closest?.(".modal, .photo-preview-modal")) return;

    const input = elements.find((el) => el.matches?.("input, textarea, select"));
    if (!input) return;
    if (input.disabled) input.disabled = false;
    input.focus({ preventScroll: true });
  },
  true
);
