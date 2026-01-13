# MedViral v3 - AI 리뷰 생성 시스템

병의원 바이럴 마케팅을 위한 AI 기반 리뷰/후기 생성 시스템입니다.

---

## 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [시스템 구조](#시스템-구조)
- [설치 및 설정](#설치-및-설정)
- [사용자 가이드](#사용자-가이드)
- [관리자 가이드](#관리자-가이드)
- [개발자 가이드](#개발자-가이드)
- [API 레퍼런스](#api-레퍼런스)
- [문제 해결](#문제-해결)

---

## 개요

MedViral v3는 병의원 마케팅용 리뷰/후기 콘텐츠를 AI로 자동 생성하는 시스템입니다.

### 핵심 가치
- **자연스러운 리뷰**: 실제 고객이 작성한 것 같은 자연스러운 후기 생성
- **맞춤형 페르소나**: 연령, 성별, 말투 등 26개 항목의 세밀한 캐릭터 설정
- **플랫폼 최적화**: 네이버 카페, 블로그, 앱 리뷰 등 플랫폼별 규칙 준수
- **비용 효율**: 실시간 토큰/비용 추적으로 마케팅 비용 관리

---

## 주요 기능

### 리뷰 생성
| 모드 | 설명 | 사용 시점 |
|------|------|----------|
| **Basic** | 자유 텍스트 입력 → 리뷰 생성 | 빠른 생성, 간단한 리뷰 |
| **Basic+** | 스타일 기반 생성 + 프롬프트 미리보기 | 스타일 커스터마이징 |
| **PRO** | 병원 가이드 + 페르소나 + 카페 설정 조합 | 정교한 맞춤 리뷰 |
| **앱 리뷰** | 강남언니 등 앱 플로우에 맞춘 후기 | 앱 리뷰 전용 |

### 프리셋 시스템
| 프리셋 | 항목 수 | 설명 |
|--------|--------|------|
| **페르소나** | 26개 | 작성자 캐릭터 (연령, 말투, 이모지 등) |
| **카페 프로필** | 21개 | 플랫폼 규칙 (글자수, 금지단어 등) |
| **컨텐츠 타입** | 6종 | 글 유형별 구조 (상담후기, 시술당일 등) |

### 병원 가이드
- Notion 마크다운 파일 자동 파싱
- 의료진, 시술, 가격 정보 구조화
- 리뷰 생성 시 자동 참조

### 보조 기능
- **스타일 추출**: 기존 글에서 말투/구조 분석
- **프롬프트 관리**: DB 기반 프롬프트 템플릿 버전 관리
- **접속 로그**: IP 기반 접속 기록

---

## 시스템 구조

### 디렉토리 계층
```
medviral_v3/
├── config/                     # Django 설정
│   ├── settings.py            # 환경 설정
│   ├── urls.py                # 루트 URL 라우팅
│   └── wsgi.py                # WSGI 진입점
│
├── apps/                       # 애플리케이션
│   ├── dashboard/             # 웹 UI
│   │   ├── views.py           # 뷰 함수 (2400+ lines)
│   │   ├── urls.py            # URL 라우팅
│   │   ├── middleware.py      # 접속 로그 미들웨어
│   │   └── templates/         # HTML 템플릿
│   │       └── dashboard/
│   │           ├── base.html                    # 기본 레이아웃
│   │           ├── index.html                   # 대시보드 홈
│   │           ├── review_generate_basic.html   # Basic 생성
│   │           ├── review_generate_basic_plus.html  # Basic+ 생성
│   │           ├── review_generate_v2.html      # PRO 생성
│   │           ├── app_review_gangnam.html      # 강남언니 앱 리뷰
│   │           ├── persona_list.html            # 페르소나 목록
│   │           ├── cafe_list.html               # 카페 설정 목록
│   │           ├── clinic_list.html             # 병원 가이드 목록
│   │           ├── prompt_template_list.html    # 프롬프트 관리
│   │           └── ...
│   │
│   ├── data/                  # 데이터 모델
│   │   ├── models.py          # 전체 모델 정의
│   │   ├── initial_data.py    # 초기 데이터/프리셋
│   │   └── admin.py           # Django Admin 설정
│   │
│   └── ml/                    # AI/ML 서비스
│       └── services/
│           ├── llm_service.py         # LLM API 호출
│           ├── prompt_generator.py    # 프롬프트 빌더
│           ├── style_analyzer.py      # 스타일 분석
│           ├── clinic_parser.py       # MD 파일 파서
│           └── content_type_analyzer.py
│
├── docs/                       # 문서
├── db.sqlite3                  # SQLite 데이터베이스
├── manage.py                   # Django CLI
├── requirements.txt            # 의존성
└── .env                        # 환경변수 (비공개)
```

### 데이터 모델
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Persona      │     │   CafeProfile   │     │ ContentTypeProfile│
│  (작성자 설정)   │     │  (플랫폼 설정)   │     │   (글 유형 설정)  │
│  - 26개 항목    │     │  - 21개 항목    │     │   - 6종 타입     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ClinicGuide   │────▶│ GeneratedReview │◀────│ PromptTemplate  │
│  (병원 가이드)   │     │   (생성된 리뷰)  │     │  (프롬프트 관리)  │
│  - 의료진/시술   │     │   - 결과물 저장  │     │  - 버전 관리     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 기술 스택
| 구분 | 기술 |
|------|------|
| Backend | Django 4.2, Python 3.10+ |
| Frontend | Vanilla JS, CSS Variables |
| Database | SQLite (개발), PostgreSQL (운영) |
| AI | OpenAI GPT, Anthropic Claude |

---

## 설치 및 설정

### 요구사항
- Python 3.10 이상
- OpenAI API Key 또는 Anthropic API Key

### 설치 단계

```bash
# 1. 저장소 클론
git clone https://github.com/swoo1061/datalab_v3.git
cd datalab_v3

# 2. 가상환경 생성
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 입력

# 5. DB 마이그레이션
python manage.py migrate

# 6. 초기 데이터 로드 (선택)
python manage.py shell -c "from apps.data.initial_data import create_all; create_all()"

# 7. 서버 실행
python manage.py runserver
```

### 환경변수 (.env)
```env
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
```

---

## 사용자 가이드

### Basic 모드 (간편 생성)
1. 사이드바 → **✨ Basic** 클릭
2. 텍스트 영역에 자유롭게 입력
   ```
   강남 A성형외과 눈매교정 후기
   20대 후반 여성, 붙임머리 스타일
   시술 후 3일차, 만족스러움
   ```
3. AI 모델 선택 → **생성하기** 클릭
4. 결과 확인 및 복사

### Basic+ 모드 (스타일 기반)
1. 사이드바 → **⚡ Basic+** 클릭
2. **탭 1**: 직접 입력 (Basic과 동일)
3. **탭 2**: 기존 글에서 스타일 추출 → 새 글 생성
4. **탭 3**: 프롬프트 미리보기 및 수정

### PRO 모드 (상세 설정)
1. 사이드바 → **🚀 PRO** 클릭
2. 병원 가이드 선택 → 원장/시술 선택
3. 페르소나, 카페 프로필, 컨텐츠 타입 선택
4. 옵션 조정 (글자수, 이모지 등)
5. **리뷰 생성하기** 클릭

### 강남언니 앱 리뷰
1. 사이드바 → **💄 강남언니** 클릭
2. 시술 정보 입력 (병원명, 시술종류, 날짜 등)
3. 페르소나/경험 설정 (접이식 메뉴)
4. **후기 생성하기** 클릭
5. 앱 입력 순서대로 결과 표시
   - 시술 전 고민 → 태그 선택 → 결과 후기 → 별점 등

### 스타일 추출
1. 사이드바 → **🔍 프리셋 추출** 클릭
2. 기존 리뷰 텍스트 붙여넣기
3. **스타일 분석하기** 클릭
4. 분석 결과를 페르소나/카페 프리셋으로 저장

---

## 관리자 가이드

### 병원 가이드 관리
1. **🏥 병원 가이드** 메뉴
2. **MD 파일 가져오기**로 Notion 마크다운 업로드
3. 자동 파싱: 의료진, 시술, 가격, 특징 추출
4. 비활성화/삭제로 목록 관리

### 프리셋 관리
| 메뉴 | 기능 |
|------|------|
| **👤 페르소나** | 작성자 캐릭터 추가/수정/삭제 |
| **☕ 카페 셋팅** | 플랫폼별 규칙 설정 |
| **📄 컨텐츠 타입** | 글 유형 구조 설정 |

### 프롬프트 관리
1. **📝 프롬프트 관리** 메뉴
2. 모드별 탭: Basic, Basic+, PRO, 앱 등
3. 템플릿 수정 시 자동 버전 관리
4. **기본 설정**으로 기본 템플릿 지정
5. 이전 버전 복원 가능

### 서버 설정
1. **⚙️ 서버 설정** 메뉴
2. 접속 로그 확인 (IP, 경로, 시간)
3. 로그 일괄 삭제

---

## 개발자 가이드

### 새 리뷰 생성 모드 추가

1. **모델 수정** (`apps/data/models.py`)
```python
class PromptTemplate(models.Model):
    MODE_CHOICES = [
        ...
        ('new_mode', '새 모드'),  # 추가
    ]
```

2. **뷰 함수 추가** (`apps/dashboard/views.py`)
```python
def new_mode_view(request):
    return render(request, "dashboard/new_mode.html")

def api_generate_new_mode(request):
    # API 로직
    pass
```

3. **URL 등록** (`apps/dashboard/urls.py`)
```python
path("generate/new-mode/", views.new_mode_view, name="new_mode"),
path("api/generate-new-mode/", views.api_generate_new_mode, name="api_generate_new_mode"),
```

4. **템플릿 생성** (`apps/dashboard/templates/dashboard/new_mode.html`)

5. **사이드바 추가** (`base.html`)
```html
<a href="{% url 'dashboard:new_mode' %}">🆕 새 모드</a>
```

### LLM 서비스 사용
```python
from apps.ml.services.llm_service import generate_review_with_prompt

result = generate_review_with_prompt(
    prompt="리뷰를 생성해주세요...",
    model="claude-sonnet-4-5-20250929",
    temperature=0.85,
    return_usage=True
)

print(result["text"])        # 생성된 텍스트
print(result["input_tokens"])  # 입력 토큰
print(result["output_tokens"]) # 출력 토큰
print(result["cost_usd"])      # 비용 (USD)
```

### 프롬프트 템플릿 변수
```python
# views.py에서 사용
prompt_vars = {
    'persona_age': '20대 후반',
    'hospital_name': 'A성형외과',
    'procedure_type': '눈매교정',
    # ...
}
prompt = template.content.format(**prompt_vars)
```

### 초기 데이터 추가
```python
# apps/data/initial_data.py
PERSONA_PRESETS = [
    {
        "name": "새 페르소나",
        "age_group": "20_late",
        # ...
    }
]

def create_all():
    create_personas()
    create_cafes()
    create_content_types()
    create_prompt_templates()
```

---

## API 레퍼런스

### 리뷰 생성

#### POST `/dashboard/api/generate-basic/`
Basic 모드 리뷰 생성

**Request:**
```json
{
  "input_text": "강남 A성형외과 눈매교정 후기...",
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.85
}
```

**Response:**
```json
{
  "success": true,
  "review": "생성된 리뷰 텍스트...",
  "usage": {
    "input_tokens": 500,
    "output_tokens": 800,
    "cost_usd": 0.0045,
    "cost_krw": 6.5
  }
}
```

#### POST `/dashboard/api/generate-gangnam-review/`
강남언니 앱 리뷰 생성

**Request:**
```json
{
  "hospital_name": "A성형외과",
  "procedure_type": "눈매교정",
  "procedure_date": "2025-01-10",
  "write_date": "2025-01-13",
  "persona_age": "20대 중후반",
  "satisfaction_level": "매우 만족",
  "model": "claude-sonnet-4-5-20250929"
}
```

### 스타일 분석

#### POST `/dashboard/api/analyze-style/`
텍스트에서 스타일 추출

**Request:**
```json
{
  "text": "분석할 기존 리뷰 텍스트..."
}
```

**Response:**
```json
{
  "success": true,
  "persona": { ... },
  "cafe": { ... },
  "content_type": { ... }
}
```

### 프롬프트 템플릿

#### GET `/dashboard/api/prompt-templates/`
템플릿 목록 조회

#### POST `/dashboard/api/prompt-templates/<pk>/set-default/`
기본 템플릿 설정

---

## AI 모델 및 가격

| 모델 | Input ($/1M) | Output ($/1M) | 특징 |
|------|-------------|---------------|------|
| GPT-4o Mini | $0.15 | $0.60 | 저렴, 기본 품질 |
| GPT-4o | $2.50 | $10.00 | 빠름, 고품질 |
| Claude Sonnet 4.5 | $3.00 | $15.00 | **추천**, 빠름, 고품질 |
| Claude Opus 4.5 | $15.00 | $75.00 | 최고 품질, 고비용 |

---

## 문제 해결

### API 키 오류
```
ANTHROPIC_API_KEY가 설정되지 않았습니다
```
→ `.env` 파일에 API 키 확인

### 마이그레이션 오류
```bash
python manage.py migrate --run-syncdb
```

### 포트 충돌
```bash
python manage.py runserver 8080
```

### 프롬프트 템플릿 변수 오류
```
KeyError: 'variable_name'
```
→ `views.py`의 `prompt_vars` 딕셔너리에 변수 추가 필요

### 초기 데이터 로드
```bash
python manage.py shell -c "from apps.data.initial_data import create_all; create_all()"
```

---

## 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v060109 | 2025-01-13 | 강남언니 앱 리뷰 생성, 시술일자/작성일자 |
| v060108 | 2025-01-12 | 프롬프트 관리 기능 |
| v060107 | 2025-01-11 | Basic+ 스타일 추출 |

---

## 라이선스

내부용 프로젝트 - 무단 배포 금지

---

## 문의

- GitHub Issues: https://github.com/swoo1061/datalab_v3/issues
