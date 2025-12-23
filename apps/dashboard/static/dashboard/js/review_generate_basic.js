document.addEventListener('DOMContentLoaded', () => {
  const userInput = document.getElementById('userInput');
  const resultBox = document.getElementById('resultBox');
  const charCount = document.getElementById('charCount');
  const tokenInfo = document.getElementById('tokenInfo');
  const costInfo = document.getElementById('costInfo');
  const loadingCard = document.getElementById('loadingCard');
  const generateBtn = document.getElementById('generateBtn');
  const promptEditor = document.getElementById('promptEditor');
  const promptCard = document.getElementById('promptCard');

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
    const input = userInput.value.trim();
    const selectedModel =
      document.querySelector('input[name="model"]:checked')?.value
      || 'claude-sonnet-4-5-20250929';

    if (!input) {
      alert('리뷰 정보를 입력해주세요.');
      return;
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
    tokenInfo.style.display = 'none';
    costInfo.style.display = 'none';
    promptEditor.value = '';
    promptCard.open = false;
  });
});