// 데이터 저장용
let currentClinicData = null;
let currentReviewId = null;

// DOM 요소
const clinicSelect = document.getElementById('clinicSelect');
const doctorSelect = document.getElementById('doctorSelect');
const procedureSelect = document.getElementById('procedureSelect');
const contentTypeSelect = document.getElementById('contentTypeSelect');
const personaSelect = document.getElementById('personaSelect');
const cafeSelect = document.getElementById('cafeSelect');
const consultantSelect = document.getElementById('consultantSelect');
const reviewForm = document.getElementById('reviewForm');
const resultCard = document.getElementById('resultCard');
const loadingCard = document.getElementById('loadingCard');
const resultBox = document.getElementById('resultBox');
const charCount = document.getElementById('charCount');
const tokenInfo = document.getElementById('tokenInfo');
const costInfo = document.getElementById('costInfo');
const promptEditor = document.getElementById('promptEditor');
const promptCard = document.getElementById('promptCard');
const generatePromptBtn = document.getElementById('generatePromptBtn');
const generateReviewBtn = document.getElementById('generateReviewBtn');
const editCard = document.getElementById('editCard');

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

// 직접입력 토글 함수
function setupCustomInput(selectId, customInputId) {
  const select = document.getElementById(selectId);
  const customInput = document.getElementById(customInputId);

  select.addEventListener('change', function() {
    if (this.value === '__custom__') {
      customInput.style.display = 'block';
      customInput.querySelector('input').focus();
    } else {
      customInput.style.display = 'none';
    }
  });
}

// 모든 직접입력 필드 설정
setupCustomInput('clinicSelect', 'clinicCustomInput');
setupCustomInput('doctorSelect', 'doctorCustomInput');
setupCustomInput('procedureSelect', 'procedureCustomInput');
setupCustomInput('contentTypeSelect', 'contentTypeCustomInput');
setupCustomInput('personaSelect', 'personaCustomInput');
setupCustomInput('cafeSelect', 'cafeCustomInput');
setupCustomInput('consultantSelect', 'consultantCustomInput');

// 병원 선택 시
clinicSelect.addEventListener('change', async function() {
  const clinicId = this.value;

  // 없음 또는 직접입력 선택 시
  if (!clinicId || clinicId === '__none__' || clinicId === '__custom__') {
    // 직접입력일 경우 의료진/시술도 직접입력 모드로
    if (clinicId === '__custom__') {
      // 의료진 select에 기본 옵션 유지
    }
    return;
  }

  // API로 의료진 데이터 로드
  try {
    const response = await fetch(`/dashboard/api/clinic/${clinicId}/doctors/`);
    const data = await response.json();
    const doctors = data.doctors || [];
    const consultants = data.consultants || [];

    // 의료진 드롭다운 업데이트
    doctorSelect.innerHTML = '<option value="">원장님을 선택하세요</option><option value="__none__">없음</option><option value="__custom__">직접입력</option>';
    doctors.forEach(doc => {
      const opt = document.createElement('option');
      opt.value = doc.code;
      opt.textContent = `${doc.name} 원장님 (${doc.code})`;
      opt.dataset.style = doc.style || '';
      opt.dataset.specialties = JSON.stringify(doc.specialties || []);
      doctorSelect.appendChild(opt);
    });

    // 상담실장 드롭다운 업데이트
    consultantSelect.innerHTML = '<option value="">랜덤 또는 미지정</option><option value="__none__">없음</option><option value="__custom__">직접입력</option>';
    consultants.forEach(cons => {
      const opt = document.createElement('option');
      opt.value = cons.name;
      opt.textContent = `${cons.name} 실장님 (${cons.age || ''}세, ${cons.style || ''})`;
      consultantSelect.appendChild(opt);
    });

  } catch (e) {
    console.error('의료진 데이터 로드 오류:', e);
  }
});

