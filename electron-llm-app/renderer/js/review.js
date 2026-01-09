console.log("review.js loaded");

// ================================
// 전역 상태
// ================================
let state = {
  clinicId: null,
  doctorId: null,
  model: null,
  personas: [],
};

let isGenerating = false;

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
  console.log("doctors:", doctors); //디버깅 로그
  const clinicId = document.getElementById("clinicSelect").value;

  state.clinicId = clinicId;
  state.doctorId = null;

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
}

// ================================
// AI 모델
// ================================
console.log("LLM models:", models); //디버깅 로그
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

    card.innerHTML = `
      <strong>${m.name}</strong>
      <div class="meta">${(m.provider || "UNKNOWN").toUpperCase()}</div>
    `;

    card.addEventListener("click", () => {
      selectModel(m.key, card);
    });

    container.appendChild(card);

    if (!state.model && m.recommended) {
      selectModel(m.key, card);
    }
  });
}

function selectModel(modelKey, el) {
  state.model = modelKey;

  document
    .querySelectorAll(".model-card")
    .forEach(card => card.classList.remove("selected"));

  el.classList.add("selected");
}

// ================================
// 리뷰 생성
// ================================
async function generateReview() {
  if (isGenerating) return;
  if (!state.clinicId) return alert("병원을 선택하세요.");
  if (!state.model) return alert("AI 모델을 선택하세요.");

  isGenerating = true;

  const resultBox = document.getElementById("result");
  resultBox.value = "⏳ AI가 리뷰를 생성 중입니다...";

  try {
    const res = await window.api.generateReview({
      clinic_id: state.clinicId,
      doctor_id: state.doctorId,
      model: state.model,
      personas: state.personas,
    });

    resultBox.value = res.review_text || "리뷰 결과가 없습니다.";
  } catch (e) {
    console.error(e);
    resultBox.value = "❌ 리뷰 생성 실패";
  } finally {
    isGenerating = false;
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

// ================================
// 초기 실행
// ================================
window.addEventListener("DOMContentLoaded", async () => {
  await loadClinics();
  await loadModels();

  document
    .getElementById("clinicSelect")
    .addEventListener("change", onClinicChange);

  document
    .getElementById("doctorSelect")
    .addEventListener("change", (e) => {
      state.doctorId = e.target.value || null;
    });

  document
    .getElementById("personaInput")
    .addEventListener("input", (e) => {
      state.personas = e.target.value
        .split(",")
        .map(v => v.trim())
        .filter(Boolean);
    });
});

// ================================
// 전역 바인딩
// ================================
window.generateReview = generateReview;