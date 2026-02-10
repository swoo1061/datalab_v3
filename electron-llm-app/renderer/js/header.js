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
const AGENT_HISTORY_LIMIT = 20;
const AGENT_CHAT_STORAGE_LIMIT = 20;
const AGENT_MESSAGE_STORAGE_LIMIT = 80;
const AGENT_HISTORY_STORAGE_PREFIX = "agentHistory:";
const AGENT_CHATS_STORAGE_PREFIX = "agentChats:";
const AGENT_ACTIVE_CHAT_STORAGE_PREFIX = "agentActiveChat:";
const AGENT_STYLE_STORAGE_PREFIX = "agentStyle:";
const AGENT_PREFS_STORAGE_PREFIX = "agentPrefs:";
let agentChats = [];
let activeAgentChatId = "";
let agentChatsStorageKey = "";
let agentActiveChatStorageKey = "";
let agentLegacyHistoryStorageKey = "";
let agentStyleStorageKey = "";
let agentPrefsStorageKey = "";
let agentToneStyle = "friendly";
let agentResponseLength = "balanced";
let agentEnterToSend = true;
let agentAutoScroll = true;
let agentStreamSpeed = "normal";
let agentFontSize = "normal";
let aiCatRoamRaf = null;
let aiCatRoamState = null;
let aiCatWalkRefCenterX = null;
let aiCatWalkRefScale = null;
let aiCatWalkRefFootY = null;
let agentSending = false;
// Walk cycle order (0-based frame index into walk-f*).
// Blend cat10~15(=index 9~14) into base walk and repeat cat13(index 12)
// to reduce the "fixed hind leg" feel.
const CAT_WALK_FRAME_ORDER = [
  // Keep stable loop around cat13 anchor, with cat15(14) included.
  12, 9, 14
];
const CAT_WALK_FRAME_FILES = [
  "cat1.png", "cat2.png", "cat3.png",
  "cat4.png", "cat5.png", "cat6.png",
  "cat7.png", "cat8.png", "cat9.png",
  "cat10.png", "cat11.png", "cat12.png",
  "cat13.png", "cat14.png", "cat15.png",
];
const CAT_WALK_FRAME_TARGET_BOX = { width: 184, height: 110 };
const AGENT_ACTION_LABEL = {
  review: "AI 리뷰 생성",
  gugong_review: "구공이 리뷰 생성",
  gangnam_review: "강남언니 후기 생성",
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
  {
    const res = await fetch(`./components/header.html?v=cat_hotfix_68`, { cache: "no-store" });
    if (!res.ok) {
      console.error("header.html fetch failed");
      return;
    }
    // Always refresh header markup to avoid stale DOM from previous hotfixes.
    headerRoot.innerHTML = await res.text();
  }

  const infoCloseBtn = document.querySelector("#profileInfoModal .popup-btn");
  if (infoCloseBtn) {
    infoCloseBtn.textContent = "←";
    infoCloseBtn.setAttribute("aria-label", "뒤로가기");
    infoCloseBtn.classList.add("info-back-btn");
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

  const userKey = me?.id ? `user:${me.id}` : `user:${me?.username || me?.email || "unknown"}`;
  localStorage.setItem("currentUserKey", userKey);
  agentChatsStorageKey = `${AGENT_CHATS_STORAGE_PREFIX}${userKey}`;
  agentActiveChatStorageKey = `${AGENT_ACTIVE_CHAT_STORAGE_PREFIX}${userKey}`;
  agentLegacyHistoryStorageKey = `${AGENT_HISTORY_STORAGE_PREFIX}${userKey}`;
  agentStyleStorageKey = `${AGENT_STYLE_STORAGE_PREFIX}${userKey}`;
  agentPrefsStorageKey = `${AGENT_PREFS_STORAGE_PREFIX}${userKey}`;
  loadAgentChats();
  loadAgentToneStyle();
  loadAgentPrefs();

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
  bindHeaderModeAndAgent();
  renderAgentChatSelector();
  renderAgentMessages();
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

function normalizeWalkFrameImage(frameEl, frameIndex) {
  if (!frameEl || frameEl.dataset.normDone === "1") return;
  const img = frameEl;
  const nw = img.naturalWidth || 0;
  const nh = img.naturalHeight || 0;
  if (!nw || !nh) return;

  const srcCanvas = document.createElement("canvas");
  srcCanvas.width = nw;
  srcCanvas.height = nh;
  const ctx = srcCanvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return;
  ctx.drawImage(img, 0, 0);

  const imageData = ctx.getImageData(0, 0, nw, nh);
  const data = imageData.data;

  // cat10~15 background cleanup:
  // remove only border-connected bright gray background (keep white cat body).
  if (frameIndex >= 9) {
    const visited = new Uint8Array(nw * nh);
    const queue = [];
    const isBgLike = (x, y) => {
      const i = (y * nw + x) * 4;
      const a = data[i + 3];
      if (a < 8) return false;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      return r >= 165 && g >= 165 && b >= 165 && (max - min) <= 24;
    };
    const push = (x, y) => {
      if (x < 0 || y < 0 || x >= nw || y >= nh) return;
      const id = y * nw + x;
      if (visited[id]) return;
      if (!isBgLike(x, y)) return;
      visited[id] = 1;
      queue.push(id);
    };

    for (let x = 0; x < nw; x += 1) {
      push(x, 0);
      push(x, nh - 1);
    }
    for (let y = 1; y < nh - 1; y += 1) {
      push(0, y);
      push(nw - 1, y);
    }

    while (queue.length) {
      const id = queue.pop();
      const x = id % nw;
      const y = (id - x) / nw;
      const i = id * 4;
      data[i + 3] = 0;
      push(x - 1, y);
      push(x + 1, y);
      push(x, y - 1);
      push(x, y + 1);
    }
  }

  // Keep only the largest connected alpha component.
  // This removes detached speed-lines/noise that cause anchor jitter.
  {
    const aOn = (x, y) => {
      const i = (y * nw + x) * 4;
      return data[i + 3] > 10;
    };
    const visited = new Uint8Array(nw * nh);
    let best = null;
    const stack = [];
    const push = (x, y) => {
      if (x < 0 || y < 0 || x >= nw || y >= nh) return;
      const id = y * nw + x;
      if (visited[id]) return;
      if (!aOn(x, y)) return;
      visited[id] = 1;
      stack.push(id);
    };
    for (let y = 0; y < nh; y += 1) {
      for (let x = 0; x < nw; x += 1) {
        const id0 = y * nw + x;
        if (visited[id0] || !aOn(x, y)) continue;
        visited[id0] = 1;
        stack.length = 0;
        stack.push(id0);
        const comp = [];
        while (stack.length) {
          const id = stack.pop();
          comp.push(id);
          const cx = id % nw;
          const cy = (id - cx) / nw;
          push(cx - 1, cy);
          push(cx + 1, cy);
          push(cx, cy - 1);
          push(cx, cy + 1);
        }
        if (!best || comp.length > best.length) best = comp;
      }
    }
    if (best && best.length) {
      const keep = new Uint8Array(nw * nh);
      for (const id of best) keep[id] = 1;
      for (let id = 0; id < nw * nh; id += 1) {
        if (!keep[id]) {
          data[id * 4 + 3] = 0;
        }
      }
    }
  }

  let minX = nw;
  let minY = nh;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < nh; y += 1) {
    for (let x = 0; x < nw; x += 1) {
      const i = (y * nw + x) * 4;
      if (data[i + 3] > 10) {
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX < minX || maxY < minY) return;

  ctx.putImageData(imageData, 0, 0);

  const cropW = maxX - minX + 1;
  const cropH = maxY - minY + 1;
  const targetW = CAT_WALK_FRAME_TARGET_BOX.width;
  const targetH = CAT_WALK_FRAME_TARGET_BOX.height;
  let scale = Math.min(targetW / cropW, targetH / cropH);

  // Bottom-most opaque point in cropped space (foot baseline candidate).
  let localFootY = cropH - 1;
  outer:
  for (let y = maxY; y >= minY; y -= 1) {
    for (let x = minX; x <= maxX; x += 1) {
      const i = (y * nw + x) * 4;
      if (data[i + 3] > 10) {
        localFootY = y - minY;
        break outer;
      }
    }
  }

  // Use cat13(index 12) as strict global reference for scale + baseline.
  if (frameIndex === 12 || aiCatWalkRefScale == null) {
    aiCatWalkRefScale = scale;
    aiCatWalkRefFootY = localFootY * scale;
  } else if (aiCatWalkRefScale != null) {
    scale = aiCatWalkRefScale;
  }
  const drawW = Math.max(1, Math.round(cropW * scale));
  const drawH = Math.max(1, Math.round(cropH * scale));

  // Compute anchor from torso region only (exclude extended paws/speed-lines).
  // This greatly reduces frame-to-frame horizontal popping.
  let sumX = 0;
  let countX = 0;
  for (let y = minY; y <= maxY; y += 1) {
    const ry = y - minY;
    const yInTorso = ry <= cropH * 0.72;
    if (!yInTorso) continue;
    for (let x = minX; x <= maxX; x += 1) {
      const rx = x - minX;
      const xInTorso = rx >= cropW * 0.18 && rx <= cropW * 0.82;
      if (!xInTorso) continue;
      const i = (y * nw + x) * 4;
      if (data[i + 3] > 10) {
        sumX += rx;
        countX += 1;
      }
    }
  }
  if (!countX) {
    for (let y = minY; y <= maxY; y += 1) {
      for (let x = minX; x <= maxX; x += 1) {
        const i = (y * nw + x) * 4;
        if (data[i + 3] > 10) {
          sumX += (x - minX);
          countX += 1;
        }
      }
    }
  }
  const localCx = countX ? (sumX / countX) : (cropW / 2);
  const centeredDx = (targetW - drawW) / 2;
  const centeredCx = centeredDx + (localCx * scale);
  if (frameIndex === 12 || aiCatWalkRefCenterX == null) {
    aiCatWalkRefCenterX = centeredCx;
  }

  const out = document.createElement("canvas");
  out.width = targetW;
  out.height = targetH;
  const octx = out.getContext("2d");
  if (!octx) return;
  octx.clearRect(0, 0, targetW, targetH);
  let dx = Math.round((aiCatWalkRefCenterX ?? centeredCx) - (localCx * scale));
  dx = Math.max(-2, Math.min(targetW - drawW + 2, dx));
  const baselineY = targetH - 2;
  let dy = Math.round(baselineY - (localFootY * scale));
  dy = Math.max(-2, Math.min(targetH - 1, dy));
  octx.drawImage(srcCanvas, minX, minY, cropW, cropH, dx, dy, drawW, drawH);

  frameEl.dataset.normDone = "1";
  frameEl.src = out.toDataURL("image/png");
}

// ================================
// 프로필 메뉴
// ================================
function bindProfileMenu() {
  document.querySelectorAll(".menu-item").forEach((item) => {
    item.onclick = () => {
      const action = item.dataset.action;
      if (action === "profile") openProfileInfo();
      if (action === "attendance") window.showAlert?.("출퇴근 기록 준비중");
      if (action === "my_dashboard") window.nav.go("my_dashboard");
    };
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

    window.showAlert?.("검색 결과가 없습니다");
  });
}

function bindHeaderModeAndAgent() {
  const agentBtn = document.getElementById("headerModeAgent");
  const closeBtn = document.getElementById("agentPanelClose");
  const settingsToggleEl = document.getElementById("agentSettingsToggle");
  const settingsPanelEl = document.getElementById("agentSettingsPanel");
  const agentPanelEl = document.getElementById("agentPanel");
  const sendBtn = document.getElementById("agentSend");
  const inputEl = document.getElementById("agentInput");
  const newChatBtn = document.getElementById("agentNewChat");
  const chatSelectEl = document.getElementById("agentChatSelect");
  const toneSelectEl = document.getElementById("agentToneSelect");
  const responseLengthEl = document.getElementById("agentResponseLength");
  const enterToSendEl = document.getElementById("agentEnterToSend");
  const autoScrollEl = document.getElementById("agentAutoScroll");
  const streamSpeedEl = document.getElementById("agentStreamSpeed");
  const fontSizeEl = document.getElementById("agentFontSize");

  if (!agentBtn) return;
  initAICatRoaming();

  const applyAgentFontSize = () => {
    if (!agentPanelEl) return;
    agentPanelEl.classList.remove("font-small", "font-normal", "font-large");
    const next = ["small", "normal", "large"].includes(agentFontSize) ? agentFontSize : "normal";
    agentPanelEl.classList.add(`font-${next}`);
  };

  const openAgentSettings = (open) => {
    if (!settingsPanelEl) return;
    if (open) {
      settingsPanelEl.classList.remove("hidden");
      settingsPanelEl.setAttribute("aria-hidden", "false");
      settingsToggleEl?.setAttribute("aria-expanded", "true");
    } else {
      settingsPanelEl.classList.add("hidden");
      settingsPanelEl.setAttribute("aria-hidden", "true");
      settingsToggleEl?.setAttribute("aria-expanded", "false");
    }
  };
  openAgentSettings(false);

  agentBtn.addEventListener("click", () => setHeaderMode("agent"));
  closeBtn?.addEventListener("click", () => {
    openAgentSettings(false);
    setHeaderMode("closed");
  });
  settingsToggleEl?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const isOpen = settingsPanelEl && !settingsPanelEl.classList.contains("hidden");
    openAgentSettings(!isOpen);
  });
  sendBtn?.addEventListener("click", () => handleAgentSend());
  newChatBtn?.addEventListener("click", () => {
    createNewAgentChat();
    renderAgentChatSelector();
    renderAgentMessages();
    ensureAgentInitGreeting();
  });
  chatSelectEl?.addEventListener("change", () => {
    const chatId = chatSelectEl.value || "";
    if (!chatId) return;
    setActiveAgentChat(chatId);
    renderAgentMessages();
    ensureAgentInitGreeting();
  });
  toneSelectEl?.addEventListener("change", () => {
    const next = String(toneSelectEl.value || "friendly");
    if (!["calm", "friendly", "coach", "cute"].includes(next)) return;
    agentToneStyle = next;
    saveAgentToneStyle();
  });
  responseLengthEl?.addEventListener("change", () => {
    const next = String(responseLengthEl.value || "balanced");
    if (!["short", "balanced", "long"].includes(next)) return;
    agentResponseLength = next;
    saveAgentPrefs();
  });
  enterToSendEl?.addEventListener("change", () => {
    agentEnterToSend = !!enterToSendEl.checked;
    saveAgentPrefs();
  });
  autoScrollEl?.addEventListener("change", () => {
    agentAutoScroll = !!autoScrollEl.checked;
    saveAgentPrefs();
  });
  streamSpeedEl?.addEventListener("change", () => {
    const next = String(streamSpeedEl.value || "normal");
    if (!["slow", "normal", "fast"].includes(next)) return;
    agentStreamSpeed = next;
    saveAgentPrefs();
  });
  fontSizeEl?.addEventListener("change", () => {
    const next = String(fontSizeEl.value || "normal");
    if (!["small", "normal", "large"].includes(next)) return;
    agentFontSize = next;
    applyAgentFontSize();
    saveAgentPrefs();
  });
  if (toneSelectEl) toneSelectEl.value = agentToneStyle;
  if (responseLengthEl) responseLengthEl.value = agentResponseLength;
  if (enterToSendEl) enterToSendEl.checked = !!agentEnterToSend;
  if (autoScrollEl) autoScrollEl.checked = !!agentAutoScroll;
  if (streamSpeedEl) streamSpeedEl.value = agentStreamSpeed;
  if (fontSizeEl) fontSizeEl.value = agentFontSize;
  applyAgentFontSize();
  inputEl?.addEventListener("keydown", (e) => {
    if (!agentEnterToSend) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      handleAgentSend();
    }
  }, true);
}

