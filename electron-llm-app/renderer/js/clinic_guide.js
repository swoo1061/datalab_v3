console.log("clinic_guide.js loaded");
console.log("query =", window.location.search);


/* ================================
   상태
================================ */
let currentClinic = null;
let currentDoctorKey = null;
let currentSachiClinic = "";
let currentSachiProfiles = [];

const SACHI_SUB_CLINICS = [
  "루미의원",
  "부평란의원",
  "미앤미 강남점",
  "데이뷰의원",
  "하오덤의원",
  "프리미의원",
];

/* ================================
   API
================================ */
async function fetchClinics() {
  return await window.api.getClinics();
}

async function fetchClinicDetail(id) {
  return await window.api.getClinicDetail(id);
}

/* ================================
   URL 유틸 (추가)
================================ */
function getClinicIdFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("clinic_id");
  console.log("🔥 clinic_id from query =", id);
  return id;
}

/* ================================
   초기 로드
================================ */


async function initClinicGuide() {
  try {
    setupSachiAccordion();
    const clinics = await fetchClinics();
    renderClinicNav(clinics);

    const clinicIdFromQuery = getClinicIdFromQuery();

    if (clinicIdFromQuery) {
      await loadClinic(clinicIdFromQuery);
      return;
    }

    if (clinics.length > 0) {
      await loadClinic(clinics[0].id);
    }
  } catch (e) {
    console.error(e);
    window.showAlert?.("병원 목록을 불러오지 못했습니다.");
  }
}

/* ================================
   병원 선택
================================ */
function renderClinicNav(clinics) {
  const wrap = document.getElementById("clinicNavList");
  const count = document.getElementById("clinicNavCount");
  if (!wrap) return;

  wrap.innerHTML = clinics.map((clinic) => `
    <button type="button" class="clinic-nav-item" data-clinic-id="${clinic.id}">
      ${clinic.name}
    </button>
  `).join("");
  if (count) count.textContent = String(clinics.length);

  wrap.querySelectorAll(".clinic-nav-item").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const clinicId = btn.dataset.clinicId;
      if (!clinicId) return;
      await loadClinic(clinicId);
    });
  });
}

function setGuideTitle(name) {
  const titleEl = document.querySelector(".topbar .h1");
  if (titleEl) {
    titleEl.innerText = `${name} 가이드`;
  }
}

/* ================================
   병원 상세 로드
================================ */
async function loadClinic(clinicId) {
  try {
    currentClinic = await fetchClinicDetail(clinicId);
  } catch (e) {
    console.error(e);
    window.showAlert?.("병원 가이드 로드 실패");
    return;
  }

  renderClinicInfo(currentClinic);
  renderClinicSpecial(currentClinic);
  renderDoctorTabs(currentClinic);
  renderConsultants(currentClinic);
  renderAftercare(currentClinic);
  syncActiveClinicNav(clinicId);
}

function syncActiveClinicNav(clinicId) {
  document.querySelectorAll(".clinic-nav-item").forEach((item) => {
    item.classList.toggle("active", String(item.dataset.clinicId) === String(clinicId));
  });
}

/* ================================
   기본 정보
================================ */
function renderClinicInfo(data) {
  const c = data.clinic || {};
  setText("clinicName", c.name);
  setText("clinicLocation", c.location);
  setText("clinicHours", formatHoursText(c.hours));
  setText("clinicParking", c.parking);
  setText("clinicProcess", c.process);
}

function formatHoursText(value) {
  const raw = String(value || "").replace(/\r\n?/g, "\n").trim();
  if (!raw) return "-";
  if (raw.includes("\n")) return raw;
  return raw.replace(/\s*,\s*/g, "\n");
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || "-";
}

