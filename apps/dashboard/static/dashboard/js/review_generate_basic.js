document.addEventListener('DOMContentLoaded', () => {
  let currentReviewId = null;
  const userInput = document.getElementById('userInput');
  const resultBox = document.getElementById('resultBox');
  const charCount = document.getElementById('charCount');
  const tokenInfo = document.getElementById('tokenInfo');
  const costInfo = document.getElementById('costInfo');
  const loadingCard = document.getElementById('loadingCard');
  const generateBtn = document.getElementById('generateBtn');
  const promptEditor = document.getElementById('promptEditor');
  const promptCard = document.getElementById('promptCard');
  const MBTI_RE = /\b(ISTJ|ISFJ|INFJ|INTJ|ISTP|ISFP|INFP|INTP|ESTP|ESFP|ENFP|ENTP|ESTJ|ESFJ|ENFJ|ENTJ)\b/i;
  function extractMbti(text) {
    const m = String(text || "").match(MBTI_RE);
    return m ? m[1].toUpperCase() : null;
  }
  const titleSuggestionsBox = document.getElementById('titleSuggestionsBox');
  const titleSuggestionsList = document.getElementById('titleSuggestionsList');
  resultBox.contentEditable = 'true';
  resultBox.spellcheck = false;

  // CSRF 토큰
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

  // ✅ 프롬프트 복사 버튼: summary 클릭 토글 막기
  const copyPromptBtn = document.getElementById('copyPromptBtn');
  if (copyPromptBtn) {
    copyPromptBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      navigator.clipboard.writeText(promptEditor.value).then(() => {
        copyPromptBtn.textContent = '복사됨!';
        setTimeout(() => { copyPromptBtn.textContent = '복사'; }, 2000);
      });
    });
  }

  // 리뷰 생성
  generateBtn.addEventListener('click', async function () {
    let input = userInput.value.trim();
    const selectedModel =
      document.querySelector('input[name="model"]:checked')?.value
      || 'claude-sonnet-4-5-20250929';

    if (!input) {
      alert('리뷰 정보를 입력해주세요.');
      return;
    }

    const mbti = extractMbti(input);
    if (selectedModel === 'ft:gpt-4.1-2025-04-14:personal::D3gDuLBk' && mbti) {
      input = `${input}\nMBTI: ${mbti}`;
    }

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
          user_input: input,
          model: selectedModel
        })
      });

      const result = await response.json();

      if (result.error) {
        throw new Error(result.error);
      }

      resultBox.textContent = result.review;
      resultBox.style.color = '';
      charCount.textContent = `${result.char_count}자`;
      currentReviewId = result.review_id || null;
      if (Array.isArray(result.title_suggestions) && result.title_suggestions.length) {
        titleSuggestionsList.innerHTML = result.title_suggestions
          .map(t => `<li>${t}</li>`)
          .join('');
        titleSuggestionsBox.style.display = '';
      } else {
        titleSuggestionsList.innerHTML = '';
        titleSuggestionsBox.style.display = 'none';
      }

      // 토큰/비용 표시
      if (result.total_tokens) {
        let tokenText = `입력: ${result.input_tokens.toLocaleString()}`;
        if (result.cached_input_tokens > 0) {
          tokenText += ` (캐시: ${result.cached_input_tokens.toLocaleString()})`;
        }
        tokenText += ` | 출력: ${result.output_tokens.toLocaleString()}`;
        tokenInfo.textContent = tokenText;
        tokenInfo.style.display = '';
      }
      if (result.cost_krw !== undefined) {
        costInfo.textContent = `₩${result.cost_krw.toLocaleString()}`;
        costInfo.style.display = '';
      }

      // 프롬프트 표시
      if (result.prompt_used) {
        promptEditor.value = result.prompt_used;
        promptCard.open = true;
      }

      loadingCard.style.display = 'none';

    } catch (err) {
      alert('생성 실패: ' + err.message);
      loadingCard.style.display = 'none';
      resultBox.textContent = '리뷰가 여기에 표시됩니다.';
      resultBox.style.color = 'var(--muted)';
    } finally {
      generateBtn.disabled = false;
    }
  });

  // 다시 생성 (프롬프트 수정 반영)
  document.getElementById('regenerateBtn').addEventListener('click', async function () {
    const prompt = promptEditor.value.trim();
    const selectedModel =
      document.querySelector('input[name="model"]:checked')?.value
      || 'claude-sonnet-4-5-20250929';

    if (!prompt) {
      generateBtn.click();
      return;
    }

    loadingCard.style.display = 'block';
    resultBox.textContent = '생성 중...';
    resultBox.style.color = 'var(--muted)';

    try {
      const response = await fetch('/dashboard/api/generate-from-prompt/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
          prompt: prompt,
          model: selectedModel
        })
      });

      const result = await response.json();

      if (result.error) {
        throw new Error(result.error);
      }

      resultBox.textContent = result.review;
      resultBox.style.color = '';
      charCount.textContent = `${result.char_count}자`;
      currentReviewId = result.review_id || null;
      if (Array.isArray(result.title_suggestions) && result.title_suggestions.length) {
        titleSuggestionsList.innerHTML = result.title_suggestions
          .map(t => `<li>${t}</li>`)
          .join('');
        titleSuggestionsBox.style.display = '';
      } else {
        titleSuggestionsList.innerHTML = '';
        titleSuggestionsBox.style.display = 'none';
      }

      loadingCard.style.display = 'none';

    } catch (err) {
      alert('재생성 실패: ' + err.message);
      loadingCard.style.display = 'none';
      resultBox.textContent = '리뷰가 여기에 표시됩니다.';
      resultBox.style.color = 'var(--muted)';
    }
  });

  // 복사
  document.getElementById('copyBtn').addEventListener('click', function () {
    const btn = this;
    navigator.clipboard.writeText(resultBox.textContent).then(() => {
      btn.textContent = '복사됨!';
      setTimeout(() => { btn.textContent = '복사'; }, 2000);
    });
  });

  // 초기화
  document.getElementById('resetBtn').addEventListener('click', function () {
    userInput.value = '';
    resultBox.textContent = '리뷰가 여기에 표시됩니다.';
    resultBox.style.color = 'var(--muted)';
    charCount.textContent = '0자';
    titleSuggestionsList.innerHTML = '';
    titleSuggestionsBox.style.display = 'none';
    tokenInfo.style.display = 'none';
    costInfo.style.display = 'none';
    promptEditor.value = '';
    promptCard.open = false;
    currentReviewId = null;
  });

  // 수정 저장
  document.getElementById('saveEditedBtn')?.addEventListener('click', async function () {
    const edited = resultBox.textContent.trim();
    if (!currentReviewId) {
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
        body: JSON.stringify({
          review_id: currentReviewId,
          edited_text: edited
        })
      });
      const result = await response.json();
      if (result.error) throw new Error(result.error);
      currentReviewId = result.review_id;
      charCount.textContent = `${result.char_count}자`;
      if (Array.isArray(result.title_suggestions) && result.title_suggestions.length) {
        titleSuggestionsList.innerHTML = result.title_suggestions.map(t => `<li>${t}</li>`).join('');
        titleSuggestionsBox.style.display = '';
      }
      alert('수정본이 저장되었습니다.');
    } catch (err) {
      alert('수정 저장 실패: ' + err.message);
    }
  });
});
// 프롬프트 복사
document.getElementById('copyPromptBtn').addEventListener('click', function() {
  navigator.clipboard.writeText(promptEditor.value).then(() => {
    this.textContent = '복사됨!';
    setTimeout(() => { this.textContent = '복사'; }, 2000);
  });
});