function loadAgentToneStyle() {
  agentToneStyle = "friendly";
  if (!agentStyleStorageKey) return;
  try {
    const raw = localStorage.getItem(agentStyleStorageKey) || "friendly";
    if (["calm", "friendly", "coach", "cute"].includes(raw)) {
      agentToneStyle = raw;
    }
  } catch (_e) {
    agentToneStyle = "friendly";
  }
}

function saveAgentToneStyle() {
  if (!agentStyleStorageKey) return;
  try {
    localStorage.setItem(agentStyleStorageKey, agentToneStyle || "friendly");
  } catch (_e) {
    // ignore storage errors
  }
}

function loadAgentPrefs() {
  agentResponseLength = "balanced";
  agentEnterToSend = true;
  agentAutoScroll = true;
  agentStreamSpeed = "normal";
  agentFontSize = "normal";
  if (!agentPrefsStorageKey) return;
  try {
    const raw = localStorage.getItem(agentPrefsStorageKey);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed?.responseLength === "short" || parsed?.responseLength === "balanced" || parsed?.responseLength === "long") {
      agentResponseLength = parsed.responseLength;
    }
    if (typeof parsed?.enterToSend === "boolean") agentEnterToSend = parsed.enterToSend;
    if (typeof parsed?.autoScroll === "boolean") agentAutoScroll = parsed.autoScroll;
    if (parsed?.streamSpeed === "slow" || parsed?.streamSpeed === "normal" || parsed?.streamSpeed === "fast") {
      agentStreamSpeed = parsed.streamSpeed;
    }
    if (parsed?.fontSize === "small" || parsed?.fontSize === "normal" || parsed?.fontSize === "large") {
      agentFontSize = parsed.fontSize;
    }
  } catch (_e) {
    // ignore storage errors
  }
}

