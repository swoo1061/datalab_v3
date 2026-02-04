console.log("review.js loaded");

const MBTI_RE = /\b(ISTJ|ISFJ|INFJ|INTJ|ISTP|ISFP|INFP|INTP|ESTP|ESFP|ENFP|ENTP|ESTJ|ESFJ|ENFJ|ENTJ)\b/i;

const state = {
  userInput: "",
  modelKey: null,
  modelName: null,
  modelProfileText: null,
  models: [],
  currentReviewId: null,
};

const keywordInputEl = document.getElementById("keywordInput");
const modelListEl = document.getElementById("modelList");
const previewMetaEl = document.getElementById("previewMetaMain");
const promptPreviewEl = document.getElementById("promptPreview");
const modalReviewEl = document.getElementById("modalReview");
const titleSuggestionsEl = document.getElementById("titleSuggestions");
const titleSuggestionListEl = document.getElementById("titleSuggestionList");
const reviewModalEl = document.getElementById("reviewModal");

function extractMbtiFromText(text) {
  const m = String(text || "").match(MBTI_RE);
  return m ? m[1].toUpperCase() : null;
}

function normalizeArray(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  if (data?.data) return data.data;
  return [];
}

function normalizeTier(value, fallback) {
  const raw = String(value || "").toLowerCase();
  if (!raw) return fallback;
  if (["high", "good", "fast", "quick", "premium", "expensive", "top"].some((k) => raw.includes(k))) return "높음";
  if (["low", "cheap", "slow", "lite", "mini", "economy"].some((k) => raw.includes(k))) return "낮음";
  if (["medium", "mid", "balanced", "normal"].some((k) => raw.includes(k))) return "보통";
  return fallback;
}

function inferModelProfile(model) {
  const key = String(model?.key || "").toLowerCase();
  const name = String(model?.label || model?.name || "").toLowerCase();
  const target = `${key} ${name}`;

  let quality = normalizeTier(model?.quality_tier || model?.quality, "보통");
  let speed = normalizeTier(model?.speed_tier || model?.latency_tier || model?.speed, "보통");
  let cost = normalizeTier(model?.cost_tier || model?.price_tier || model?.cost, "보통");

  if (quality === "보통" && speed === "보통" && cost === "보통") {
    if (/mini|nano|lite|haiku|flash/.test(target)) {
      quality = "보통";
      speed = "높음";
      cost = "낮음";
    } else if (/gpt-4\.1|gpt-5|o3|opus|sonnet/.test(target)) {
      quality = "높음";
      speed = "보통";
      cost = "높음";
    }
  }

  return {
    quality,
    speed,
    cost,
    text: `품질: ${quality} / 속도: ${speed} / 비용: ${cost}`,
  };
}

function getModelPerformanceText(model) {
  const raw = String(
    model?.desc || model?.description || model?.summary || model?.notes || ""
  ).trim();
  if (raw) return raw.replace(/\s*\(추천\)\s*/g, "").trim();
  return inferModelProfile(model).text;
}