// 원장 선택 시
doctorSelect.addEventListener('change', function() {
  const selected = this.options[this.selectedIndex];
  const doctorCode = this.value;

  // 직접입력 처리는 setupCustomInput에서 이미 처리됨
  if (!doctorCode || doctorCode === '__none__' || doctorCode === '__custom__') {
    document.getElementById('doctorInfo').textContent = '';
    return;
  }

  // 원장 정보 표시
  document.getElementById('doctorInfo').textContent = selected.dataset.style || '';

  // 시술 목록 로드 (API 호출)
  const clinicId = clinicSelect.value;
  if (!clinicId || clinicId === '__none__' || clinicId === '__custom__') return;

  fetch(`/dashboard/api/clinic/${clinicId}/procedures/${doctorCode}/`)
    .then(res => res.json())
    .then(data => {
      procedureSelect.innerHTML = '<option value="">시술을 선택하세요</option><option value="__none__">없음</option><option value="__custom__">직접입력</option>';
      data.procedures.forEach(proc => {
        const opt = document.createElement('option');
        opt.value = proc.procedure;
        opt.textContent = `${proc.procedure} (${proc.price_display || proc.price})`;
        procedureSelect.appendChild(opt);
      });
    })
    .catch(err => {
      console.error('시술 로드 오류:', err);
    });
});

// 컨텐츠 유형 선택 시
contentTypeSelect.addEventListener('change', function() {
  const selected = this.options[this.selectedIndex];
  if (this.value === '__none__' || this.value === '__custom__') {
    document.getElementById('contentTypeInfo').textContent = '';
    return;
  }
  if (selected.dataset.desc) {
    document.getElementById('contentTypeInfo').textContent = selected.dataset.desc;
  } else {
    document.getElementById('contentTypeInfo').textContent = '컨텐츠 유형에 따라 글의 구조와 톤이 달라집니다';
  }
});

// 페르소나 선택 시
personaSelect.addEventListener('change', function() {
  if (this.value === '__none__' || this.value === '__custom__') {
    document.getElementById('personaInfo').textContent = '';
    return;
  }
  document.getElementById('personaInfo').textContent = '';
});

// 카페 선택 시
cafeSelect.addEventListener('change', function() {
  const selected = this.options[this.selectedIndex];
  if (this.value === '__none__' || this.value === '__custom__') {
    document.getElementById('cafeInfo').textContent = '';
    return;
  }
  if (selected.dataset.min && selected.dataset.max) {
    document.getElementById('cafeInfo').textContent = `글자수: ${selected.dataset.min}~${selected.dataset.max}자`;
  } else {
    document.getElementById('cafeInfo').textContent = '';
  }
});

// 폼 데이터 수집 함수
function collectFormData() {
  const formData = new FormData(reviewForm);
  const data = Object.fromEntries(formData.entries());

  // 직접입력 값 처리
  if (data.clinic_id === '__custom__') {
    data.clinic_custom = document.getElementById('clinicCustomText').value;
  }
  if (data.doctor_code === '__custom__') {
    data.doctor_custom = document.getElementById('doctorCustomText').value;
  }
  if (data.procedure === '__custom__') {
    data.procedure = document.getElementById('procedureCustomText').value;
  }
  if (data.content_type === '__custom__') {
    data.content_type_custom = document.getElementById('contentTypeCustomText').value;
  }
  if (data.persona_id === '__custom__') {
    data.persona_custom = document.getElementById('personaCustomText').value;
  }
  if (data.cafe_id === '__custom__') {
    data.cafe_custom = document.getElementById('cafeCustomText').value;
  }
  if (data.consultant_name === '__custom__') {
    data.consultant_name = document.getElementById('consultantCustomText').value;
  }

  // '__none__' 값은 빈 문자열로 변환
  Object.keys(data).forEach(key => {
    if (data[key] === '__none__') data[key] = '';
  });

  return data;
}

