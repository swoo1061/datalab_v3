console.log("clinic_guide.js loaded");
console.log("query =", window.location.search);


/* ================================
   상태
================================ */
let currentClinic = null;
let currentDoctorKey = null;

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
    const clinics = await fetchClinics();
    renderClinicSelect(clinics);

    const clinicIdFromQuery = getClinicIdFromQuery();

    if (clinicIdFromQuery) {
      await loadClinic(clinicIdFromQuery);
      hideClinicSelect();
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
function renderClinicSelect(clinics) {
  const select = document.getElementById("clinicSelect");
  if (!select) return;

  select.innerHTML = "";

  clinics.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);
  });

  select.onchange = async () => {
    await loadClinic(select.value);
  };
}

function hideClinicSelect() {
  const el = document.getElementById("clinicSelect");
  if (el) el.style.display = "none";
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
  renderDoctorTabs(currentClinic);
  renderConsultants(currentClinic);
  renderAftercare(currentClinic);
}

/* ================================
   기본 정보
================================ */
function renderClinicInfo(data) {
  const c = data.clinic || {};
  setText("clinicName", c.name);
  setText("clinicLocation", c.location);
  setText("clinicHours", c.hours);
  setText("clinicParking", c.parking);
  setText("clinicProcess", c.process);
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || "-";
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
        <td colspan="2" class="muted">표시할 수가 정보가 없습니다.</td>
      </tr>
    `;
    return;
  }

  filtered.forEach(p => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b>${p.procedure || "-"}</b></td>
      <td class="price">${p.price_display || "상담 필요"}</td>
    `;
    tbody.appendChild(tr);
  });
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

/* ================================
   시작
================================ */
window.addEventListener("DOMContentLoaded", initClinicGuide);