function saveAgentPrefs() {
  if (!agentPrefsStorageKey) return;
  try {
    localStorage.setItem(
      agentPrefsStorageKey,
      JSON.stringify({
        responseLength: agentResponseLength,
        enterToSend: agentEnterToSend,
        autoScroll: agentAutoScroll,
        streamSpeed: agentStreamSpeed,
        fontSize: agentFontSize,
      }),
    );
  } catch (_e) {
    // ignore storage errors
  }
}

function getAgentStreamCharMs() {
  if (agentStreamSpeed === "slow") return 28;
  if (agentStreamSpeed === "fast") return 10;
  return 16;
}

function initAICatRoaming() {
  const zone = document.querySelector(".cat-roam-zone");
  const cat = document.getElementById("headerModeAgent");
  if (!zone || !cat) return;
  if (cat.dataset.roamInit === "true") return;
  cat.dataset.roamInit = "true";
  cat.dataset.step = String(CAT_WALK_FRAME_ORDER[0] ?? 0);
  aiCatWalkRefCenterX = null;
  aiCatWalkRefScale = null;
  aiCatWalkRefFootY = null;
  const activeFrameSet = new Set(CAT_WALK_FRAME_ORDER);
  let normalizedCount = 0;
  const targetNormalizeCount = activeFrameSet.size;
  cat.style.setProperty("visibility", "hidden", "important");

  // Force walk frames to original user assets (cat1..cat22), bypassing stale header markup.
  for (let i = 0; i < 22; i += 1) {
    const frameEl = cat.querySelector(`.cat-photo.walk-f${i}`);
    if (!frameEl) continue;
    if (i < CAT_WALK_FRAME_FILES.length && activeFrameSet.has(i)) {
      frameEl.src = `./assets/${CAT_WALK_FRAME_FILES[i]}?v=16`;
      frameEl.dataset.disabled = "0";
      frameEl.style.removeProperty("display");
    } else {
      // Hard-disable unknown extra frames so they can never pop in.
      frameEl.removeAttribute("src");
      frameEl.dataset.disabled = "1";
      frameEl.style.setProperty("display", "none", "important");
      continue;
    }
    frameEl.style.setProperty(
      "transform",
      "scale(var(--cat-walk-scale)) translateY(var(--cat-walk-y))",
      "important",
    );
    const normalizeNow = () => {
      normalizeWalkFrameImage(frameEl, i);
      if (activeFrameSet.has(i)) {
        normalizedCount += 1;
        if (normalizedCount >= targetNormalizeCount) {
          cat.style.removeProperty("visibility");
        }
      }
    };
    frameEl.addEventListener("load", normalizeNow, { once: true });
    if (frameEl.complete && frameEl.naturalWidth > 0) normalizeNow();
  }

  // Hard lock cat size vars here to bypass duplicated CSS overrides.
  cat.style.setProperty("--cat-walk-scale", "0.8", "important");
  cat.style.setProperty("--cat-sit-scale", "0.86", "important");
  cat.style.setProperty("--cat-sit-side-scale", "0.86", "important");
  cat.style.setProperty("--cat-stretch-scale", "0.86", "important");
  cat.style.setProperty("--cat-walk-y", "2px", "important");
  cat.style.setProperty("--cat-sit-y", "0px", "important");
  cat.style.setProperty("--cat-sit-side-y", "0px", "important");
  cat.style.setProperty("--cat-stretch-y", "0px", "important");

  const chooseTarget = () => {
    const zoneRect = zone.getBoundingClientRect();
    const catRect = cat.getBoundingClientRect();
    const maxX = Math.max(24, zoneRect.width - catRect.width - 24);
    return {
      x: 12 + Math.random() * (maxX - 12),
      y: 0,
    };
  };

  const setMovingClass = (moving) => {
    cat.classList.toggle("is-moving", !!moving);
  };

  aiCatRoamState = {
    x: 12,
    renderX: 12,
    y: 0,
    renderY: 0,
    target: chooseTarget(),
    direction: 1,
    speed: 0,
    moving: false,
    nextMoveAt: performance.now() + 500,
    lastTs: performance.now(),
    startedAt: performance.now(),
    stepAt: performance.now(),
    stepTimer: 0,
    walkStrideAccum: 0,
    stepIndex: 0,
    idleSitUntil: 0,
    stretchUntil: 0,
    paused: false,
  };

  const tick = (now) => {
    if (!aiCatRoamState) return;
    const state = aiCatRoamState;
    const dt = Math.max(8, Math.min(34, now - (state.lastTs || now)));
    state.lastTs = now;

    if (!state.paused) {
      const dx = state.target.x - state.x;
      const dist = Math.abs(dx);
      const isStretching = now < (state.stretchUntil || 0);
      const isIdleSit = now < (state.idleSitUntil || 0);
      const isResting = !isStretching && !isIdleSit && now < state.nextMoveAt;
      cat.classList.toggle("is-stretching", isStretching);
      cat.classList.toggle("is-idle-sit", isIdleSit && !isStretching);
      cat.classList.toggle("is-resting", isResting);

      if (isStretching || isIdleSit) {
        state.moving = false;
        state.speed = 0;
        state.stepIndex = 0;
        cat.dataset.step = String(CAT_WALK_FRAME_ORDER[0] ?? 0);
      } else if (isResting) {
        // Rest phase before next movement.
        state.moving = false;
        state.speed += (0 - state.speed) * 0.1;
        state.stepIndex = 0;
        cat.dataset.step = String(CAT_WALK_FRAME_ORDER[0] ?? 0);
      } else {
        // Move phase with soft acceleration/deceleration.
        state.moving = true;
        const desiredSpeed = Math.min(0.32, 0.06 + dist * 0.0062);
        state.speed += (desiredSpeed - state.speed) * 0.08;
        const step = Math.min(dist, state.speed * (dt / 16.7));
        if (dist > 0.001) state.x += Math.sign(dx) * step;

        // Walk-only mode.
        cat.classList.remove("is-running");

        state.stepTimer = (state.stepTimer || 0) + dt;
        // Slow leg cadence so feet don't over-cycle compared to body movement.
        // Foot cycle is distance-driven to avoid "skating" look.
        state.walkStrideAccum += Math.abs(step);
        const stridePx = 10.8;
        if (state.walkStrideAccum >= stridePx) {
          state.walkStrideAccum -= stridePx;
          // Prevent burst-skip on occasional large dt spikes.
          if (state.walkStrideAccum > stridePx * 0.9) {
            state.walkStrideAccum = stridePx * 0.9;
          }
          state.stepIndex = (state.stepIndex >= (CAT_WALK_FRAME_ORDER.length - 1) || state.stepIndex < 0 || state.stepIndex > (CAT_WALK_FRAME_ORDER.length - 1))
            ? 0
            : state.stepIndex + 1;
          const frameIdx = CAT_WALK_FRAME_ORDER[state.stepIndex] ?? 0;
          cat.dataset.step = String(frameIdx);
        }

        if (dist < 3.2) {
          state.target = chooseTarget();
          state.nextMoveAt = now + 2400 + Math.random() * 2600;
          state.moving = false;
          state.stepIndex = 0;
          state.stepTimer = 0;
          state.walkStrideAccum = 0;
          cat.classList.remove("is-running");
          cat.dataset.step = String(CAT_WALK_FRAME_ORDER[0]);
          const poseRand = Math.random();
          if (poseRand < 0.24) {
            state.idleSitUntil = now + 1400 + Math.random() * 1800;
            state.stretchUntil = 0;
          } else if (poseRand < 0.52) {
            state.stretchUntil = now + 1100 + Math.random() * 900;
            state.idleSitUntil = 0;
          } else {
            state.idleSitUntil = 0;
            state.stretchUntil = 0;
          }
        }
      }

      if (Math.abs(dx) > 0.8) {
        // Source walk frames face right by default.
        state.direction = dx > 0 ? 1 : -1;
      }
    } else {
      state.moving = false;
      state.speed = 0;
      cat.classList.remove("is-resting", "is-idle-sit", "is-stretching");
      cat.classList.remove("is-running");
      cat.dataset.step = String(CAT_WALK_FRAME_ORDER[0] ?? 0);
    }

    setMovingClass(state.moving && !state.paused);
    const smoothFactor = state.moving ? 0.18 : 0.12;
    const ySmoothFactor = state.moving ? 0.24 : 0.16;
    state.renderX += (state.x - state.renderX) * smoothFactor;
    state.renderY += (0 - state.renderY) * ySmoothFactor;
    cat.style.setProperty(
      "transform",
      `translate3d(${state.renderX}px, ${state.renderY}px, 0) scaleX(${state.direction})`,
      "important"
    );

    aiCatRoamRaf = requestAnimationFrame(tick);
  };

  aiCatRoamRaf = requestAnimationFrame(tick);
}

