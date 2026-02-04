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
  if (document.querySelector(".modal.modal-lock:not(.hidden)")) return;
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

const GLASS_SELECT_VERSION = "5";
const GLASS_CLINIC_SELECT_IDS = [
  "postClinicSelect",
  "postSortSelect",
  "calendarClinicSelect",
  "calendarMemoClinicSelect",
  "clinicSelect",
  "myMemoClinicSelect",
  "detailClinicSelect",
  "hospitalSelect",
];

function buildGlassSelectOption(opt, select, menu, labelEl) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "glass-select-option";
  btn.textContent = opt.textContent;
  btn.dataset.value = opt.value;
  btn.disabled = opt.disabled;
  if (opt.selected) btn.classList.add("active");

  btn.addEventListener("click", () => {
    if (opt.disabled) return;
    select.value = opt.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    labelEl.textContent = opt.textContent;
    menu.querySelectorAll(".glass-select-option").forEach((el) => el.classList.remove("active"));
    btn.classList.add("active");
    select.closest(".glass-select")?.classList.remove("open");
  });

  return btn;
}

function syncGlassSelect(select, menu, labelEl) {
  menu.innerHTML = "";
  const options = Array.from(select.options || []);
  options.forEach((opt) => menu.appendChild(buildGlassSelectOption(opt, select, menu, labelEl)));

  const selected = select.options?.[select.selectedIndex];
  labelEl.textContent = selected?.textContent || "선택";
}

function enhanceGlassSelect(select) {
  if (!select || select.dataset.glassEnhanced === "true") return;
  if (select.closest(".glass-select")) return;

  const wrapper = document.createElement("div");
  wrapper.className = "glass-select";

  if (select.classList.contains("inline-select")) {
    wrapper.classList.add("is-inline");
    wrapper.classList.add("glass-block");
  }

  const parent = select.parentElement;
  if (!parent) return;

  parent.insertBefore(wrapper, select);
  wrapper.appendChild(select);

  select.classList.add("glass-native");
  select.dataset.glassEnhanced = "true";
  select.dataset.glassVersion = GLASS_SELECT_VERSION;
  select.style.display = "none";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "glass-select-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");

  const labelEl = document.createElement("span");
  labelEl.className = "glass-select-label";
  const caret = document.createElement("span");
  caret.className = "glass-select-caret";
  caret.textContent = "▾";

  trigger.appendChild(labelEl);
  trigger.appendChild(caret);

  const menu = document.createElement("div");
  menu.className = "glass-select-menu";
  menu.setAttribute("role", "listbox");
  menu.style.position = "fixed";
  menu.style.zIndex = "4000";
  menu.style.visibility = "hidden";

  wrapper.appendChild(trigger);
  const portal = getGlassSelectPortal();
  portal.appendChild(menu);
  if (select.id) menu.dataset.glassFor = select.id;

  const positionMenu = () => {
    const rect = trigger.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();
    const gap = 8;
    const minLeft = 8;
    const minTop = 8;
    const maxLeft = window.innerWidth - menuRect.width - minLeft;
    const maxTop = window.innerHeight - menuRect.height - minTop;

    let left = rect.left;
    if (left > maxLeft) left = Math.max(minLeft, maxLeft);
    if (left < minLeft) left = minLeft;

    let top = rect.bottom + gap;
    if (top > maxTop && rect.top - menuRect.height - gap >= minTop) {
      top = rect.top - menuRect.height - gap;
    }

    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.minWidth = `${rect.width}px`;
  };

  const closeMenu = () => updateOpenState(false);

  const updateOpenState = (open) => {
    wrapper.classList.toggle("open", open);
    trigger.setAttribute("aria-expanded", String(open));

    if (open) {
      menu.style.display = "grid";
      menu.style.visibility = "visible";
      requestAnimationFrame(positionMenu);
      setTimeout(positionMenu, 0);
      window.addEventListener("resize", positionMenu);
      window.addEventListener("scroll", positionMenu, true);
    } else {
      menu.style.display = "none";
      menu.style.visibility = "hidden";
      window.removeEventListener("resize", positionMenu);
      window.removeEventListener("scroll", positionMenu, true);
    }
  };

  trigger.addEventListener("click", () => {
    const next = !wrapper.classList.contains("open");
    updateOpenState(next);
  });

  trigger.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      updateOpenState(!wrapper.classList.contains("open"));
    }

    if (e.key === "Escape") {
      updateOpenState(false);
      trigger.blur();
    }
  });

  document.addEventListener("click", (e) => {
    if (wrapper.contains(e.target) || menu.contains(e.target)) return;
    closeMenu();
  });

  select.addEventListener("change", () => {
    const selected = select.options?.[select.selectedIndex];
    labelEl.textContent = selected?.textContent || "선택";
    menu.querySelectorAll(".glass-select-option").forEach((el) => {
      el.classList.toggle("active", el.dataset.value === select.value);
    });
  });

  const observer = new MutationObserver(() => {
    syncGlassSelect(select, menu, labelEl);
    if (wrapper.classList.contains("open")) {
      requestAnimationFrame(positionMenu);
    }
  });
  observer.observe(select, { childList: true, subtree: true });

  syncGlassSelect(select, menu, labelEl);

  const computed = getComputedStyle(select);
  const width = select.offsetWidth || parseFloat(computed.width) || 0;
  if (width) wrapper.style.minWidth = `${width}px`;
}

