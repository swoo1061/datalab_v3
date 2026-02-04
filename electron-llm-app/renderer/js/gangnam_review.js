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
      opt.textContent = `${m.label ?? m.name ?? m.key}`;

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
    window.showAlert?.("AI 모델을 선택하세요");
    return;
  }

  const hospitalName = $("hospitalName")?.value?.trim();
  const procedureType = $("procedureType")?.value?.trim();

  if (!hospitalName || !procedureType) {
    window.showAlert?.("병원명과 시술 종류는 필수입니다.");
    return;
  }

  const btn = $("generateBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "리뷰 생성 중입니다…";
  }
  const loading = $("globalLoading");
  if (loading) loading.classList.remove("hidden");
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

    const raw = (data?.result_review || data?.review_text || data?.raw_text || "").toString();
    const tagText = [
      data?.before_worry,
      data?.result_review,
      data?.bad_reason,
      data?.additional,
      payload?.good_points_hint,
      payload?.bad_points_hint,
    ]
      .filter(Boolean)
      .join(" ");
    autoSelectTagsByReview(tagText || raw);

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
    const msg = e?.data?.error || e?.message || "강남언니 후기 생성 실패 (서버/네트워크)";
    window.showAlert?.(msg);
    closeReviewResultModal();
    clearModalOverlays();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "후기 생성하기";
    }
    setFormEnabled(true);
    if (loading) loading.classList.add("hidden");

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
  const safeRaw = rawText || serverData?.result_review || serverData?.review_text || "";
  return {
    raw_text: safeRaw,
    surgery_date: serverData?.procedure_date || "-",
    created_at: serverData?.write_date || "-",
    before_reason: serverData?.before_worry || "",
    select_reasons: tags.select_reasons,
    after_review: serverData?.result_review || serverData?.review_text || safeRaw,
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
function updateCharCount(sectionId, text) {
  const section = document.querySelector(`[data-section="${sectionId}"]`);
  if (!section) return;
  const countEl = section.querySelector(".char-count");
  if (!countEl) return;
  const len = text ? text.length : 0;
  countEl.textContent = `${len}자`;
}

function renderStars(rating) {
  const score = Number(rating || 0);
  const fullStars = Math.floor(score);
  const halfStar = score % 1 >= 0.5;
  let stars = "★".repeat(fullStars);
  if (halfStar) stars += "½";
  stars += "☆".repeat(5 - Math.ceil(score));
  return `${stars} (${score || 0}점)`;
}

function openReviewResultModal(result) {
  $("display_procedure_date").innerText = result.surgery_date;
  $("display_write_date").innerText = result.created_at;
  if ($("dateInfo")) $("dateInfo").style.display = "flex";

  const ta = $("reviewResultText");
  ta.value = result.raw_text;
  ta.disabled = false;
  ta.readOnly = false;
  ta.style.pointerEvents = "auto";

  $("result_before_worry").textContent = result.before_reason || "";
  $("result_result_review").textContent = result.after_review || "";
  $("result_bad_reason").textContent = result.bad_reason || "";
  $("result_additional").textContent = result.extra_comment || "";
  $("result_rating").innerText = renderStars(result.rating);

  updateCharCount("before_worry", result.before_reason || "");
  updateCharCount("result_review", result.after_review || "");
  updateCharCount("bad_reason", result.bad_reason || "");
  updateCharCount("additional", result.extra_comment || "");

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

function copySection(sectionId, btn) {
  const content = $(`result_${sectionId}`)?.textContent || "";
  navigator.clipboard.writeText(content);
  flashCopy(btn);
}

function copyTags(type, btn) {
  const container = $(`tags_${type}`);
  if (!container) return;
  const selectedTags = [];
  container.querySelectorAll(".tag-chip.selected").forEach((chip) => {
    selectedTags.push(chip.dataset.tag);
  });
  navigator.clipboard.writeText(selectedTags.join(", "));
  flashCopy(btn);
}

function copyAll(btn) {
  const getSelectedTags = (containerId) => {
    const tags = [];
    document.querySelectorAll(`#${containerId} .tag-chip.selected`).forEach((chip) => {
      tags.push(chip.dataset.tag);
    });
    return tags.join(", ") || "없음";
  };

  const fullText = `[시술 전 고민과 시술을 결정한 계기]
${$("result_before_worry")?.textContent || ""}

[이 병원 및 이벤트를 선택한 이유]
${getSelectedTags("tags_reason")}

[시술 결과 후기]
${$("result_result_review")?.textContent || ""}

[좋았던 점]
${getSelectedTags("tags_good")}

[아쉬운 점]
${getSelectedTags("tags_bad")}

[아쉬운 점을 선택한 이유]
${$("result_bad_reason")?.textContent || ""}

[전체 경험 총점]
${$("result_rating")?.textContent || ""}

  [추가 의견]
  ${$("result_additional")?.textContent || ""}
  `;

  navigator.clipboard.writeText(fullText);
  flashCopy(btn);
}

document.addEventListener("click", (e) => {
  const sectionBtn = e.target.closest("[data-copy-section]");
  if (sectionBtn) {
    copySection(sectionBtn.dataset.copySection, sectionBtn);
    return;
  }

  const tagsBtn = e.target.closest("[data-copy-tags]");
  if (tagsBtn) {
    copyTags(tagsBtn.dataset.copyTags, tagsBtn);
    return;
  }
});

$("closeReviewModal")?.addEventListener("click", closeReviewResultModal);
$("confirmReviewBtn")?.addEventListener("click", closeReviewResultModal);
$("copyAllBtn")?.addEventListener("click", (e) => copyAll(e.currentTarget));

/* =====================================================
   TAG DATA & AUTO SELECT
===================================================== */
const REASON_TAGS = [
  "합리적 가격",
  "높은 평점",
  "후기 내용",
  "의사 전문성",
  "병원 인지도",
  "병원 위치",
  "재방문",
  "지인 추천",
  "병원 시설",
  "최신 기기",
  "앱결제",
  "포인트 사용",
  "기타",
];
const GOOD_TAGS = [
  "빠른 효과",
  "결과 만족",
  "부작용 없음",
  "적은 통증",
  "흉터 없음",
  "빠른 회복",
  "일상 생활 가능",
  "꼼꼼한 시술",
  "애프터케어",
  "기타",
  "없어요",
];
const BAD_TAGS = [
  "효과 없음",
  "결과 불만족",
  "부작용 있음",
  "시술 중 통증",
  "시술 후 통증",
  "흉터 남음",
  "더딘 회복",
  "일상 복귀 시간 필요",
  "성의 없는 시술",
  "애프터케어 부족",
  "기타",
  "없어요",
];

const TAG_RULES = {
  reason: {
    "합리적 가격": ["가격", "비용", "가성비"],
    "높은 평점": ["평점", "후기", "리뷰"],
    "후기 내용": ["후기", "리뷰", "평가"],
    "의사 전문성": ["의사", "원장", "전문", "실력"],
    "병원 인지도": ["유명", "인지도", "평판"],
    "병원 위치": ["위치", "교통", "거리", "근처"],
    "재방문": ["재방문", "다시", "또"],
    "지인 추천": ["추천", "지인", "친구", "소개"],
    "병원 시설": ["시설", "깨끗", "환경"],
    "최신 기기": ["기기", "장비", "최신"],
    "앱결제": ["앱결제", "앱 결제", "결제"],
    "포인트 사용": ["포인트", "적립"],
  },
  good: {
    "빠른 효과": ["빠른", "효과", "즉시"],
    "결과 만족": ["만족", "좋았", "만족도"],
    "부작용 없음": ["부작용 없", "문제 없", "이상 없"],
    "적은 통증": ["통증 적", "안 아", "덜 아"],
    "흉터 없음": ["흉터 없", "자국 없"],
    "빠른 회복": ["회복 빠", "금방", "빠르게"],
    "일상 생활 가능": ["일상", "생활 가능", "바로"],
    "꼼꼼한 시술": ["꼼꼼", "세심", "디테일"],
    "애프터케어": ["애프터", "케어", "사후"],
  },
  bad: {
    "효과 없음": ["효과 없", "변화 없"],
    "결과 불만족": ["불만족", "아쉽", "별로"],
    "부작용 있음": ["부작용 있", "문제 있", "이상 있"],
    "시술 중 통증": ["시술 중", "중에 아", "통증"],
    "시술 후 통증": ["시술 후", "끝나고 아", "통증"],
    "흉터 남음": ["흉터", "자국"],
    "더딘 회복": ["회복 느", "오래", "더디"],
    "일상 복귀 시간 필요": ["일상 복귀", "복귀", "시간 필요"],
    "성의 없는 시술": ["성의", "대충", "불친절"],
    "애프터케어 부족": ["애프터", "케어 부족", "사후"],
  },
};

function clearSelectedTags(containerId) {
  document.querySelectorAll(`#${containerId} .tag-chip`).forEach((chip) => {
    chip.classList.remove("selected");
  });
}

function selectTagsFromText(containerId, tags, rules, text, maxCount) {
  const normalized = (text || "").replace(/\s+/g, "").toLowerCase();
  let count = 0;
  tags.forEach((tag) => {
    if (count >= maxCount) return;
    const keywords = rules?.[tag] || [tag];
    const hit = keywords.some((k) =>
      normalized.includes(String(k).replace(/\s+/g, "").toLowerCase())
    );
    if (hit) {
      document
        .querySelector(`#${containerId} .tag-chip[data-tag="${tag}"]`)
        ?.classList.add("selected");
      count += 1;
    }
  });
  return count;
}

function autoSelectTagsByReview(text) {
  clearSelectedTags("tags_reason");
  clearSelectedTags("tags_good");
  clearSelectedTags("tags_bad");

  const reasonCount = selectTagsFromText(
    "tags_reason",
    REASON_TAGS,
    TAG_RULES.reason,
    text,
    3
  );
  const goodCount = selectTagsFromText(
    "tags_good",
    GOOD_TAGS,
    TAG_RULES.good,
    text,
    3
  );
  const badCount = selectTagsFromText(
    "tags_bad",
    BAD_TAGS,
    TAG_RULES.bad,
    text,
    3
  );

  if (badCount === 0) {
    document
      .querySelector(`#tags_bad .tag-chip[data-tag="없어요"]`)
      ?.classList.add("selected");
  }
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

function syncTemperatureUI() {
  const range = $("temperature");
  const value = $("tempValue");
  if (!range || !value) return;
  value.innerText = Number(range.value || 0.85).toFixed(2);
}

/* =====================================================
   INIT
===================================================== */
window.addEventListener("DOMContentLoaded", () => {
  loadLLMModels();
  renderTags("tags_reason", REASON_TAGS);
  renderTags("tags_good", GOOD_TAGS);
  renderTags("tags_bad", BAD_TAGS);
  syncTemperatureUI();
  $("temperature")?.addEventListener("input", syncTemperatureUI);
});