function setHtml(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html || "-";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function toRichBlock(text) {
  const lines = String(text || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) return '<p class="muted">정보가 없습니다.</p>';

  const bullets = [];
  const paragraphs = [];
  for (const line of lines) {
    if (/^[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*]\s+/, "").trim());
    } else {
      paragraphs.push(line);
    }
  }

  let html = paragraphs.map((line) => `<p>${escapeHtml(line)}</p>`).join("");
  if (bullets.length) {
    html += `<ul>${bullets.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>`;
  }
  return html || '<p class="muted">정보가 없습니다.</p>';
}

function toKeywordChips(text) {
  const tags = Array.from(
    new Set(
      String(text || "")
        .replace(/\r\n?/g, "\n")
        .split(/[\s,\n]+/)
        .map((t) => t.trim())
        .filter((t) => t.startsWith("#") && t.length > 1)
    )
  );
  if (!tags.length) return toRichBlock(text);
  return `<div class="keyword-chips">${tags
    .map((tag) => `<span class="keyword-chip">${escapeHtml(tag)}</span>`)
    .join("")}</div>`;
}

function toLabeledList(text) {
  const lines = String(text || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return '<p class="muted">정보가 없습니다.</p>';

  const items = lines.map((line) => {
    const m = line.match(/^(.{1,40}?)\s*:\s*(.+)$/);
    if (!m) return `<li>${escapeHtml(line)}</li>`;
    return `<li><b>${escapeHtml(m[1])}</b>: ${escapeHtml(m[2])}</li>`;
  });
  return `<ul class="labeled-list">${items.join("")}</ul>`;
}

function toPriceGuideBlocks(text) {
  const raw = String(text || "").replace(/\r\n?/g, "\n").trim();
  if (!raw) return '<p class="muted">정보가 없습니다.</p>';

  const chunks = raw
    .split(/\n\s*\n+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);
  if (!chunks.length) return toRichBlock(raw);

  const blocks = chunks.map((chunk) => {
    const lines = chunk
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) return "";

    const head = lines[0];
    const details = lines.slice(1);
    const detailHtml = details.length
      ? `<ul>${details.map((d) => `<li>${escapeHtml(d.replace(/^[-*]\s+/, ""))}</li>`).join("")}</ul>`
      : "";

    return `
      <article class="price-guide-block">
        <div class="price-guide-title">${escapeHtml(head)}</div>
        ${detailHtml}
      </article>
    `;
  });

  return `<div class="price-guide-grid">${blocks.join("")}</div>`;
}

function splitTextBySubClinic(text) {
  const lines = String(text || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const map = {};
  SACHI_SUB_CLINICS.forEach((name) => {
    map[name] = [];
  });

  let current = "";
  for (const line of lines) {
    const matched = SACHI_SUB_CLINICS.find((name) => line.includes(name));
    if (matched) {
      current = matched;
      map[current].push(line);
      continue;
    }
    if (current) map[current].push(line);
  }
  return map;
}

function buildSachiProfiles(data) {
  const splitCommunity = splitTextBySubClinic(data.community);
  const splitPrice = splitTextBySubClinic(data.priceGuide);

  return SACHI_SUB_CLINICS.map((name) => ({
    name,
    productIntro: data.productIntro || "",
    timeline: data.timeline || "",
    keywords: data.keywords || "",
    community: (splitCommunity[name] || []).join("\n").trim(),
    priceGuide: (splitPrice[name] || []).join("\n").trim(),
  }));
}

function renderSachiClinicNav(profiles) {
  const nav = document.getElementById("sachiClinicNav");
  if (!nav) return;
  nav.innerHTML = profiles
    .map((p) => {
      const active = p.name === currentSachiClinic ? "active" : "";
      const hasAny = Boolean(p.community || p.priceGuide || p.productIntro || p.timeline || p.keywords);
      const muted = hasAny ? "" : "muted";
      return `<button type="button" class="sachi-clinic-btn ${active} ${muted}" data-name="${escapeHtml(p.name)}">${escapeHtml(p.name)}</button>`;
    })
    .join("");
}

function drawSachiProfile(name) {
  const row = currentSachiProfiles.find((p) => p.name === name) || currentSachiProfiles[0];
  if (!row) return;
  currentSachiClinic = row.name;

  setHtml("sachiProductIntro", `<div class="sachi-rich">${toRichBlock(row.productIntro || "제품 소개 정보가 없습니다.")}</div>`);
  setHtml("sachiTimeline", `<div class="sachi-rich">${toRichBlock(row.timeline || "기전/타임라인 정보가 없습니다.")}</div>`);
  setHtml("sachiKeywords", `<div class="sachi-rich">${toKeywordChips(row.keywords || "제품 키워드 정보가 없습니다.")}</div>`);
  setHtml("sachiCommunity", `<div class="sachi-rich">${toLabeledList(row.community || "커뮤니티 참고사항이 없습니다.")}</div>`);
  setHtml("sachiPriceGuide", `<div class="sachi-rich">${toPriceGuideBlocks(row.priceGuide || "수가표 정보가 없습니다.")}</div>`);

  const nav = document.getElementById("sachiClinicNav");
  nav?.querySelectorAll(".sachi-clinic-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.name === currentSachiClinic);
  });
}

