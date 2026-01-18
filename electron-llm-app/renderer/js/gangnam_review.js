console.log("🔥 gangnam_review.js loaded");

/* =====================================================
   UTIL
===================================================== */
const $ = (id) => document.getElementById(id);

/* =====================================================
   STATE
===================================================== */
let state = {
  modelKey: null,
};

function setFormEnabled(enabled) {
  document
    .querySelectorAll(".review-form input, .review-form select, .review-form textarea")
    .forEach((el) => {
      el.disabled = !enabled;
      if (enabled && el.tagName === "TEXTAREA") {
        el.readOnly = false;
      }
    });
}

/* =====================================================
   LLM MODELS
===================================================== */
async function loadLLMModels() {
  const select = $("modelSelect");
  if (!select) return;

  try {
    const models = await window.api.getLLMModels();
    select.innerHTML = "";

    (models || []).forEach((m, i) => {
      const opt = document.createElement("option");
      opt.value = m.key;
      opt.textContent = `${m.label ?? m.name ?? m.key} (${m.vendor ?? "vendor"})`;

      if (m.recommended || i === 0) {
        opt.selected = true;
        state.modelKey = m.key;
      }
      select.appendChild(opt);
    });

    select.onchange = () => {
      state.modelKey = select.value;
    };

  } catch (e) {
    console.error("❌ 모델 로드 실패:", e);
    select.innerHTML = `<option value="">모델 로드 실패</option>`;
  }
}

/* =====================================================
   TAG HELPERS
===================================================== */
function getSelectedTags(containerId) {
  return [...document.querySelectorAll(`#${containerId} .tag-chip.selected`)]
    .map(chip => chip.dataset.tag);
}

/* =====================================================
   🔥 REVIEW GENERATE (실패해도 무조건 입력 가능)
===================================================== */
async function generateGangnamReview() {
  if (!state.modelKey) {
    alert("AI 모델을 선택하세요");
    return;
  }

  const hospitalName = $("hospitalName")?.value?.trim();
  const procedureType = $("procedureType")?.value?.trim();

  if (!hospitalName || !procedureType) {
    alert("병원명과 시술 종류는 필수입니다.");
    return;
  }

  const btn = $("generateBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "리뷰 생성 중입니다…";
  }
  setFormEnabled(true);
  forceInteractive();
  startInteractionWatchdog();
  closeReviewResultModal();
  let ok = false;

  const payload = {
    hospital_name: hospitalName,
    procedure_type: procedureType,
    procedure_detail: $("procedureDetail")?.value || "",
    doctor_name: $("doctorName")?.value || "",
    anesthesia: $("anesthesia")?.value || "",
    price_range: $("priceRange")?.value || "",
    procedure_date: $("procedureDate")?.value || "",
    write_date: $("writeDate")?.value || "",
    before_concern: $("beforeConcern")?.value || "",
    satisfaction_level: $("satisfactionLevel")?.value || "매우 만족",
    good_points_hint: $("goodPoints")?.value || "",
    bad_points_hint: $("badPoints")?.value || "",
    persona_age: $("personaAge")?.value || "20대 중후반",
    persona_gender: $("personaGender")?.value || "여성",
    persona_tone: $("personaTone")?.value || "친근한",
    emoji_usage: $("emojiUsage")?.value || "적당히",
    forbidden_expressions: $("forbidden")?.value || "",
    model: state.modelKey,
    temperature: Number($("temperature")?.value ?? 0.85),
  };

  try {
    const data = await window.api.generateGangnamReview(payload);

    const raw = (data?.result_review || "").toString();
    autoSelectTagsByReview(raw);

    const tags = {
      select_reasons: getSelectedTags("tags_reason"),
      good_points: getSelectedTags("tags_good"),
      bad_points: getSelectedTags("tags_bad"),
    };

    const modalResult = buildModalResultFromServer(raw, tags, data);
    openReviewResultModal(modalResult);
    ok = true;

  } catch (e) {
    console.error("❌ generateGangnamReview error:", e);
    alert("강남언니 후기 생성 실패 (서버/네트워크)");
    closeReviewResultModal();
    clearModalOverlays();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "후기 생성하기";
    }
    setFormEnabled(true);

    // 🔥 실패/성공 상관없이 항상 입력 가능
    const ta = $("reviewResultText");
    if (ta) {
      ta.disabled = false;
      ta.readOnly = false;
      ta.style.pointerEvents = "auto";
      if (ok && !$("reviewModal")?.classList.contains("hidden")) {
        ta.focus();
      } else {
        $("hospitalName")?.focus();
      }
    }
  }
}

$("generateBtn")?.addEventListener("click", generateGangnamReview);

