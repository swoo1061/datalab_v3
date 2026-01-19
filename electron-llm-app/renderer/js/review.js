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
  if (data?.results) return data.results;
  if (data?.data) return data.data;
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
      state.keywords = [...document.querySelectorAll(`#${containerId} .active`)]
        .map(b => b.innerText);
      updatePreview();
    };
  });
}

/* ---------- clinics ---------- */
async function loadClinics() {
  const clinics = normalizeArray(await window.api.getClinics());

  clinics.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    clinicSelect.appendChild(opt);
  });

  clinicSelect.onchange = async () => {
    state.clinicId = clinicSelect.value || null;
    state.clinicName =
      clinicSelect.options[clinicSelect.selectedIndex]?.text || null;

    if (state.clinicId) {
      try {
        state.clinicGuide = await window.api.getClinicGuide(state.clinicId);
      } catch (e) {
        console.error("❌ clinic guide load error:", e);
        state.clinicGuide = null;
      }
    } else {
      state.clinicGuide = null;
    }

    updatePreview();
  };

  const queryClinicId = new URLSearchParams(window.location.search).get("clinic_id");
  if (queryClinicId) {
    clinicSelect.value = queryClinicId;
    clinicSelect.onchange();
  }
}

/* ---------- models ---------- */
async function loadModels() {
  const models = normalizeArray(await window.api.getLLMModels());
  modelList.innerHTML = "";

  models.forEach(m => {
    const displayName = m.label || m.name || m.key;

    const card = document.createElement("div");
    card.className = "model-card";
    card.innerHTML = `<strong>${displayName}</strong>`;

    card.onclick = () => {
      state.modelKey = m.key;
      state.modelName = displayName;

      document
        .querySelectorAll(".model-card")
        .forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");

      updatePreview();
    };

    modelList.appendChild(card);

    if (!state.modelKey && m.recommended) card.click();
  });
}

/* ---------- persona ---------- */
personaInput.addEventListener("input", e => {
  state.personas = e.target.value
    .split(",")
    .map(v => v.trim())
    .filter(Boolean);

  updatePreview();
});

/* ---------- preview ---------- */
function updatePreview() {
  personaPreview.innerHTML = state.personas.length
    ? state.personas.map(p => `<span>${p}</span>`).join("")
    : "<span class='muted'>미입력</span>";

  const rows = [];
  if (state.clinicName) rows.push({ label: "병원", value: state.clinicName });
  if (state.modelName) rows.push({ label: "AI 모델", value: state.modelName });
  if (state.reviewType) rows.push({ label: "리뷰 유형", value: state.reviewType });
  if (state.reviewTiming) rows.push({ label: "후기 시점", value: state.reviewTiming });
  if (state.keywords.length)
    rows.push({ label: "강조", value: state.keywords.join(", ") });

  previewMeta.innerHTML = rows.length
    ? rows.map(r => `
        <div class="preview-row">
          <div class="preview-label">${r.label}</div>
          <div class="preview-value">${r.value}</div>
        </div>
      `).join("")
    : "<span class='muted'>선택된 조건 없음</span>";

  promptPreview.innerText =
    "※ 실제 프롬프트는 병원 가이드 + 선택 조건을 기반으로 프론트에서 생성됩니다.";
}

/* ---------- 🔥 PROMPT BUILD ---------- */
function buildPrompt() {
  const lines = [];

  lines.push(`병원명: ${state.clinicName}`);
  if (state.reviewType) lines.push(`리뷰 유형: ${state.reviewType}`);
  if (state.reviewTiming) lines.push(`후기 시점: ${state.reviewTiming}`);

  if (state.personas.length) {
    lines.push(`작성자 페르소나: ${state.personas.join(", ")}`);
  }

  if (state.keywords.length) {
    lines.push(`강조 키워드: ${state.keywords.join(", ")}`);
  }

  if (state.clinicGuide) {
    lines.push("");
    lines.push("병원 가이드:");
    lines.push(JSON.stringify(state.clinicGuide, null, 2));
  }

  lines.push("");
  lines.push(
    "위 조건을 반영하여 실제 고객이 작성한 것처럼 자연스럽고 솔직한 리뷰를 작성하라."
  );

  return lines.join("\n");
}