function buildAgentChatTitle(messages = []) {
  const firstUser = messages.find((m) => m?.role === "user" && m?.content);
  if (!firstUser) return "새 채팅";
  const base = String(firstUser.content).replace(/\s+/g, " ").trim();
  if (!base) return "새 채팅";
  return base.length > 20 ? `${base.slice(0, 20)}...` : base;
}

function sanitizeAgentMessages(messages = []) {
  if (!Array.isArray(messages)) return [];
  return messages
    .map((item) => ({
      role: item?.role === "assistant" ? "assistant" : "user",
      content: String(item?.content || "").trim(),
      actions: Array.isArray(item?.actions) ? item.actions : [],
    }))
    .filter((item) => (item.role === "user" || item.role === "assistant") && item.content)
    .slice(-AGENT_MESSAGE_STORAGE_LIMIT);
}

function normalizeAgentChat(raw) {
  const messages = sanitizeAgentMessages(raw?.messages || []);
  const id = String(raw?.id || `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const nowIso = new Date().toISOString();
  return {
    id,
    title: String(raw?.title || buildAgentChatTitle(messages) || "새 채팅"),
    created_at: String(raw?.created_at || nowIso),
    updated_at: String(raw?.updated_at || nowIso),
    messages,
  };
}

function getActiveAgentChat() {
  return agentChats.find((chat) => chat.id === activeAgentChatId) || null;
}

function setActiveAgentChat(chatId) {
  const target = agentChats.find((chat) => chat.id === chatId);
  if (!target) return;
  activeAgentChatId = target.id;
  saveAgentChats();
}

function createNewAgentChat() {
  const nowIso = new Date().toISOString();
  const chat = {
    id: `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    title: "새 채팅",
    created_at: nowIso,
    updated_at: nowIso,
    messages: [],
  };
  agentChats.unshift(chat);
  if (agentChats.length > AGENT_CHAT_STORAGE_LIMIT) {
    agentChats = agentChats.slice(0, AGENT_CHAT_STORAGE_LIMIT);
  }
  activeAgentChatId = chat.id;
  saveAgentChats();
  return chat;
}