/* =====================================================
   MODAL DATA
===================================================== */
function buildModalResultFromServer(rawText, tags, serverData) {
  return {
    raw_text: rawText,
    surgery_date: serverData?.procedure_date || "-",
    created_at: serverData?.write_date || "-",
    before_reason: serverData?.before_worry || rawText,
    select_reasons: tags.select_reasons,
    after_review: serverData?.result_review || rawText,
    good_points: tags.good_points,
    bad_points: tags.bad_points,
    bad_reason: serverData?.bad_reason || "",
    rating: Number(serverData?.rating ?? 5),
    extra_comment: serverData?.additional || "",
  };
}

/* =====================================================
   RENDER
===================================================== */
const copyMap = {};

function renderTextSection({ index, title, text }) {
  copyMap[index] = text;
  return `
    <div class="review-section">
      <div class="section-header">
        <h4>${index}. ${title}</h4>
        <button data-copy="${index}">복사</button>
      </div>
      <div class="section-body">${text || ""}</div>
    </div>
  `;
}

function renderTagSection({ index, title, tags }) {
  const list = Array.isArray(tags) ? tags : [];
  copyMap[index] = list.join(", ");
  return `
    <div class="review-section">
      <div class="section-header">
        <h4>${index}. ${title}</h4>
        <button data-copy="${index}">복사</button>
      </div>
      <div class="tag-list">
        ${list.map(t => `<span class="tag">${t}</span>`).join("")}
      </div>
    </div>
  `;
}

function renderRatingSection(score) {
  return `
    <div class="review-section">
      <h4>7. 전체 경험 총점</h4>
      <div class="rating">${"★".repeat(score)} (${score}점)</div>
    </div>
  `;
}

function openReviewResultModal(result) {
  $("surgeryDate").innerText = result.surgery_date;
  $("createdDate").innerText = result.created_at;

  const ta = $("reviewResultText");
  ta.value = result.raw_text;
  ta.disabled = false;
  ta.readOnly = false;
  ta.style.pointerEvents = "auto";

  $("reviewSections").innerHTML = [
    renderTextSection({ index: 1, title: "시술 전 고민", text: result.before_reason }),
    renderTagSection({ index: 2, title: "선택 이유", tags: result.select_reasons }),
    renderTextSection({ index: 3, title: "후기", text: result.after_review }),
    renderTagSection({ index: 4, title: "좋았던 점", tags: result.good_points }),
    renderTagSection({ index: 5, title: "아쉬운 점", tags: result.bad_points }),
    renderRatingSection(result.rating),
    renderTextSection({ index: 8, title: "추가 의견", text: result.extra_comment }),
  ].join("");

  $("reviewModal").classList.remove("hidden");
  ta.focus();
}

function closeReviewResultModal() {
  const modal = $("reviewModal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.style.display = "none";
  requestAnimationFrame(() => {
    modal.style.display = "";
  });
}

function clearModalOverlays() {
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

/* =====================================================
   EVENTS (document 캡처 제거)
===================================================== */
document.addEventListener("click", (e) => {
  if (e.target.closest("#reviewModal")) return;

  const copyBtn = e.target.closest("[data-copy]");
  if (copyBtn) {
    navigator.clipboard.writeText(copyMap[copyBtn.dataset.copy] || "");
  }
});

$("closeReviewModal")?.addEventListener("click", closeReviewResultModal);
$("confirmReviewBtn")?.addEventListener("click", closeReviewResultModal);
document
  .querySelector("#reviewModal .modal-backdrop")
  ?.addEventListener("click", closeReviewResultModal);

/* =====================================================
   TAG DATA & AUTO SELECT
===================================================== */
const REASON_TAGS = ["합리적 가격","높은 평점","후기 내용","의사 전문성","병원 인지도"];
const GOOD_TAGS = ["결과 만족","빠른 회복","통증 적음","애프터케어"];
const BAD_TAGS = ["통증 있음","회복 느림","아쉬움"];

const TAG_RULES = {
  reason: { "합리적 가격": ["가격"] },
  good: { "결과 만족": ["만족"] },
  bad: { "통증 있음": ["아팠"] },
};

function autoSelectTagsByReview(text) {
  Object.entries(TAG_RULES).forEach(([type, rules]) => {
    Object.entries(rules).forEach(([tag, keywords]) => {
      if (keywords.some(k => text.includes(k))) {
        document
          .querySelector(`#tags_${type} .tag-chip[data-tag="${tag}"]`)
          ?.classList.add("selected");
      }
    });
  });
}

function renderTags(containerId, tags) {
  const c = $(containerId);
  if (!c) return;
  c.innerHTML = "";
  tags.forEach(tag => {
    const el = document.createElement("span");
    el.className = "tag-chip";
    el.dataset.tag = tag;
    el.innerText = tag;
    el.onclick = () => el.classList.toggle("selected");
    c.appendChild(el);
  });
}

/* =====================================================
   INIT
===================================================== */
window.addEventListener("DOMContentLoaded", () => {
  loadLLMModels();
  renderTags("tags_reason", REASON_TAGS);
  renderTags("tags_good", GOOD_TAGS);
  renderTags("tags_bad", BAD_TAGS);
});