/* ---------- generate ---------- */
async function generateReview() {
  if (!state.modelKey) {
    alert("AI 모델을 선택하세요.");
    return;
  }

  const btn = document.getElementById("generateReviewBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "리뷰 생성 중...";
  }
  forceInteractive();
  startInteractionWatchdog();
  modalReview.innerText = "";
  let ok = false;

  // ✅ 서버가 요구하는 단 하나의 입력
  const prompt = `
병원: ${state.clinicName || "미선택"}
리뷰 유형: ${state.reviewType || "일반 후기"}
후기 시점: ${state.reviewTiming || "미지정"}
강조 포인트: ${state.keywords.join(", ") || "없음"}
페르소나: ${state.personas.join(", ") || "없음"}

위 조건을 반영해 실제 사용자가 작성한 것처럼
자연스럽고 솔직한 후기를 작성해주세요.
  `.trim();

  const payload = {
    model: state.modelKey,
    context: {
      prompt, // 🔥 이거 하나면 끝
    },
  };

  try {
    const res = await window.api.generateReview(payload);
    modalReview.innerText = res.review_text || "";
    openModal();
    ok = true;
  } catch (e) {
    console.error("❌ generateReview error:", e);
    alert("리뷰 생성 실패");
    forceCloseModal();
    clearModalOverlays();
  } finally {
    reviewLoading.classList.add("hidden");
    if (btn) {
      btn.disabled = false;
      btn.innerText = "리뷰 생성";
    }
    if (!ok) {
      forceCloseModal();
      clearModalOverlays();
    }
  }
}

/* ---------- modal ---------- */
function flashCopy(btn) {
  if (!btn) return;
  const original = btn.dataset.originalText || btn.innerText;
  btn.dataset.originalText = original;
  btn.innerText = "복사됨!";
  if (btn._copyTimer) clearTimeout(btn._copyTimer);
  btn._copyTimer = setTimeout(() => {
    btn.innerText = original;
  }, 1200);
}

function openModal() {
  document.body.style.overflow = "hidden";
  reviewModal.classList.remove("hidden");
}

function closeModal() {
  document.body.style.overflow = "";
  reviewModal.classList.add("hidden");
}

function forceCloseModal() {
  document.body.style.overflow = "";
  if (reviewModal) {
    reviewModal.classList.add("hidden");
    reviewModal.style.display = "none";
    requestAnimationFrame(() => {
      reviewModal.style.display = "";
    });
  }
}

function clearModalOverlays() {
  document.body.style.overflow = "";
  document.body.style.pointerEvents = "auto";
  document.querySelectorAll(".modal, .modal-backdrop").forEach((el) => {
    el.classList.add("hidden");
    el.style.display = "none";
    el.style.pointerEvents = "none";
    requestAnimationFrame(() => {
      el.style.display = "";
      el.style.pointerEvents = "";
    });
  });
}

function forceInteractive() {
  document.body.style.pointerEvents = "auto";
  document.querySelectorAll("input, select, textarea").forEach((el) => {
    el.disabled = false;
    el.style.pointerEvents = "auto";
  });
  clearModalOverlays();
}

function startInteractionWatchdog() {
  const start = Date.now();
  const tick = () => {
    const hasVisibleModal = document.querySelector(".modal:not(.hidden)");
    if (!hasVisibleModal) {
      forceInteractive();
    }
    if (Date.now() - start < 10000) {
      setTimeout(tick, 500);
    }
  };
  setTimeout(tick, 0);
}

/* ---------- init ---------- */
window.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("copyModalBtn")?.addEventListener("click", () => {
    const text = modalReview?.innerText || "";
    navigator.clipboard.writeText(text);
    flashCopy(document.getElementById("copyModalBtn"));
  });

  setupSingleGroup("reviewType", "reviewType");
  setupSingleGroup("reviewTiming", "reviewTiming");
  setupMultiGroup("keywordGroup");

  await loadClinics();
  await loadModels();
});

/* ---------- global ---------- */
window.generateReview = generateReview;
window.closeModal = closeModal;
