document.addEventListener('DOMContentLoaded', () => {
  const GUGONG_MODEL = 'ft:gpt-4.1-2025-04-14:personal::D3gDuLBk';
  const GUGONG_LABEL = '구공이(V_3)';

  let state = {
    clinicId: null,
    clinicName: null,
    modelKey: GUGONG_MODEL,
    modelName: GUGONG_LABEL,
    currentReviewId: null,
    reviewIntent: '자연스러운 후기',
    ageGroup: '20대 후반',
    mbti: 'INFP',
    tonePreset: '자연스럽고 담백한 톤',
    keywords: [],
    forbiddenKeywords: [],
    personas: [],
  };

  const clinicSelect = document.getElementById('clinicSelect');
  const personaInput = document.getElementById('personaInput');
  const modelList = document.getElementById('modelList');
  const resultBox = document.getElementById('resultBox');
  const charCount = document.getElementById('charCount');
  const tokenInfo = document.getElementById('tokenInfo');
  const costInfo = document.getElementById('costInfo');
  const loadingCard = document.getElementById('loadingCard');
  const promptEditor = document.getElementById('promptEditor');
  const promptCard = document.getElementById('promptCard');
  const previewMeta = document.getElementById('previewMeta');
  const personaPreview = document.getElementById('personaPreview');
  const titleSuggestionsBox = document.getElementById('titleSuggestionsBox');
  const titleSuggestionsList = document.getElementById('titleSuggestionsList');
  const generateBtn = document.getElementById('generateBtn');
  const resetBtn = document.getElementById('resetBtn');
  const copyBtn = document.getElementById('copyBtn');
  const regenerateBtn = document.getElementById('regenerateBtn');
  const saveEditedBtn = document.getElementById('saveEditedBtn');
  const copyPromptBtn = document.getElementById('copyPromptBtn');

  resultBox.contentEditable = 'true';
  resultBox.spellcheck = false;

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function flashButton(btn, text = '복사됨!') {
    if (!btn) return;
    const original = btn.dataset.originalText || btn.textContent;
    btn.dataset.originalText = original;
    btn.textContent = text;
    clearTimeout(btn._flashTimer);
    btn._flashTimer = setTimeout(() => {
      btn.textContent = original;
    }, 1200);
  }

  function setupSingleGroup(containerId, key) {
    const buttons = document.querySelectorAll(`#${containerId} button`);
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const active = btn.classList.contains('active');
        buttons.forEach((b) => b.classList.remove('active'));
        state[key] = active ? null : (btn.dataset.value || btn.textContent.trim());
        if (!active) btn.classList.add('active');
        updatePreview();
      });
    });
  }

  function setupMultiGroup(containerId, key) {
    document.querySelectorAll(`#${containerId} button`).forEach((btn) => {
      btn.addEventListener('click', () => {
        btn.classList.toggle('active');
        state[key] = Array.from(document.querySelectorAll(`#${containerId} button.active`)).map((b) => b.textContent.trim());
        updatePreview();
      });
    });
  }

  async function loadClinics() {
    try {
      const res = await fetch('/api/data/clinics/');
      const data = await res.json();
      const clinics = Array.isArray(data) ? data : (data.results || data.data || []);
      clinics.forEach((c) => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.name;
        clinicSelect.appendChild(opt);
      });
    } catch (e) {
      console.error('clinic load error', e);
    }

    clinicSelect.addEventListener('change', () => {
      state.clinicId = clinicSelect.value || null;
      state.clinicName = clinicSelect.options[clinicSelect.selectedIndex]?.text || null;
      updatePreview();
    });
  }

  function loadModelCard() {
    modelList.innerHTML = `<div class="g90-model-card selected"><strong>${state.modelName}</strong></div>`;
  }

  function updatePreview() {
    const rows = [];
    if (state.clinicName) rows.push({ label: '병원', value: state.clinicName });
    rows.push({ label: 'AI 모델', value: state.modelName });
    if (state.reviewIntent) rows.push({ label: '글 목적', value: state.reviewIntent });
    if (state.ageGroup) rows.push({ label: '연령대', value: state.ageGroup });
    if (state.mbti) rows.push({ label: 'MBTI', value: state.mbti });
    if (state.tonePreset) rows.push({ label: '톤', value: state.tonePreset });
    if (state.keywords.length) rows.push({ label: '강조', value: state.keywords.join(', ') });
    if (state.forbiddenKeywords.length) rows.push({ label: '금지', value: state.forbiddenKeywords.join(', ') });

    previewMeta.innerHTML = rows.map((row) => `
      <div class="g90-preview-row">
        <div class="g90-preview-label">${row.label}</div>
        <div class="g90-preview-value">${row.value}</div>
      </div>
    `).join('');

    personaPreview.innerHTML = state.personas.length
      ? state.personas.map((p) => `<span>${p}</span>`).join('')
      : '<span class="muted">미입력</span>';

    promptEditor.value = buildPrompt();
  }

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
    lines.push(`병원: ${state.clinicName || '미선택'}`);
    lines.push(`글 목적: ${state.reviewIntent || '자연스러운 후기'}`);
    lines.push(`연령대: ${state.ageGroup || '20대 후반'}`);
    lines.push(`MBTI: ${state.mbti || 'INFP'}`);
    lines.push(`톤: ${state.tonePreset || '자연스럽고 담백한 톤'}`);

    if (state.personas.length) lines.push(`페르소나: ${state.personas.join(', ')}`);
    if (state.keywords.length) lines.push(`강조 포인트: ${state.keywords.join(', ')}`);
    if (state.forbiddenKeywords.length) lines.push(`금지 표현: ${state.forbiddenKeywords.join(', ')}`);

    lines.push('길이: 500~1000자');
    lines.push('');
    lines.push('중요: 광고/홍보 문구 없이 실제 사용자 후기처럼 작성.');
    lines.push('중요: 마지막 문장에 조건 설명(예: 키워드를 신경썼어요) 문구 금지.');
    lines.push(...buildToneRules(state.tonePreset));
    lines.push('위 조건을 반영해 자연스럽고 솔직한 글을 작성해주세요.');

    return lines.join('\n');
  }

  async function generateReviewFromPrompt(prompt) {
    loadingCard.style.display = 'block';
    resultBox.textContent = '생성 중...';
    resultBox.style.color = 'var(--muted)';
    generateBtn.disabled = true;

    try {
      const response = await fetch('/dashboard/api/generate-basic/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
          user_input: prompt,
          model: GUGONG_MODEL
        })
      });

      const result = await response.json();
      if (!response.ok || result.error) throw new Error(result.error || `HTTP ${response.status}`);

      resultBox.textContent = result.review || '';
      resultBox.style.color = '';
      charCount.textContent = `${result.char_count || 0}자`;
      state.currentReviewId = result.review_id || null;

      if (Array.isArray(result.title_suggestions) && result.title_suggestions.length) {
        titleSuggestionsList.innerHTML = result.title_suggestions.slice(0, 3).map((t) => `<li>${t}</li>`).join('');
        titleSuggestionsBox.style.display = '';
      } else {
        titleSuggestionsList.innerHTML = '';
        titleSuggestionsBox.style.display = 'none';
      }

      if (result.total_tokens) {
        let tokenText = `입력: ${(result.input_tokens || 0).toLocaleString()}`;
        if ((result.cached_input_tokens || 0) > 0) {
          tokenText += ` (캐시: ${result.cached_input_tokens.toLocaleString()})`;
        }
        tokenText += ` | 출력: ${(result.output_tokens || 0).toLocaleString()}`;
        tokenInfo.textContent = tokenText;
        tokenInfo.style.display = '';
      } else {
        tokenInfo.style.display = 'none';
      }

      if (result.cost_krw !== undefined) {
        costInfo.textContent = `₩${Number(result.cost_krw).toLocaleString()}`;
        costInfo.style.display = '';
      } else {
        costInfo.style.display = 'none';
      }

      promptEditor.value = result.prompt_used || prompt;
      promptCard.open = true;
    } finally {
      loadingCard.style.display = 'none';
      generateBtn.disabled = false;
    }
  }

  generateBtn.addEventListener('click', async () => {
    try {
      await generateReviewFromPrompt(buildPrompt());
    } catch (e) {
      alert('생성 실패: ' + e.message);
      resultBox.textContent = '리뷰가 여기에 표시됩니다.';
      resultBox.style.color = 'var(--muted)';
    }
  });

  regenerateBtn.addEventListener('click', async () => {
    const prompt = (promptEditor.value || '').trim();
    try {
      if (!prompt) {
        await generateReviewFromPrompt(buildPrompt());
      } else {
        loadingCard.style.display = 'block';
        resultBox.textContent = '생성 중...';
        resultBox.style.color = 'var(--muted)';

        const response = await fetch('/dashboard/api/generate-from-prompt/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
          },
          body: JSON.stringify({ prompt, model: GUGONG_MODEL })
        });

        const result = await response.json();
        if (!response.ok || result.error) throw new Error(result.error || `HTTP ${response.status}`);

        resultBox.textContent = result.review || '';
        resultBox.style.color = '';
        charCount.textContent = `${result.char_count || 0}자`;
        state.currentReviewId = result.review_id || null;

        if (Array.isArray(result.title_suggestions) && result.title_suggestions.length) {
          titleSuggestionsList.innerHTML = result.title_suggestions.slice(0, 3).map((t) => `<li>${t}</li>`).join('');
          titleSuggestionsBox.style.display = '';
        } else {
          titleSuggestionsList.innerHTML = '';
          titleSuggestionsBox.style.display = 'none';
        }
      }
    } catch (e) {
      alert('재생성 실패: ' + e.message);
    } finally {
      loadingCard.style.display = 'none';
    }
  });

  saveEditedBtn.addEventListener('click', async () => {
    const edited = (resultBox.textContent || '').trim();
    if (!state.currentReviewId) {
      alert('먼저 리뷰를 생성해주세요.');
      return;
    }
    if (!edited) {
      alert('저장할 내용이 없습니다.');
      return;
    }

    try {
      const response = await fetch('/dashboard/api/generated/save-edit/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ review_id: state.currentReviewId, edited_text: edited })
      });

      const result = await response.json();
      if (!response.ok || result.error) throw new Error(result.error || `HTTP ${response.status}`);

      state.currentReviewId = result.review_id || state.currentReviewId;
      charCount.textContent = `${result.char_count || edited.length}자`;
      if (Array.isArray(result.title_suggestions) && result.title_suggestions.length) {
        titleSuggestionsList.innerHTML = result.title_suggestions.slice(0, 3).map((t) => `<li>${t}</li>`).join('');
        titleSuggestionsBox.style.display = '';
      }
      alert('수정본이 저장되었습니다.');
    } catch (e) {
      alert('수정 저장 실패: ' + e.message);
    }
  });

  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(resultBox.textContent || '');
    flashButton(copyBtn);
  });

  copyPromptBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(promptEditor.value || '');
    flashButton(copyPromptBtn);
  });

  resetBtn.addEventListener('click', () => {
    state = {
      ...state,
      clinicId: null,
      clinicName: null,
      currentReviewId: null,
      reviewIntent: '자연스러운 후기',
      ageGroup: '20대 후반',
      mbti: 'INFP',
      tonePreset: '자연스럽고 담백한 톤',
      keywords: [],
      forbiddenKeywords: [],
      personas: [],
    };

    clinicSelect.value = '';
    personaInput.value = '';
    document.querySelectorAll('.chip-group button').forEach((b) => b.classList.remove('active'));
    document.querySelector('#reviewIntent button[data-value="자연스러운 후기"]')?.classList.add('active');
    document.querySelector('#ageGroup button[data-value="20대 후반"]')?.classList.add('active');
    document.querySelector('#mbtiGroup button[data-value="INFP"]')?.classList.add('active');
    document.querySelector('#tonePreset button[data-value="자연스럽고 담백한 톤"]')?.classList.add('active');

    resultBox.textContent = '리뷰가 여기에 표시됩니다.';
    resultBox.style.color = 'var(--muted)';
    charCount.textContent = '0자';
    tokenInfo.style.display = 'none';
    costInfo.style.display = 'none';
    titleSuggestionsList.innerHTML = '';
    titleSuggestionsBox.style.display = 'none';
    updatePreview();
  });

  personaInput.addEventListener('input', (e) => {
    state.personas = String(e.target.value || '')
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean);
    updatePreview();
  });

  setupSingleGroup('reviewIntent', 'reviewIntent');
  setupSingleGroup('ageGroup', 'ageGroup');
  setupSingleGroup('mbtiGroup', 'mbti');
  setupSingleGroup('tonePreset', 'tonePreset');
  setupMultiGroup('keywordGroup', 'keywords');
  setupMultiGroup('forbiddenGroup', 'forbiddenKeywords');

  loadClinics();
  loadModelCard();
  updatePreview();
});