function loadAgentChats() {
  let loadedChats = [];
  try {
    const raw = localStorage.getItem(agentChatsStorageKey);
    const parsed = raw ? JSON.parse(raw) : [];
    if (Array.isArray(parsed)) {
      loadedChats = parsed.map((item) => normalizeAgentChat(item));
    }
  } catch (_e) {
    loadedChats = [];
  }

  // Backward compatibility: migrate single history to first chat.
  if (!loadedChats.length && agentLegacyHistoryStorageKey) {
    try {
      const legacyRaw = localStorage.getItem(agentLegacyHistoryStorageKey);
      const legacyParsed = legacyRaw ? JSON.parse(legacyRaw) : [];
      const legacyMessages = sanitizeAgentMessages(legacyParsed);
      if (legacyMessages.length) {
        loadedChats = [
          normalizeAgentChat({
            id: `chat_${Date.now()}_legacy`,
            title: buildAgentChatTitle(legacyMessages),
            messages: legacyMessages,
          }),
        ];
      }
    } catch (_e) {
      // ignore legacy parse errors
    }
  }

  agentChats = loadedChats.slice(0, AGENT_CHAT_STORAGE_LIMIT);
  try {
    activeAgentChatId = localStorage.getItem(agentActiveChatStorageKey) || "";
  } catch (_e) {
    activeAgentChatId = "";
  }
  if (!getActiveAgentChat()) {
    activeAgentChatId = agentChats[0]?.id || "";
  }
  if (!activeAgentChatId) {
    createNewAgentChat();
  }
}

function saveAgentChats() {
  if (!agentChatsStorageKey || !agentActiveChatStorageKey) return;
  try {
    localStorage.setItem(agentChatsStorageKey, JSON.stringify(agentChats.slice(0, AGENT_CHAT_STORAGE_LIMIT)));
    localStorage.setItem(agentActiveChatStorageKey, activeAgentChatId || "");
  } catch (_e) {
    // ignore storage errors
  }
}

function renderAgentChatSelector() {
  const selectEl = document.getElementById("agentChatSelect");
  if (!selectEl) return;
  const options = [...agentChats]
    .sort((a, b) => new Date(b.updated_at).valueOf() - new Date(a.updated_at).valueOf())
    .map((chat) => `<option value="${chat.id}">${chat.title}</option>`);
  selectEl.innerHTML = options.join("");
  if (activeAgentChatId) selectEl.value = activeAgentChatId;
}