/* ================================
   의료진 탭
================================ */
function renderDoctorTabs(data) {
  const wrap = document.getElementById("doctorTabs");
  if (!wrap) return;

  wrap.innerHTML = "";

  const doctors = Array.isArray(data.doctors) ? data.doctors : [];
  const prices = Array.isArray(data.price_list) ? data.price_list : [];

  doctors.forEach(d => {
    const tab = document.createElement("div");
    tab.className = "nav-item";
    tab.dataset.key = d.code || d.name;
    tab.innerHTML = `<span>${d.name}</span>`;
    tab.onclick = () => selectDoctor(tab.dataset.key);
    wrap.appendChild(tab);
  });

  if (prices.some(p => !p.doctor_code)) {
    const tab = document.createElement("div");
    tab.className = "nav-item";
    tab.dataset.key = "common";
    tab.innerHTML = `<span>공통 수가</span>`;
    tab.onclick = () => selectDoctor("common");
    wrap.appendChild(tab);
  }

  if (doctors.length > 0) {
    selectDoctor(doctors[0].code || doctors[0].name);
  } else {
    selectDoctor("common");
  }
}

function selectDoctor(key) {
  currentDoctorKey = key;

  document.querySelectorAll(".nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.key === key);
  });

  renderPriceTable(currentClinic, key);
}

/* ================================
   수가
================================ */
function renderPriceTable(data, key) {
  const tbody = document.getElementById("priceTbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const prices = Array.isArray(data.price_list) ? data.price_list : [];

  const filtered = prices.filter(p => {
    if (key === "common") return !p.doctor_code;
    return p.doctor_code === key;
  });

  setDoctorHeader(data, key, filtered.length);

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="4" class="muted">표시할 수가 정보가 없습니다.</td>
      </tr>
    `;
    return;
  }

  for (let i = 0; i < filtered.length; i += 2) {
    const left = filtered[i];
    const right = filtered[i + 1];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="procedure">${left?.procedure || "-"}</td>
      <td class="price">${left?.price_display || "상담 필요"}</td>
      <td class="procedure">${right?.procedure || "-"}</td>
      <td class="price">${right?.price_display || (right ? "상담 필요" : "-")}</td>
    `;
    tbody.appendChild(tr);
  }
}

function setDoctorHeader(data, key, count) {
  const titleEl = document.getElementById("doctorTitle");
  const countEl = document.getElementById("priceCount");
  const doctors = Array.isArray(data.doctors) ? data.doctors : [];
  let label = "공통 수가";

  if (key !== "common") {
    const found = doctors.find(d => (d.code || d.name) === key);
    label = found?.name || key;
  }

  if (titleEl) titleEl.textContent = label;
  if (countEl) countEl.textContent = `${count}개 항목`;
}