function getGlassSelectPortal() {
  let portal = document.getElementById("glassSelectPortal");
  if (portal) return portal;

  portal = document.createElement("div");
  portal.id = "glassSelectPortal";
  document.body.appendChild(portal);
  return portal;
}

function initGlassSelects(root = document) {
  GLASS_CLINIC_SELECT_IDS.forEach((id) => {
    const el = root.getElementById ? root.getElementById(id) : document.getElementById(id);
    if (!el) return;
    if (el.dataset.glassEnhanced === "true" && el.dataset.glassVersion !== GLASS_SELECT_VERSION) {
      const wrapper = el.closest(".glass-select");
      const existingMenu = el.id
        ? document.querySelector(`.glass-select-menu[data-glass-for="${el.id}"]`)
        : null;
      if (existingMenu) existingMenu.remove();
      if (wrapper && wrapper.parentElement) {
        wrapper.parentElement.insertBefore(el, wrapper);
        wrapper.remove();
      }
      el.classList.remove("glass-native");
      el.style.display = "";
      delete el.dataset.glassEnhanced;
      delete el.dataset.glassVersion;
    }
    enhanceGlassSelect(el);
  });
}

window.initGlassSelects = initGlassSelects;

document.addEventListener("DOMContentLoaded", () => {
  initGlassSelects();
});

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

function mixWithWhite(rgbString, ratio = 0.9) {
  const parts = String(rgbString || "")
    .split(",")
    .map((v) => Number.parseInt(v.trim(), 10));
  if (parts.length !== 3 || parts.some((v) => Number.isNaN(v))) return "#ffffff";
  const mix = (v) => Math.round(v * (1 - ratio) + 255 * ratio);
  return `rgb(${mix(parts[0])}, ${mix(parts[1])}, ${mix(parts[2])})`;
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
  const root = document.documentElement;
  const body = document.body;
  if (!root || !body) return;
  const storedPrimary = readUserStorage("themePrimary");
  const storedAccent = readUserStorage("themeAccent");
  const primary = storedPrimary || "#ffffff";
  const accent = storedAccent || "#ffffff";
  const primaryRgb = hexToRgbString(primary) || "255, 255, 255";
  const accentRgb = hexToRgbString(accent) || "255, 255, 255";

  root.style.setProperty("--theme-primary", primary);
  root.style.setProperty("--theme-accent", accent);
  root.style.setProperty("--theme-primary-rgb", primaryRgb);
  root.style.setProperty("--theme-accent-rgb", accentRgb);
  body.style.setProperty("--theme-primary", primary);
  body.style.setProperty("--theme-accent", accent);
  body.style.setProperty("--theme-primary-rgb", primaryRgb);
  body.style.setProperty("--theme-accent-rgb", accentRgb);

  const hasCustom = Boolean(storedPrimary || storedAccent);
  const nextBg = hasCustom ? mixWithWhite(accentRgb, 0.94) : "#ffffff";
  const nextSurface2 = hasCustom ? mixWithWhite(primaryRgb, 0.97) : "#ffffff";

  root.style.setProperty("--bg", "#ffffff");
  root.style.setProperty("--surface", "#ffffff");
  root.style.setProperty("--surface-2", nextSurface2);
  body.style.backgroundColor = nextBg;

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
