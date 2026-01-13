console.log("review.js loaded");

let state = {
  clinicId: null,
  clinicName: null,
  modelKey: null,
  modelName: null,
  reviewType: null,
  reviewTiming: null,
  keywords: [],
  personas: [],
};

/* ---------- util ---------- */
function normalizeArray(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  if (Array.isArray(data.data)) return data.data;
  return [];
}

/* ---------- chip groups ---------- */
function setupSingleGroup(containerId, key) {
  document.querySelectorAll(`#${containerId} button`).forEach(btn => {
    btn.onclick = () => {
      const active = btn.classList.contains("active");
      document
        .querySelectorAll(`#${containerId} button`)
        .forEach(b => b.classList.remove("active"));

      state[key] = active ? null : btn.dataset.value;
      if (!active) btn.classList.add("active");

      updatePreview();
    };
  });
}

function setupMultiGroup(containerId) {
  document.querySelectorAll(`#${containerId} button`).forEach(btn => {
    btn.onclick = () => {
      btn.classList.toggle("active");
      state.keywords = Array.from(
        document.querySelectorAll(`#${containerId} .active`)
      ).map(b => b.innerText);

      updatePreview();
    };
  });
}

/* ---------- clinics ---------- */
async function loadClinics() {
  const clinics = normalizeArray(await window.api.getClinics());
  const select = clinicSelect;

  clinics.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);
  });

  select.onchange = () => {
    state.clinicId = select.value || null;
    state.clinicName =
      select.options[select.selectedIndex]?.text || null;
    updatePreview();
  };
}

/* ---------- models (🔥 가로 정렬) ---------- */
async function loadModels() {
  const models = normalizeArray(await window.api.getLLMModels());
  const container = modelList;
  container.innerHTML = "";

  models.forEach(m => {
    // 🔥 표시 이름 안전 처리
    const displayName =
      m.name || m.label || m.display_name || m.key;

    const card = document.createElement("div");
    card.className = "model-card";
    card.innerHTML = `<strong>${displayName}</strong>`;

    card.onclick = () => {
      state.modelKey = m.key;
      state.modelName = displayName; // ✅ 절대 undefined 안 됨

      document
        .querySelectorAll(".model-card")
        .forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");

      updatePreview();
    };

    container.appendChild(card);

    // 추천 모델 자동 선택
    if (!state.modelKey && m.recommended) {
      card.click();
    }
  });
}

/* ---------- persona input ---------- */
personaInput.addEventListener("input", e => {
  state.personas = e.target.value
    .split(",")
    .map(v => v.trim())
    .filter(Boolean);

  updatePreview();
});

/* ---------- preview ---------- */
function updatePreview() {
  /* ---------- 페르소나 ---------- */
  personaPreview.innerHTML = state.personas.length
    ? state.personas.map(p => `<span>${p}</span>`).join("")
    : "<span style='color:#9ca3af;font-size:12px;'>미입력</span>";

  /* ---------- 메타 정보 ---------- */
  const metaRows = [];

  if (state.clinicName) {
    metaRows.push({ label: "병원", value: state.clinicName });
  }
  if (state.modelName) {
    metaRows.push({ label: "AI 모델", value: state.modelName });
  }
  if (state.reviewType) {
    metaRows.push({ label: "리뷰 유형", value: state.reviewType });
  }
  if (state.reviewTiming) {
    metaRows.push({ label: "후기 시점", value: state.reviewTiming });
  }
  if (state.keywords.length) {
    metaRows.push({
      label: "강조 포인트",
      value: state.keywords.join(", "),
    });
  }

  previewMeta.innerHTML = metaRows.length
    ? metaRows
        .map(
          r => `
          <div class="preview-row">
            <div class="preview-label">${r.label}</div>
            <div class="preview-value">${r.value}</div>
          </div>
        `
        )
        .join("")
    : "<div style='color:#9ca3af;font-size:12px;'>선택된 설정 없음</div>";

  /* ---------- 실제 프롬프트 ---------- */
  const promptLines = [];

  if (state.personas.length) {
    promptLines.push(`페르소나: ${state.personas.join(", ")}`);
  }
  metaRows.forEach(r => {
    promptLines.push(`${r.label}: ${r.value}`);
  });

  promptLines.push(
    "",
    "위 조건을 반영해 실제 사용자가 작성한 것처럼",
    "과한 느낌 없이 자연스럽고 솔직한 후기를 작성하라."
  );

  promptPreview.innerText = promptLines.join("\n");
}

/* ---------- generate ---------- */
async function generateReview() {
  if (!state.clinicId || !state.modelKey) {
    alert("병원과 AI 모델만 선택하세요.");
    return;
  }

  openModal(); // ✅ 여기
  reviewLoading.classList.remove("hidden");
  modalReview.innerText = "";

  const res = await window.api.generateReview({
    clinic_id: state.clinicId,
    model: state.modelKey,
    context: {
      type: state.reviewType,
      timing: state.reviewTiming,
      keywords: state.keywords,
      personas: state.personas,
    },
  });

  reviewLoading.classList.add("hidden");
  modalReview.innerText = res.review_text || "";
}

/* ---------- modal ---------- */
function closeModal() {
  reviewModal.classList.add("hidden");
}

/* ---------- init ---------- */
window.addEventListener("DOMContentLoaded", async () => {
  setupSingleGroup("reviewType", "reviewType");
  setupSingleGroup("reviewTiming", "reviewTiming");
  setupMultiGroup("keywordGroup");

  await loadClinics();
  await loadModels();
});

function openModal() {
  document.body.style.overflow = "hidden"; // 🔥 배경 스크롤 차단
  reviewModal.classList.remove("hidden");
}

function closeModal() {
  document.body.style.overflow = ""; // 원래대로 복구
  reviewModal.classList.add("hidden");
}

reviewModal.addEventListener("wheel", (e) => {
  e.stopPropagation();
}, { passive: false });

reviewModal.addEventListener("touchmove", (e) => {
  e.stopPropagation();
}, { passive: false });

/* ---------- global ---------- */
window.generateReview = generateReview;
window.closeModal = closeModal;