function renderAgentMessages() {
  const container = document.getElementById("agentMessages");
  if (!container) return;

  container.innerHTML = "";
  const chat = getActiveAgentChat();
  const messages = chat?.messages || [];
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "agent-empty";
    empty.innerText = "자유롭게 대화하세요. 감정/상황까지 반영해서 도와드릴게요.";
    container.appendChild(empty);
    return;
  }

  messages.forEach((item) => {
    appendAgentMessage(item.role, item.content, item.actions || []);
  });
}

function pushAgentMessage(role, content, actions = []) {
  const chat = getActiveAgentChat();
  if (!chat) return;
  const text = String(content || "").trim();
  if (!text) return;
  chat.messages.push({
    role: role === "assistant" ? "assistant" : "user",
    content: text,
    actions: Array.isArray(actions) ? actions : [],
  });
  if (chat.messages.length > AGENT_MESSAGE_STORAGE_LIMIT) {
    chat.messages = chat.messages.slice(-AGENT_MESSAGE_STORAGE_LIMIT);
  }
  chat.updated_at = new Date().toISOString();
  if (role === "user" && chat.title === "새 채팅") {
    chat.title = buildAgentChatTitle(chat.messages);
  }
  saveAgentChats();
}

function setHeaderMode(mode) {
  const agentBtn = document.getElementById("headerModeAgent");
  const panel = document.getElementById("agentPanel");
  const inputEl = document.getElementById("agentInput");

  const currentlyOpen = !!panel && !panel.classList.contains("hidden");
  let nextOpen = currentlyOpen;
  if (mode === "agent") nextOpen = !currentlyOpen;
  if (mode === "open") nextOpen = true;
  if (mode === "closed") nextOpen = false;

  agentBtn?.classList.toggle("active", nextOpen);
  panel?.classList.toggle("hidden", !nextOpen);
  if (panel) panel.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  document.body.classList.toggle("agent-open", nextOpen);
  if (aiCatRoamState) {
    aiCatRoamState.paused = nextOpen;
    aiCatRoamState.nextMoveAt = performance.now() + (nextOpen ? 999999 : 300);
    if (nextOpen) {
      aiCatRoamState.idleSitUntil = 0;
      aiCatRoamState.stretchUntil = 0;
    }
  }
  agentBtn?.classList.toggle("is-sitting", nextOpen);
  agentBtn?.classList.toggle("is-moving", !nextOpen);
  if (nextOpen) {
    agentBtn?.classList.remove("is-idle-sit", "is-stretching");
  }

  if (nextOpen) {
    inputEl?.focus();
    ensureAgentInitGreeting();
  }
}

function ensureAgentInitGreeting() {
  const container = document.getElementById("agentMessages");
  if (!container) return;
  const active = getActiveAgentChat();
  if (!active) return;
  if (active.messages.length > 0) return;
  const text = "안녕하세요. 오늘 업무 같이 정리해볼까요? 편하게 말해주시면 바로 도와드릴게요.";
  appendAgentMessage("assistant", text);
  pushAgentMessage("assistant", text);
  renderAgentChatSelector();
}

function appendAgentMessage(role, text, actions = []) {
  const container = document.getElementById("agentMessages");
  if (!container) return null;

  const empty = container.querySelector(".agent-empty");
  if (empty) empty.remove();

  const wrap = document.createElement("div");
  wrap.className = `agent-message ${role === "user" ? "user" : "assistant"}`;

  const content = document.createElement("div");
  content.className = "agent-bubble";
  content.innerText = text || "";
  wrap.appendChild(content);

  appendAgentActionButtons(wrap, actions);

  container.appendChild(wrap);
  if (agentAutoScroll) container.scrollTop = container.scrollHeight;
  return { wrap, content };
}

function appendAgentActionButtons(wrap, actions = []) {
  if (!wrap || !Array.isArray(actions) || !actions.length) return;
  const actionsEl = document.createElement("div");
  actionsEl.className = "agent-actions";
  actions.forEach((action) => {
    if (action?.type !== "navigate" || !action?.page) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "agent-action-btn";
    const label = AGENT_ACTION_LABEL[action.page] || action.page;
    btn.innerText = `${label} 이동`;
    btn.addEventListener("click", () => window.nav?.go?.(action.page));
    actionsEl.appendChild(btn);
  });
  if (actionsEl.childElementCount > 0) wrap.appendChild(actionsEl);
}

async function streamAgentAssistantMessage(text, actions = []) {
  const created = appendAgentMessage("assistant", "");
  if (!created) return;

  const { wrap, content } = created;
  const fullText = String(text || "");
  const totalLen = fullText.length;
  if (!totalLen) return;

  const perCharMs = getAgentStreamCharMs();
  const chunkMin = 1;
  const chunkMax = 3;
  let idx = 0;

  while (idx < totalLen) {
    const chunk = Math.min(
      totalLen - idx,
      Math.max(chunkMin, Math.min(chunkMax, Math.floor(Math.random() * 3) + 1))
    );
    idx += chunk;
    content.innerText = fullText.slice(0, idx);
    const container = document.getElementById("agentMessages");
    if (agentAutoScroll && container) container.scrollTop = container.scrollHeight;
    await new Promise((resolve) => setTimeout(resolve, perCharMs * chunk));
  }

  appendAgentActionButtons(wrap, actions);
}

async function streamAgentResponse(payload) {
  const headers = await buildAuthHeaders();
  const response = await fetch(`${window.API_BASE}/api/ml/agent/chat/stream/`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`stream http ${response.status}`);
  }

  const created = appendAgentMessage("assistant", "");
  if (!created) throw new Error("assistant bubble create failed");
  const { wrap, content } = created;

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let answer = "";
  let actions = [];
  let source = "";
  let model = "";
  let suggestions = [];

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      let msg = null;
      try {
        msg = JSON.parse(line);
      } catch (_e) {
        continue;
      }

      if (msg.type === "delta") {
        const chunk = String(msg.text || "");
        if (!chunk) continue;
        answer += chunk;
        content.innerText = answer;
        const container = document.getElementById("agentMessages");
        if (agentAutoScroll && container) container.scrollTop = container.scrollHeight;
      } else if (msg.type === "done") {
        answer = String(msg.answer || answer || "");
        actions = Array.isArray(msg.actions) ? msg.actions : [];
        source = String(msg.source || "");
        model = String(msg.model || "");
        suggestions = Array.isArray(msg.suggestions) ? msg.suggestions : [];
      }
    }
  }

  content.innerText = answer || "응답을 받지 못했습니다.";
  appendAgentActionButtons(wrap, actions);
  return { answer: content.innerText, actions, source, model, suggestions };
}

