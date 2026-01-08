console.log("review.js loaded");

// ================================
// 전역 상태
// ================================
let state = {
  clinicId: null,
  doctorId: null,
  model: null,
};

// ================================
// 병원 목록
// ================================
async function loadClinics() {
  const clinics = await window.api.getClinics();
  const select = document.getElementById("clinicSelect");

  select.innerHTML = '<option value="">병원을 선택하세요</option>';

  clinics.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);
  });
}

// ================================
// 병원 → 원장
// ================================
async function onClinicChange() {
  const clinicId = document.getElementById("clinicSelect").value;
  state.clinicId = clinicId;

  const doctorSelect = document.getElementById("doctorSelect");
  doctorSelect.innerHTML = '<option value="">원장님을 선택하세요</option>';
  doctorSelect.disabled = true;

  if (!clinicId) return;

  const doctors = await window.api.getDoctors(clinicId);
  doctorSelect.disabled = false;

  doctors.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = d.name;
    doctorSelect.appendChild(opt);
  });

  doctorSelect.onchange = () => {
    state.doctorId = doctorSelect.value;
  };
}

// ================================
// AI 모델
// ================================
async function loadModels() {
  const models = await window.api.getLLMModels();
  const container = document.getElementById("modelList");
  container.innerHTML = "";

  if (!Array.isArray(models)) {
    container.innerHTML = "<div>모델 목록 로드 실패</div>";
    return;
  }

  models.forEach(m => {
    const card = document.createElement("div");
    card.className = "model-card";
    if (m.recommended) card.classList.add("recommended");

    card.innerHTML = `
      <strong>${m.name}</strong>
      <div class="meta">${(m.provider || "UNKNOWN").toUpperCase()}</div>
    `;

    card.onclick = (e) => selectModel(m.key, e);
    container.appendChild(card);

    if (!state.model && m.recommended) {
      selectModel(m.key, { currentTarget: card });
    }
  });
}

function selectModel(modelKey, event) {
  state.model = modelKey;

  document
    .querySelectorAll(".model-card")
    .forEach(el => el.classList.remove("selected"));

  event.currentTarget.classList.add("selected");
}

// ================================
// 리뷰 생성
// ================================
async function generateReview() {
  if (!state.clinicId) return alert("병원을 선택하세요.");
  if (!state.model) return alert("AI 모델을 선택하세요.");

  const resultBox = document.getElementById("result");
  resultBox.value = "리뷰 생성 중...";

  try {
    const res = await window.api.generateReview({
      clinic_id: state.clinicId,
      doctor_id: state.doctorId,
      model: state.model,
    });
    resultBox.value = res.review_text;
  } catch (e) {
    console.error(e);
    resultBox.value = "리뷰 생성 실패";
  }
}

// ================================
// 유틸
// ================================
function copyResult() {
  navigator.clipboard.writeText(
    document.getElementById("result").value
  );
}

function navigate(page) {
  if (window.nav?.go) window.nav.go(page);
  else window.location.href = `${page}.html`;
}

function goDashboard() {
  navigate("dashboard");
}

// ================================
// 초기 실행
// ================================
window.addEventListener("DOMContentLoaded", async () => {
  await loadClinics();
  await loadModels();
});

// ================================
// 전역 바인딩
// ================================
window.onClinicChange = onClinicChange;
window.generateReview = generateReview;
window.goDashboard = goDashboard;