// 프롬프트 생성 버튼
generatePromptBtn.addEventListener('click', async function() {
  const data = collectFormData();

  generatePromptBtn.disabled = true;
  generatePromptBtn.textContent = '⏳ 생성 중...';

  try {
    const response = await fetch('/dashboard/api/generate-prompt/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(result.error);
    }

    // 프롬프트 표시
    promptEditor.value = result.prompt;
    promptCard.open = true;  // details 열기
    generateReviewBtn.disabled = false;

  } catch (err) {
    alert('프롬프트 생성 실패: ' + err.message);
  } finally {
    generatePromptBtn.disabled = false;
    generatePromptBtn.textContent = '📝 프롬프트 생성';
  }
});

// 리뷰 생성 버튼 (폼 데이터로 프롬프트 새로 생성 후 리뷰 생성)
generateReviewBtn.addEventListener('click', async function() {
  const data = collectFormData();
  const selectedModel = document.querySelector('input[name="model"]:checked')?.value || 'claude-sonnet-4-5-20250929';

  // UI 업데이트
  loadingCard.style.display = 'block';
  editCard.style.display = 'none';
  resultBox.textContent = '생성 중...';
  resultBox.style.color = 'var(--muted)';
  generateReviewBtn.disabled = true;

  try {
    // 폼 데이터로 리뷰 생성 (프롬프트도 새로 생성됨)
    const response = await fetch('/dashboard/api/generate/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(result.error);
    }

    // 결과 표시
    resultBox.textContent = result.review;
    resultBox.style.color = '';  // 원래 색상으로 복원
    charCount.textContent = `${result.char_count}자`;
    currentReviewId = result.review_id;

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

    // 생성된 프롬프트 표시
    if (result.prompt_preview) {
      promptEditor.value = result.prompt_preview;
    }

    // 사용한 모델 표시
    const modelUsed = document.getElementById('modelUsed');
    if (result.model_used) {
      const isOpenAI = result.model_used.startsWith('gpt');
      modelUsed.textContent = isOpenAI ? `🤖 ${result.model_used}` : `🟣 ${result.model_used}`;
      modelUsed.style.display = 'inline-block';
    }

    loadingCard.style.display = 'none';

  } catch (err) {
    alert('생성 실패: ' + err.message);
    loadingCard.style.display = 'none';
    resultBox.textContent = '리뷰가 여기에 표시됩니다.';
    resultBox.style.color = 'var(--muted)';
  } finally {
    generateReviewBtn.disabled = false;
  }
});

// 폼 제출 방지 (엔터키 등)
reviewForm.addEventListener('submit', function(e) {
  e.preventDefault();
});

// 복사 버튼
document.getElementById('copyBtn').addEventListener('click', function() {
  navigator.clipboard.writeText(resultBox.textContent).then(() => {
    this.textContent = '✅ 복사됨!';
    setTimeout(() => { this.textContent = '📋 복사'; }, 2000);
  });
});

// 다시 생성 (현재 프롬프트 창의 내용으로 리뷰 재생성)
document.getElementById('regenerateBtn').addEventListener('click', async function() {
  const prompt = promptEditor.value.trim();
  const selectedModel = document.querySelector('input[name="model"]:checked')?.value || 'claude-sonnet-4-5-20250929';

  if (!prompt) {
    alert('프롬프트가 없습니다. 먼저 프롬프트를 생성하거나 입력해주세요.');
    return;
  }

  // UI 업데이트
  loadingCard.style.display = 'block';
  editCard.style.display = 'none';
  resultBox.textContent = '생성 중...';
  resultBox.style.color = 'var(--muted)';

  try {
    // 현재 프롬프트로 리뷰 생성
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

    // 결과 표시
    resultBox.textContent = result.review;
    resultBox.style.color = '';  // 원래 색상으로 복원
    charCount.textContent = `${result.char_count}자`;
    currentReviewId = result.review_id;

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

    // 사용한 모델 표시
    const modelUsed = document.getElementById('modelUsed');
    if (result.model_used) {
      const isOpenAI = result.model_used.startsWith('gpt');
      modelUsed.textContent = isOpenAI ? `🤖 ${result.model_used}` : `🟣 ${result.model_used}`;
      modelUsed.style.display = 'inline-block';
    }

    loadingCard.style.display = 'none';

  } catch (err) {
    alert('재생성 실패: ' + err.message);
    loadingCard.style.display = 'none';
    resultBox.textContent = '리뷰가 여기에 표시됩니다.';
    resultBox.style.color = 'var(--muted)';
  }
});