/* ================================
   기타 정보
================================ */
function renderConsultants(data) {
  const root = document.getElementById("consultants");
  if (!root) return;

  const list = Array.isArray(data.consultants) ? data.consultants : [];

  if (list.length === 0) {
    root.textContent = "-";
    return;
  }

  root.innerHTML = list.map(c => `
    <div class="consultant-card">
      <div class="consultant-name">${c.name}</div>
      ${c.style ? `<div class="consultant-style">${c.style}</div>` : ""}
    </div>
  `).join("");
}

function renderAftercare(data) {
  const el = document.getElementById("aftercare");
  if (!el) return;

  el.innerHTML = (data.aftercare || []).map(
    a => `<span class="pill">${a}</span>`
  ).join("") || "-";
}

function isSachibioClinic(data) {
  const name = String(data?.clinic?.name || "").replace(/\s+/g, "");
  return name.includes("사치바이오");
}

function pickRawValue(raw, keys) {
  for (const key of keys) {
    const value = raw?.[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function renderClinicSpecial(data) {
  const special = document.getElementById("sachibioSpecial");
  const defaultMain = document.getElementById("guideMainDefault");
  const defaultSupport = document.getElementById("guideSupportDefault");
  if (!special || !defaultMain || !defaultSupport) return;

  if (!isSachibioClinic(data)) {
    special.classList.add("hidden");
    defaultMain.classList.remove("hidden");
    defaultSupport.classList.remove("hidden");
    return;
  }

  const raw = data?.raw_data || {};
  const productIntro =
    pickRawValue(raw, ["제품소개", "제품 소개", "product_intro"]) ||
    "제품 소개 정보가 없습니다.";
  const timeline =
    pickRawValue(raw, ["제품 기전 및 타임라인별 소구포인트", "제품 기전 및 타임라인별 소구 포인트", "timeline_points"]) ||
    "기전/타임라인 정보가 없습니다.";
  const keywords =
    pickRawValue(raw, ["제품 키워드", "product_keywords"]) ||
    "제품 키워드 정보가 없습니다.";
  const community =
    pickRawValue(raw, ["커뮤니티 참고사항", "community_notes"]) ||
    "커뮤니티 참고사항이 없습니다.";
  const priceGuide =
    pickRawValue(raw, ["수가표", "price_guide"]) ||
    "수가표 정보가 없습니다.";
  currentSachiProfiles = buildSachiProfiles({ productIntro, timeline, keywords, community, priceGuide });
  currentSachiClinic = currentSachiProfiles[0]?.name || "";
  renderSachiClinicNav(currentSachiProfiles);
  drawSachiProfile(currentSachiClinic);

  special.classList.remove("hidden");
  defaultMain.classList.add("hidden");
  defaultSupport.classList.add("hidden");
  collapseSachiPanels();
}

function setupSachiAccordion() {
  const special = document.getElementById("sachibioSpecial");
  if (!special) return;
  special.addEventListener("click", (e) => {
    const clinicBtn = e.target.closest(".sachi-clinic-btn");
    if (clinicBtn) {
      drawSachiProfile(clinicBtn.dataset.name || "");
      return;
    }
    const btn = e.target.closest(".accordion-btn");
    if (!btn) return;
    const id = btn.dataset.target;
    const panel = id ? document.getElementById(id) : null;
    if (!panel) return;
    const isCollapsed = panel.classList.toggle("collapsed");
    btn.textContent = isCollapsed ? "열기" : "닫기";
  });
}

function collapseSachiPanels() {
  const special = document.getElementById("sachibioSpecial");
  if (!special) return;
  const panels = Array.from(special.querySelectorAll(".panel-bd"));
  const buttons = Array.from(special.querySelectorAll(".accordion-btn"));
  panels.forEach((panel, idx) => {
    const keepOpen = idx === 0;
    panel.classList.toggle("collapsed", !keepOpen);
  });
  buttons.forEach((btn, idx) => {
    btn.textContent = idx === 0 ? "닫기" : "열기";
  });
}

/* ================================
   시작
================================ */
window.addEventListener("DOMContentLoaded", initClinicGuide);
