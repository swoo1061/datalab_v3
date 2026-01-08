// js/clinic_guide.js

const API_BASE = "http://127.0.0.1:8000";

/** TODO: 실제 리스트 API에 맞게 수정 */
async function fetchClinics() {
  // 예: /dashboard/api/clinics/
  // return fetchJson("/dashboard/api/clinics/");
  return [
    { id: 1, name: "샘플 병원 A" },
    { id: 2, name: "샘플 병원 B" },
  ];
}

async function fetchClinicDetail(id) {
  // 실제: /dashboard/api/clinics/<id>/detail/
  // return fetchJson(`/dashboard/api/clinics/${id}/detail/`);

  // 샘플 데이터 (구조 맞춤)
  return {
    clinic: {
      id,
      name: id === 1 ? "샘플 병원 A" : "샘플 병원 B",
      location: "서울 강남구",
      hours: "10:00 - 19:00",
      parking: "가능",
      process: "상담 → 진단 → 시술",
    },
    doctors: id === 1
      ? [{ id: "d1", name: "김원장", specialty: "코/윤곽" }, { id: "d2", name: "이원장", specialty: "눈" }]
      : [],
    price_list: [
      { id: "p1", item: "코 기본", category: "코", doctor_id: "d1", price: 3500000 },
      { id: "p2", item: "눈 자연유착", category: "눈", doctor_id: "d2", price: null },
      { id: "p3", item: "공통 상담", category: "상담", doctor_id: null, price: null },
    ],
    consultants: [{ name: "박상담", role: "실장" }],
    aftercare: [{ name: "사후 케어 1" }, { name: "사후 케어 2" }],
  };
}

async function fetchJson(path) {
  const res = await fetch(API_BASE + path, { credentials: "include" });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data?.message || `HTTP ${res.status}`);
  return data;
}

// ---------- UI ----------
let currentDetail = null;
let currentDoctorKey = null; // "doctor:<id>" or "common"

function formatPrice(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  if (Number.isNaN(n)) return null;
  return n.toLocaleString("ko-KR") + "원";
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? "-";
}

function renderClinicInfo(detail) {
  const c = detail.clinic || {};
  setText("clinicName", c.name || "-");
  setText("clinicLocation", c.location || "-");
  setText("clinicHours", c.hours || "-");
  setText("clinicParking", c.parking || "-");
  setText("clinicProcess", c.process || "-");

  const badge = document.getElementById("clinicIdBadge");
  if (badge) badge.textContent = `ID ${c.id ?? "-"}`;
}

function buildDoctorTabs(detail) {
  const wrap = document.getElementById("doctorTabs");
  wrap.innerHTML = "";

  const doctors = Array.isArray(detail.doctors) ? detail.doctors : [];
  const hasCommon = (detail.price_list || []).some(p => !p.doctor_id);

  // 의사 탭
  doctors.forEach(d => {
    const btn = document.createElement("div");
    btn.className = "nav-item";
    btn.dataset.key = `doctor:${d.id}`;
    btn.innerHTML = `
      <span>${d.name}</span>
      <span class="badge">${d.specialty || "의료진"}</span>
    `;
    btn.onclick = () => selectDoctor(btn.dataset.key);
    wrap.appendChild(btn);
  });

  // 원장 없는 병원/공통 수가 탭
  if (hasCommon || doctors.length === 0) {
    const btn = document.createElement("div");
    btn.className = "nav-item";
    btn.dataset.key = "common";
    btn.innerHTML = `
      <span>공통 수가</span>
      <span class="badge">의료진 없음/공통</span>
    `;
    btn.onclick = () => selectDoctor("common");
    wrap.appendChild(btn);
  }

  // 기본 선택
  if (doctors.length > 0) selectDoctor(`doctor:${doctors[0].id}`);
  else selectDoctor("common");
}

function selectDoctor(key) {
  currentDoctorKey = key;

  // active UI
  document.querySelectorAll(".clinic-page .nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.key === key);
  });

  renderPriceTable(currentDetail, key);
}

function renderPriceTable(detail, key) {
  const tbody = document.getElementById("priceTbody");
  tbody.innerHTML = "";

  const doctors = Array.isArray(detail.doctors) ? detail.doctors : [];
  const prices = Array.isArray(detail.price_list) ? detail.price_list : [];

  let doctor = null;
  if (key?.startsWith("doctor:")) {
    const id = key.split(":")[1];
    doctor = doctors.find(d => String(d.id) === String(id)) || null;
  }

  const filtered = prices.filter(p => {
    if (key === "common") return !p.doctor_id;
    if (!doctor) return false;
    return String(p.doctor_id) === String(doctor.id);
  });

  // 제목
  const title = document.getElementById("doctorTitle");
  if (title) title.textContent = key === "common" ? "공통 수가" : (doctor?.name || "-");

  // count badge
  const count = document.getElementById("priceCount");
  if (count) count.textContent = `항목 ${filtered.length}`;

  // 렌더
  if (filtered.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td colspan="4" class="muted" style="padding:14px;">
        표시할 수가 정보가 없습니다.
      </td>
    `;
    tbody.appendChild(tr);
    return;
  }

  filtered.forEach(p => {
    const tr = document.createElement("tr");
    const priceText = formatPrice(p.price);
    tr.innerHTML = `
      <td><b>${p.item || "-"}</b></td>
      <td>${p.category || "-"}</td>
      <td>${key === "common" ? "공통" : (doctor?.name || "-")}</td>
      <td class="price">${priceText ? priceText : `<span class="need-consult">상담 필요</span>`}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderConsultants(detail) {
  const root = document.getElementById("consultants");
  const list = Array.isArray(detail.consultants) ? detail.consultants : [];
  if (list.length === 0) { root.textContent = "-"; return; }

  root.innerHTML = list.map(c => `<span class="pill">${c.name || "상담"} ${c.role ? "· " + c.role : ""}</span>`).join("");
}

function renderAftercare(detail) {
  const root = document.getElementById("aftercare");
  const list = Array.isArray(detail.aftercare) ? detail.aftercare : [];
  if (list.length === 0) { root.textContent = "-"; return; }

  root.innerHTML = list.map(a => `<span class="pill">${a.name || "-"}</span>`).join("");
}

async function loadClinicPage() {
  const select = document.getElementById("clinicSelect");
  const clinics = await fetchClinics();

  select.innerHTML = clinics.map(c => `<option value="${c.id}">${c.name}</option>`).join("");

  select.onchange = async () => {
    const id = select.value;
    await loadDetail(id);
  };

  // default
  if (clinics.length > 0) {
    select.value = clinics[0].id;
    await loadDetail(clinics[0].id);
  }
}

async function loadDetail(id) {
  currentDetail = await fetchClinicDetail(id);

  renderClinicInfo(currentDetail);
  buildDoctorTabs(currentDetail);
  renderConsultants(currentDetail);
  renderAftercare(currentDetail);
}

function reloadClinic() {
  const select = document.getElementById("clinicSelect");
  if (select?.value) loadDetail(select.value);
}

// init
loadClinicPage().catch(err => {
  console.error(err);
  alert("병원 가이드 로드 실패: " + err.message);
});