// 프롬프트 복사
document.getElementById('copyPromptBtn').addEventListener('click', function() {
  navigator.clipboard.writeText(promptEditor.value).then(() => {
    this.textContent = '✅ 복사됨!';
    setTimeout(() => { this.textContent = '📋 프롬프트 복사'; }, 2000);
  });
});

// 수정 요청 토글
document.getElementById('editBtn').addEventListener('click', function() {
  editCard.style.display = 'block';
});
document.getElementById('cancelEditBtn').addEventListener('click', function() {
  editCard.style.display = 'none';
});

// 수정 반영 재생성
document.getElementById('submitFeedbackBtn').addEventListener('click', async function() {
  const feedback = document.getElementById('feedbackInput').value;
  if (!feedback.trim()) {
    alert('수정 요청 내용을 입력해주세요.');
    return;
  }

  // 현재 선택된 모델 가져오기
  const selectedModel = document.querySelector('input[name="model"]:checked')?.value || 'claude-sonnet-4-5-20250929';

  loadingCard.style.display = 'block';
  editCard.style.display = 'none';
  resultBox.textContent = '수정 중...';
  resultBox.style.color = 'var(--muted)';

  try {
    const response = await fetch('/dashboard/api/regenerate/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        review_id: currentReviewId,
        feedback: feedback,
        model: selectedModel
      })
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(result.error);
    }

    resultBox.textContent = result.review;
    resultBox.style.color = '';  // 원래 색상으로 복원
    charCount.textContent = `${result.char_count}자`;
    currentReviewId = result.review_id;
    document.getElementById('feedbackInput').value = '';

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

    loadingCard.style.display = 'none';

  } catch (err) {
    alert('재생성 실패: ' + err.message);
    loadingCard.style.display = 'none';
    resultBox.textContent = '리뷰가 여기에 표시됩니다.';
    resultBox.style.color = 'var(--muted)';
  }
});

// 초기화
document.getElementById('resetBtn').addEventListener('click', function() {
  reviewForm.reset();
  doctorSelect.innerHTML = '<option value="">원장님을 선택하세요</option><option value="__none__">없음</option><option value="__custom__">직접입력</option>';
  procedureSelect.innerHTML = '<option value="">시술을 선택하세요</option><option value="__none__">없음</option><option value="__custom__">직접입력</option>';
  consultantSelect.innerHTML = '<option value="">랜덤 또는 미지정</option><option value="__none__">없음</option><option value="__custom__">직접입력</option>';
  editCard.style.display = 'none';
  document.getElementById('doctorInfo').textContent = '';
  document.getElementById('personaInfo').textContent = '';
  document.getElementById('cafeInfo').textContent = '';
  document.getElementById('contentTypeInfo').textContent = '컨텐츠 유형에 따라 글의 구조와 톤이 달라집니다';

  // 리뷰 결과 초기화
  resultBox.textContent = '리뷰가 여기에 표시됩니다.';
  resultBox.style.color = 'var(--muted)';
  charCount.textContent = '0자';
  tokenInfo.style.display = 'none';
  costInfo.style.display = 'none';
  document.getElementById('modelUsed').style.display = 'none';
  currentReviewId = null;

  // 프롬프트 영역 초기화
  promptEditor.value = '';
  promptCard.open = false;

  // 모든 직접입력 필드 숨기기 및 초기화
  document.querySelectorAll('.custom-input-wrap').forEach(el => {
    el.style.display = 'none';
    el.querySelector('input').value = '';
  });
});