function buildPrompt() {
  const rawInput = (state.userInput || "").trim();
  const mbti = extractMbtiFromText(rawInput);
  const modelLine =
    state.modelName || state.modelProfileText
      ? `[모델] ${state.modelName || ""}${state.modelProfileText ? ` (${state.modelProfileText})` : ""}`.trim()
      : "";
  const lines = [
    modelLine,
    rawInput,
    state.modelKey === "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk" && mbti ? `MBTI: ${mbti}` : "",
    "",
    "위 입력 조건을 반영해 실제 사용자가 작성한 것처럼 자연스럽고 솔직한 리뷰를 작성해주세요.",
  ].filter(Boolean);
  return lines.join("\n");
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function parseInputFields(text) {
  const lines = String(text || "").split(/\r?\n/);
  const rows = [];
  const seen = new Set();
  const knownLabels = ["병원", "원장", "시술", "컨텐츠", "톤", "길이", "글자수", "권장", "금지", "리뷰 유형", "후기 시점", "페르소나", "나이대", "연령대", "성별", "MBTI"];
  const aliasMap = { "연령대": "나이대", "글자수": "길이" };
  const normalizeLabel = (label) => aliasMap[label] || label;

  for (let i = 0; i < lines.length; i += 1) {
    const raw = (lines[i] || "").trim();
    if (!raw) continue;
    const m = raw.match(/^(.+?)\s*[:：=\-]\s*(.+)$/);
    let label = "";
    let value = "";

    if (m) {
      label = (m[1] || "").trim();
      value = (m[2] || "").trim();
    } else {
      const matchedLabel = knownLabels.find((k) => raw.startsWith(`${k} `));
      if (matchedLabel) {
        label = matchedLabel;
        value = raw.slice(matchedLabel.length).trim();
      } else {
        // "병원\n강남12의원" 처럼 라벨/값이 줄바꿈으로 분리된 입력 지원
        const exactLabel = knownLabels.find((k) => raw === k);
        const next = (lines[i + 1] || "").trim();
        if (exactLabel && next) {
          label = exactLabel;
          value = next;
          i += 1; // 다음 줄을 값으로 소비
        } else {
          continue;
        }
      }
    }

    if (!label || !value) continue;
    if (/(^|[\s])성별($|[\s])/.test(label)) {
      const gm = value.match(/(여성|남성|여자|남자)/);
      if (gm) value = gm[1];
    }
    label = normalizeLabel(label);
    const key = label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    rows.push({ label, value });
  }

  return rows;
}

function inferFieldsFromFreeText(text) {
  const raw = String(text || "").trim();
  if (!raw) return [];

  const tokens = raw
    .split(/[,\n]/)
    .map((v) => v.trim())
    .filter(Boolean);

  const rows = [];
  const used = new Set();

  const pushOnce = (label, value) => {
    if (!value || used.has(label)) return;
    used.add(label);
    rows.push({ label, value });
  };

  // 1) 병원 추정
  const hospital = tokens.find((t) => /(의원|병원|클리닉|성형외과|피부과|치과|한의원)/.test(t));
  if (hospital) pushOnce("병원", hospital);

  // 2) 컨텐츠/리뷰 유형 추정
  const content = tokens.find((t) => /(후기|상담|질문|고민|경험|리뷰)/.test(t));
  if (content) pushOnce("컨텐츠", content);

  // 3) 시술 추정
  const procedure = tokens.find((t) => /(수술|시술|트임|교정|리프팅|필러|보톡스|레이저|윤곽|코|눈)/.test(t));
  if (procedure) pushOnce("시술", procedure);

  // 4) 원장 추정
  const doctor = tokens.find((t) => /(원장|의사|대표원장)/.test(t));
  if (doctor) pushOnce("원장", doctor);

  // 5) 나이대 추정
  const ageMatch = raw.match(/(\d{2})\s*대\s*(초반|중반|후반)?/);
  if (ageMatch) {
    pushOnce("나이대", `${ageMatch[1]}대${ageMatch[2] ? ` ${ageMatch[2]}` : ""}`.trim());
  }

  // 6) 성별 추정
  const genderToken = tokens.find((t) => /(여성|남성|여자|남자)/.test(t));
  if (genderToken) {
    const genderMatch = genderToken.match(/(여성|남성|여자|남자)/);
    if (genderMatch) {
      pushOnce("성별", genderMatch[1]);
    }
  }

  // 7) MBTI 추정
  const mbtiMatch = raw.match(/\b(ISTJ|ISFJ|INFJ|INTJ|ISTP|ISFP|INFP|INTP|ESTP|ESFP|ENFP|ENTP|ESTJ|ESFJ|ENFJ|ENTJ)\b/i);
  if (mbtiMatch) pushOnce("MBTI", mbtiMatch[1].toUpperCase());

  // 8) 길이/글자수 추정
  const lenMatch = raw.match(/(\d+)\s*(자|글자|문장)\s*(내외|이내|이상|정도)?/);
  if (lenMatch) {
    const unit = lenMatch[2] === "글자" ? "자" : lenMatch[2];
    const suffix = lenMatch[3] ? ` ${lenMatch[3]}` : "";
    pushOnce("길이", `${lenMatch[1]}${unit}${suffix}`);
  }

  // 9) 톤 추정
  const toneToken = tokens.find((t) => /(톤|말투|자연스럽|솔직|친근|차분|귀엽|반말|존댓말|격식|담백)/.test(t));
  if (toneToken) {
    const cleanTone = toneToken.replace(/^(톤|말투)\s*/g, "").trim();
    pushOnce("톤", cleanTone || toneToken);
  }

  // 10) 컨텐츠/후기 시점 추정
  const timing = tokens.find((t) => /(당일|1주차|2주차|3주차|1개월|2개월|3개월|전|후)/.test(t));
  if (timing) pushOnce("후기 시점", timing);

  // 11) 권장/금지 키워드 추정
  const recommendToken = tokens.find((t) => /(권장|강조|키워드)/.test(t));
  if (recommendToken) {
    const cleaned = recommendToken.replace(/(권장|강조|키워드)/g, "").replace(/[:：=\-]/g, "").trim();
    if (cleaned) pushOnce("권장", cleaned);
  }
  const forbiddenToken = tokens.find((t) => /(금지|제외|피하기|쓰지마|사용금지)/.test(t));
  if (forbiddenToken) {
    const cleaned = forbiddenToken.replace(/(금지|제외|피하기|쓰지마|사용금지)/g, "").replace(/[:：=\-]/g, "").trim();
    if (cleaned) pushOnce("금지", cleaned);
  }

  return rows;
}

function updatePreview() {
  const rows = [];
  if (state.modelName) rows.push({ label: "AI 모델", value: state.modelName });
  if (state.modelProfileText) rows.push({ label: "모델 성능", value: state.modelProfileText });

  const parsedFields = parseInputFields(state.userInput);
  const inferredFields = parsedFields.length ? [] : inferFieldsFromFreeText(state.userInput);
  rows.push(...parsedFields);
  rows.push(...inferredFields);

  if (!parsedFields.length && !inferredFields.length) {
    rows.push({ label: "입력 상태", value: state.userInput ? "작성됨" : "미입력" });
  }

  if (previewMetaEl) {
    previewMetaEl.innerHTML = rows
      .map(
        (r) => `
        <div class="preview-row">
          <div class="preview-label">${escapeHtml(r.label)}</div>
          <div class="preview-value">${escapeHtml(r.value)}</div>
        </div>
      `
      )
      .join("");
  }

  if (promptPreviewEl) {
    promptPreviewEl.innerText = state.userInput || state.modelName
      ? buildPrompt()
      : "왼쪽에 키워드를 입력하면 프롬프트가 여기에 표시됩니다.";
  }
}

async function loadModels() {
  const models = normalizeArray(await window.api.getLLMModels());
  state.models = models;
  modelListEl.innerHTML = "";

  const forcedModelKey = new URLSearchParams(window.location.search).get("model");
  const sortedModels = [...models].sort((a, b) => {
    const aScore = a?.recommended || /\(추천\)/.test(String(a?.desc || "")) ? 1 : 0;
    const bScore = b?.recommended || /\(추천\)/.test(String(b?.desc || "")) ? 1 : 0;
    return bScore - aScore;
  });

  const buttonWrapEl = document.createElement("div");
  buttonWrapEl.className = "model-btn-wrap";

  const perfEl = document.createElement("div");
  perfEl.className = "model-perf-hint";

  const applyModel = (key, clickedBtn = null) => {
    const model = sortedModels.find((m) => m.key === key) || sortedModels[0];
    if (!model) return;
    const displayName = model.label || model.name || model.key;
    const performanceText = getModelPerformanceText(model);
    state.modelKey = model.key;
    state.modelName = displayName;
    state.modelProfileText = performanceText;
    perfEl.textContent = performanceText;
    if (clickedBtn) {
      buttonWrapEl.querySelectorAll(".model-pill").forEach((el) => el.classList.remove("selected"));
      clickedBtn.classList.add("selected");
    }
    updatePreview();
  };

  sortedModels.forEach((m) => {
    const displayName = m.label || m.name || m.key;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "model-pill";
    const nameSpan = document.createElement("span");
    nameSpan.className = "model-pill-name";
    nameSpan.textContent = displayName;
    btn.appendChild(nameSpan);
    btn.addEventListener("click", () => applyModel(m.key, btn));
    buttonWrapEl.appendChild(btn);
  });

  const defaultModel =
    (forcedModelKey && sortedModels.find((m) => m.key === forcedModelKey)?.key) ||
    sortedModels.find((m) => m.recommended)?.key ||
    sortedModels[0]?.key ||
    "";

  if (defaultModel) {
    const defaultBtn = Array.from(buttonWrapEl.querySelectorAll(".model-pill")).find(
      (_, idx) => sortedModels[idx]?.key === defaultModel
    );
    applyModel(defaultModel, defaultBtn || null);
  }

  modelListEl.appendChild(buttonWrapEl);
  modelListEl.appendChild(perfEl);
}

function openModal() {
  document.body.style.overflow = "hidden";
  if (modalReviewEl) {
    modalReviewEl.contentEditable = "true";
    modalReviewEl.focus();
  }
  reviewModalEl?.classList.remove("hidden");
}

function closeModal() {
  document.body.style.overflow = "";
  reviewModalEl?.classList.add("hidden");
}

async function generateReview() {
  const rawInput = (state.userInput || "").trim();
  if (!rawInput) {
    window.showAlert?.("키워드를 입력하세요.");
    return;
  }
  if (!state.modelKey) {
    window.showAlert?.("AI 모델을 선택하세요.");
    return;
  }

  const btn = document.getElementById("generateReviewBtn");
  const loading = document.getElementById("globalLoading");
  btn && (btn.disabled = true);
  if (btn) btn.innerText = "리뷰 생성 중...";
  loading?.classList.remove("hidden");
  if (modalReviewEl) modalReviewEl.innerText = "";
  titleSuggestionsEl?.classList.add("hidden");
  if (titleSuggestionListEl) titleSuggestionListEl.innerHTML = "";

  const payload = {
    model: state.modelKey,
    context: {
      prompt: buildPrompt(),
      keywords: rawInput
        .split(/[\n,]/)
        .map((v) => v.trim())
        .filter(Boolean),
    },
  };

  try {
    const res = await window.api.generateReview(payload);
    if (modalReviewEl) modalReviewEl.innerText = res.review_text || "";
    state.currentReviewId = res.review_id || null;

    if (Array.isArray(res.title_suggestions) && res.title_suggestions.length && titleSuggestionListEl) {
      titleSuggestionListEl.innerHTML = res.title_suggestions.slice(0, 3).map((t) => `<li>${t}</li>`).join("");
      titleSuggestionsEl?.classList.remove("hidden");
    }
    openModal();
  } catch (e) {
    console.error("generateReview error:", e);
    window.showAlert?.("리뷰 생성 실패");
  } finally {
    loading?.classList.add("hidden");
    if (btn) {
      btn.disabled = false;
      btn.innerText = "리뷰 생성";
    }
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  keywordInputEl?.addEventListener("input", (e) => {
    state.userInput = (e.target.value || "").trim();
    updatePreview();
  });

  document.getElementById("copyModalBtn")?.addEventListener("click", () => {
    const text = modalReviewEl?.innerText || "";
    navigator.clipboard.writeText(text);
  });

  document.getElementById("saveModalBtn")?.addEventListener("click", async () => {
    const editedText = (modalReviewEl?.innerText || "").trim();
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
      window.showAlert?.("수정본 저장 완료");
    } catch (e) {
      console.error("saveEditedReview error:", e);
      window.showAlert?.("수정 저장 실패");
    }
  });

  await loadModels();
  updatePreview();
});

window.generateReview = generateReview;
window.closeModal = closeModal;