function getAgentContextPayload() {
  const navKey = document.body?.dataset?.nav || "";
  const title = document.getElementById("pageTitle")?.innerText || "";
  return {
    nav: navKey,
    title,
    url: window.location.pathname || "",
    agent_style: agentToneStyle || "friendly",
    response_length: agentResponseLength || "balanced",
  };
}

async function handleAgentSend() {
  if (agentSending) return;
  const active = getActiveAgentChat();
  if (!active) return;
  const inputEl = document.getElementById("agentInput");
  const sendBtn = document.getElementById("agentSend");
  if (!inputEl) return;
  const message = (inputEl.value || "").trim();
  if (!message) return;

  agentSending = true;
  if (sendBtn) sendBtn.disabled = true;
  inputEl.disabled = true;
  inputEl.value = "";
  appendAgentMessage("user", message);
  pushAgentMessage("user", message);
  renderAgentChatSelector();

  const payload = {
    message,
    context: getAgentContextPayload(),
    history: active.messages.slice(-AGENT_HISTORY_LIMIT).map((h) => ({
      role: h.role,
      content: h.content,
    })),
  };

  try {
    let answer = "";
    let actions = [];
    try {
      const streamed = await streamAgentResponse(payload);
      answer = streamed.answer || "응답을 받지 못했습니다.";
      actions = Array.isArray(streamed.actions) ? streamed.actions : [];
    } catch (_streamErr) {
      const res = await window.api?.agentChat?.(payload);
      answer = res?.answer || "응답을 받지 못했습니다.";
      actions = Array.isArray(res?.actions) ? res.actions : [];
      await streamAgentAssistantMessage(answer, actions);
    }
    pushAgentMessage("assistant", answer, actions);
    renderAgentChatSelector();
  } catch (e) {
    const errorText = "요청 처리 중 오류가 발생했습니다.";
    appendAgentMessage("assistant", errorText);
    pushAgentMessage("assistant", errorText);
    renderAgentChatSelector();
  } finally {
    agentSending = false;
    if (sendBtn) sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }
}

async function buildAuthHeaders() {
  const headers = {};
  const sessionKey = await window.session?.getKey?.();
  if (sessionKey) headers["X-Sessionid"] = sessionKey;
  return headers;
}

let notifyPollTimer = null;
let notifyItemsById = new Map();
let notifyItems = [];
const ATTENDANCE_MEMO_PLATFORM = "__attendance_correction__";
const VACATION_MEMO_PLATFORM = "__vacation__";

function getNotifyItemTime(item) {
  const raw = item?.created_at || item?.updated_at;
  const d = raw ? new Date(raw) : null;
  return d && !Number.isNaN(d.valueOf()) ? d.getTime() : 0;
}

function classifyHeaderAlert(item) {
  const platform = String(item?.platform || "").toLowerCase();
  if (platform === ATTENDANCE_MEMO_PLATFORM) return "attendance";
  if (platform === VACATION_MEMO_PLATFORM) return "vacation";
  return "memo";
}

function bindNotifications() {
  const button = document.getElementById("notifyButton");
  const dropdown = document.getElementById("notifyDropdown");
  const list = document.getElementById("notifyList");
  const empty = document.getElementById("notifyEmpty");
  const detail = document.getElementById("notifyDetail");
  const backBtn = document.getElementById("notifyBack");
  const openCenterBtn = document.getElementById("notifyOpenCenter");

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

  openCenterBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (typeof window.navigate === "function") {
      window.navigate("notifications_center");
      return;
    }
    if (window.nav?.go) {
      window.nav.go("notifications_center");
    } else {
      window.location.href = "notifications_center.html";
    }
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
    let memoItems = [];
    let unreadNotify = 0;
    try {
      const res = await fetch(`${window.API_BASE}/api/data/notifications/?limit=20`, {
        credentials: "include",
        headers,
      });
      if (res.ok) {
        const data = await res.json();
        unreadNotify = Number(data?.unread_count || 0);
        memoItems = (data?.results || []).map((item) => ({
          ...item,
          _kind: "memo",
          _key: `memo:${item.id}`,
        }));
      }
    } catch (_e) {
      // ignore notification fetch errors
    }
    let mailItems = [];
    let unreadMail = 0;
    try {
      const mres = await fetch(`${window.API_BASE}/api/data/messages/?box=inbox&limit=20`, {
        credentials: "include",
        headers,
      });
      if (mres.ok) {
        const mdata = await mres.json();
        unreadMail = Number(mdata?.unread_count || 0);
        mailItems = mdata?.results || [];
      }
    } catch (e) {
      // ignore mail unread fetch errors
    }

    const inboxItems = mailItems.map((item) => ({
      ...item,
      _kind: "mail",
      _key: `mail:${item.id}`,
    }));
    const items = [...memoItems, ...inboxItems]
      .sort((a, b) => getNotifyItemTime(b) - getNotifyItemTime(a))
      .slice(0, 30);

    const unreadCount = unreadNotify + unreadMail;
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

  notifyItems = items.slice();
  notifyItemsById = new Map(notifyItems.map((item) => [String(item._key || item.id), item]));
  if (detail) detail.classList.add("hidden");
  if (empty) empty.classList.add("hidden");
  list.classList.remove("hidden");

  list.innerHTML = items
    .map((item) => {
      const alertType = item._kind === "mail" ? "mail" : classifyHeaderAlert(item);
      const kindLabel =
        alertType === "mail" ? "메일" : alertType === "attendance" ? "근태" : alertType === "vacation" ? "휴가" : "메모";
      const title = item._kind === "mail"
        ? (item.subject || "").trim() || "제목 없음"
        : (item.content || "").trim() || "메모";
      const dateLabel = item._kind === "mail"
        ? (item.sender_name || "-")
        : (item.date || "-");

      return `
        <div class="notify-item ${item.is_read ? "is-read" : ""}" data-id="${item._key || item.id}" data-date="${dateLabel}">
          <div class="notify-summary">[${kindLabel}] ${dateLabel} · ${title}</div>
        </div>
      `;
    })
    .join("");

  list.querySelectorAll(".notify-item").forEach((itemEl) => {
    itemEl.addEventListener("click", () => {
      const key = itemEl.dataset.id;
      if (!key) return;
      openNotificationDetail(key);
    });
  });
}

