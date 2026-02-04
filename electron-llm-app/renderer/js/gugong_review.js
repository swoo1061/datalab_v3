console.log("gugong_review.js loaded");

let state = {
  clinicId: null,
  clinicName: null,
  modelKey: "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
  modelName: "구공이(V_3)",
  currentReviewId: null,

  reviewIntent: "자연스러운 후기",
  ageGroup: "20대 후반",
  mbti: "INFP",
  tonePreset: "자연스럽고 담백한 톤",
  keywords: [],
  forbiddenKeywords: [],
  personas: [],
};

/* ---------- util ---------- */
function normalizeArray(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  if (data?.data) return data.data;
  return [];
}

const MBTI_RE = /\b(ISTJ|ISFJ|INFJ|INTJ|ISTP|ISFP|INFP|INTP|ESTP|ESFP|ENFP|ENTP|ESTJ|ESFJ|ENFJ|ENTJ)\b/i;
function extractMbtiFromText(text) {
  const m = String(text || "").match(MBTI_RE);
  return m ? m[1].toUpperCase() : null;
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
      const selected = [...document.querySelectorAll(`#${containerId} .active`)]
        .map(b => b.innerText.trim());
      if (containerId === "keywordGroup") state.keywords = selected;
      if (containerId === "forbiddenGroup") state.forbiddenKeywords = selected;
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

  const gugong = models.find(m => m.key === state.modelKey) || {
    key: state.modelKey,
    label: state.modelName,
  };

  const card = document.createElement("div");
  card.className = "model-card selected";
  card.innerHTML = `<strong>${gugong.label || gugong.name || gugong.key}</strong>`;
  card.style.pointerEvents = "none";
  card.style.opacity = "0.8";
  modelList.appendChild(card);

  state.modelName = gugong.label || gugong.name || gugong.key;
  updatePreview();
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
  if (state.reviewIntent) rows.push({ label: "글 목적", value: state.reviewIntent });
  if (state.ageGroup) rows.push({ label: "연령대", value: state.ageGroup });
  if (state.mbti) rows.push({ label: "MBTI", value: state.mbti });
  if (state.tonePreset) rows.push({ label: "톤", value: state.tonePreset });
  if (state.keywords.length)
    rows.push({ label: "강조", value: state.keywords.join(", ") });
  if (state.forbiddenKeywords.length)
    rows.push({ label: "금지", value: state.forbiddenKeywords.join(", ") });

  previewMeta.innerHTML = rows.length
    ? rows.map(r => `
        <div class="preview-row">
          <div class="preview-label">${r.label}</div>
          <div class="preview-value">${r.value}</div>
        </div>
      `).join("")
    : "<span class='muted'>선택된 조건 없음</span>";

  promptPreview.innerText =
    "구공이 전용 프롬프트가 적용됩니다.";
}

/* ---------- build prompt ---------- */
function buildToneRules(tonePreset) {
  const tone = String(tonePreset || '');
  const rules = [];
  if (tone.includes('반말')) {
    rules.push('말투 규칙: 반드시 반말(친근체)로 작성하고 존댓말을 쓰지 마세요.');
  }
  if (tone.includes('질문형')) {
    rules.push('말투 규칙: 전체 톤은 캐주얼하게 유지하고 핵심 고민을 질문형 문장으로 1~2개 포함하세요.');
  }
  return rules;
}

function buildPrompt() {
  const lines = [];

  lines.push(`병원: ${state.clinicName || "미선택"}`);
  lines.push(`글 목적: ${state.reviewIntent || "자연스러운 후기"}`);
  lines.push(`연령대: ${state.ageGroup || "20대 후반"}`);
  lines.push(`MBTI: ${state.mbti || "INFP"}`);
  lines.push(`톤: ${state.tonePreset || "자연스럽고 담백한 톤"}`);

  if (state.personas.length) {
    lines.push(`페르소나: ${state.personas.join(", ")}`);
  }

  if (state.keywords.length) {
    lines.push(`강조 포인트: ${state.keywords.join(", ")}`);
  }
  if (state.forbiddenKeywords.length) {
    lines.push(`금지 표현: ${state.forbiddenKeywords.join(", ")}`);
  }

  lines.push("길이: 500~1000자");
  lines.push("");
  lines.push("중요: 광고/홍보 문구 없이 실제 사용자 후기처럼 작성.");
  lines.push("중요: 마지막 문장에 조건 설명(예: 키워드를 신경썼어요) 문구 금지.");
  lines.push(...buildToneRules(state.tonePreset));
  lines.push("위 조건을 반영해 자연스럽고 솔직한 글을 작성해주세요.");

  return lines.join("\n");
}