// 템플릿 목록 로드
const templateSelect = document.getElementById('templateSelect');
let templatesData = [];

async function loadTemplates() {
  try {
    const response = await fetch('/dashboard/api/prompt-templates/?mode=basic');
    const data = await response.json();
    templatesData = data.templates || [];

    // 기존 옵션 유지 (기본 템플릿)
    templateSelect.innerHTML = '<option value="">기본 템플릿</option>';

    templatesData.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = t.name + (t.is_default ? ' (기본)' : '');
      if (t.is_default) {
        opt.selected = true;
      }
      templateSelect.appendChild(opt);
    });
  } catch (err) {
    console.error('템플릿 로드 실패:', err);
  }
}

// 템플릿 미리보기
document.getElementById('previewTemplateBtn').addEventListener('click', async function() {
  const templateId = templateSelect.value;

  if (!templateId) {
    alert('기본 템플릿이 선택되어 있습니다. 다른 템플릿을 선택해주세요.');
    return;
  }

  const template = templatesData.find(t => t.id == templateId);
  if (template) {
    // 간단한 모달로 표시
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;';
    modal.innerHTML = `
      <div style="background:white;border-radius:12px;max-width:800px;width:90%;max-height:80vh;display:flex;flex-direction:column;">
        <div style="padding:16px 20px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;">
          <h3 style="margin:0;font-size:1.1rem;">${template.name} (v${template.version})</h3>
          <button style="background:none;border:none;font-size:1.5rem;cursor:pointer;" onclick="this.closest('div[style*=fixed]').remove()">&times;</button>
        </div>
        <div style="padding:20px;overflow-y:auto;">
          <pre style="white-space:pre-wrap;word-break:break-word;font-size:0.85rem;line-height:1.6;margin:0;">${template.content}</pre>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });
  }
});

// 페이지 로드 시 템플릿 로드
loadTemplates();