function updateHeaderBadgeFromItems() {
  const badge = document.getElementById("notifyBadge");
  if (!badge) return;
  const unread = notifyItems.filter((i) => !i.is_read).length;
  badge.textContent = unread > 99 ? "99+" : String(unread);
  badge.classList.toggle("hidden", unread <= 0);
}

function removeNotifyItemByKey(itemKey) {
  const key = String(itemKey || "");
  if (!key) return;
  notifyItems = notifyItems.filter((item) => String(item._key || item.id) !== key);
  notifyItemsById = new Map(notifyItems.map((item) => [String(item._key || item.id), item]));
  renderNotifications(notifyItems);
  updateHeaderBadgeFromItems();
}

async function markMailRead(messageId) {
  try {
    const headers = await buildAuthHeaders();
    await fetch(`${window.API_BASE}/api/data/messages/${messageId}/`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ is_read: true }),
    });
  } catch (e) {
    console.warn("mark mail read failed", e);
  }
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

function openNotifyCenterByType(type, item) {
  try {
    if (item?.id) sessionStorage.setItem("openNotifyId", String(item.id));
    if (type) sessionStorage.setItem("openNotifyType", type);
    if (item?.date) sessionStorage.setItem("openNotifyDate", item.date);
  } catch (e) {
    // ignore
  }
  const page =
    type === "mail" ? "mail_center"
      : type === "attendance" ? "attendance_admin"
        : type === "vacation" ? "vacation_admin"
          : "notifications_center";
  if (typeof window.navigate === "function") {
    window.navigate(page);
    return;
  }
  if (window.nav?.go) {
    window.nav.go(page);
  } else {
    window.location.href = `${page}.html`;
  }
}

function openNotificationDetail(itemKey) {
  const detail = document.getElementById("notifyDetail");
  const list = document.getElementById("notifyList");
  const empty = document.getElementById("notifyEmpty");
  const titleEl = document.getElementById("notifyDetailTitle");
  const metaEl = document.getElementById("notifyDetailMeta");
  const contentEl = document.getElementById("notifyDetailContent");
  const deleteBtn = document.getElementById("notifyDetailDelete");
  const openBtn = document.getElementById("notifyDetailOpen");

  if (!detail || !list || !metaEl || !contentEl || !deleteBtn || !openBtn) return;

  const item = notifyItemsById.get(String(itemKey));
  if (!item) return;

  if (item._kind === "mail") {
    if (titleEl) titleEl.innerText = item.subject || "메일";
    metaEl.innerHTML = `
      <div class="meta-row"><span>보낸사람</span><span>${item.sender_name || "-"}</span></div>
      <div class="meta-row"><span>받는사람</span><span>${item.recipient_name || "-"}</span></div>
      <div class="meta-row"><span>시간</span><span>${new Date(item.created_at).toLocaleString("ko-KR")}</span></div>
    `;
    contentEl.innerText = item.content || "";
    if (!item.is_read) {
      markMailRead(item.id);
    }
    deleteBtn.textContent = "알림에서 삭제";
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      removeNotifyItemByKey(item._key || item.id);
    };
    openBtn.textContent = "메일센터 열기";
    openBtn.onclick = (e) => {
      e.stopPropagation();
      openNotifyCenterByType("mail", item);
    };
  } else {
    const alertType = classifyHeaderAlert(item);
    const dateLabel = item.date || "-";
    const remindAt = item.remind_at ? new Date(item.remind_at) : null;
    const timeLabel = remindAt && !Number.isNaN(remindAt.valueOf())
      ? remindAt.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
      : "-";

    if (alertType === "memo") {
      const clinic = item.clinic_name || "전체";
      const platform = item.platform_label || item.platform || "";
      const account = item.account || "";
      const password = item.account_password || "";
      const author = item.user_name || "-";
      if (titleEl) titleEl.innerText = `${dateLabel} 메모`;
      metaEl.innerHTML = `
        <div class="meta-row"><span>유형</span><span>메모</span></div>
        <div class="meta-row"><span>병원</span><span>${clinic}</span></div>
        <div class="meta-row"><span>알림</span><span>${dateLabel} ${timeLabel}</span></div>
        ${platform ? `<div class="meta-row"><span>플랫폼</span><span>${platform}</span></div>` : ""}
        ${account ? `<div class="meta-row"><span>ID</span><span>${account}</span></div>` : ""}
        ${password ? `<div class="meta-row"><span>PW</span><span>${password}</span></div>` : ""}
        <div class="meta-row"><span>담당자</span><span>${author}</span></div>
      `;
    } else {
      if (titleEl) {
        titleEl.innerText =
          alertType === "attendance" ? "근태 정정요청"
            : alertType === "vacation" ? "휴가 신청 알림"
              : "알림";
      }
      metaEl.innerHTML = `
        <div class="meta-row"><span>유형</span><span>${alertType === "attendance" ? "근태 정정요청" : alertType === "vacation" ? "휴가 신청" : "알림"}</span></div>
        <div class="meta-row"><span>알림</span><span>${dateLabel} ${timeLabel}</span></div>
      `;
    }
    contentEl.innerText = item.content || "";

    if (!item.is_read) {
      markNotificationRead(item.id);
    }

    deleteBtn.textContent = "알림에서 삭제";
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      removeNotifyItemByKey(item._key || item.id);
    };

    openBtn.textContent =
      alertType === "attendance" ? "근태 관리 열기"
        : alertType === "vacation" ? "휴가 관리 열기"
          : "메모함 열기";
    openBtn.onclick = (e) => {
      e.stopPropagation();
      if (alertType === "attendance") openNotifyCenterByType("attendance", item);
      else if (alertType === "vacation") openNotifyCenterByType("vacation", item);
      else openNotifyCenterByType("memo", item);
    };
  }

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
window.addEventListener("beforeunload", () => {
  if (aiCatRoamRaf) cancelAnimationFrame(aiCatRoamRaf);
  aiCatRoamRaf = null;
  aiCatRoamState = null;
});