/* ---------- generate ---------- */
async function generateReview() {
  const btn = document.getElementById("generateReviewBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "리뷰 생성 중...";
  }
  const loading = document.getElementById("globalLoading");
  if (loading) loading.classList.remove("hidden");
  forceInteractive();
  startInteractionWatchdog();
  modalReview.innerText = "";
  if (titleSuggestions) {
    titleSuggestions.classList.add("hidden");
  }
  if (titleSuggestionList) {
    titleSuggestionList.innerHTML = "";
  }

  const prompt = buildPrompt();

  const payload = {
    model: state.modelKey,
    context: {
      prompt,
      clinic_id: state.clinicId,
      personas: state.personas,
      keywords: state.keywords,
      age_group: state.ageGroup,
      mbti: state.mbti,
    },
  };

  try {
    const res = await window.api.generateReview(payload);
    modalReview.innerText = res.review_text || "";
    state.currentReviewId = res.review_id || null;
    if (Array.isArray(res.title_suggestions) && res.title_suggestions.length) {
      if (titleSuggestionList) {
        titleSuggestionList.innerHTML = res.title_suggestions
          .slice(0, 3)
          .map(t => `<li>${t}</li>`)
          .join("");
      }
      titleSuggestions?.classList.remove("hidden");
    }
    openModal();
  } catch (e) {
    console.error("❌ generateReview error:", e);
    window.showAlert?.("리뷰 생성 실패");
  } finally {
    reviewLoading.classList.add("hidden");
    if (loading) loading.classList.add("hidden");
    if (btn) {
      btn.disabled = false;
      btn.innerText = "리뷰 생성";
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
  if (modalReview) modalReview.contentEditable = "true";
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
  document.getElementById("saveModalBtn")?.addEventListener("click", async () => {
    const editedText = (modalReview?.innerText || "").trim();
    if (!state.currentReviewId) {
      window.showAlert?.("먼저 리뷰를 생성하세요.");
      return;
    }
    if (!editedText) {
      window.showAlert?.("저장할 내용이 없습니다.");
      return;
    }
    try {
      const res = await window.api.saveEditedReview({
        review_id: state.currentReviewId,
        edited_text: editedText,
      });
      state.currentReviewId = res.review_id || state.currentReviewId;
      if (Array.isArray(res.title_suggestions) && res.title_suggestions.length) {
        if (titleSuggestionList) {
          titleSuggestionList.innerHTML = res.title_suggestions
            .slice(0, 3)
            .map(t => `<li>${t}</li>`)
            .join("");
        }
        titleSuggestions?.classList.remove("hidden");
      }
      window.showAlert?.("수정본 저장 완료");
    } catch (e) {
      console.error("❌ saveEditedReview error:", e);
      window.showAlert?.("수정 저장 실패");
    }
  });

  setupSingleGroup("reviewIntent", "reviewIntent");
  setupSingleGroup("ageGroup", "ageGroup");
  setupSingleGroup("mbtiGroup", "mbti");
  setupSingleGroup("tonePreset", "tonePreset");
  setupSingleGroup("personaPreset", "personaPreset");
  setupMultiGroup("keywordGroup");
  setupMultiGroup("forbiddenGroup");

  document.querySelectorAll("#personaPreset button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = btn.dataset.value || "";
      if (!preset) return;
      personaInput.value = preset;
      state.personas = preset
        .split(",")
        .map(v => v.trim())
        .filter(Boolean);
      updatePreview();
    });
  });

  await loadClinics();
  await loadModels();
});

/* ---------- global ---------- */
window.generateReview = generateReview;
window.closeModal = closeModal;
