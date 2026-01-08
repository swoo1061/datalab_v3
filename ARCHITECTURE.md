# MedViral v3 - 시스템 아키텍처

## 프로젝트 개요
의료 마케팅용 AI 리뷰 생성 시스템. Claude API를 활용하여 병원/시술 정보 기반의 자연스러운 리뷰 콘텐츠를 생성.

---

## 프로젝트 구조

```
medviral_v3/
├── config/                    # Django 프로젝트 설정
│   ├── settings.py           # 환경설정 (DB, API키 등)
│   ├── urls.py               # 루트 URL 라우팅
│   └── wsgi.py               # WSGI 서버 설정
│
├── apps/
│   ├── dashboard/            # 메인 웹 대시보드
│   │   ├── views.py          # 뷰 로직 (페이지 + API)
│   │   ├── urls.py           # URL 라우팅
│   │   └── templates/        # HTML 템플릿
│   │
│   ├── data/                 # 데이터 모델
│   │   ├── models.py         # Django ORM 모델 정의
│   │   ├── admin.py          # 관리자 페이지
│   │   └── initial_data.py   # 초기 데이터
│   │
│   └── ml/                   # AI/ML 서비스
│       └── services/
│           ├── llm_service.py        # Claude API 호출
│           ├── prompt_generator.py   # 프롬프트 빌더
│           ├── clinic_parser.py      # 병원 MD 파일 파서
│           ├── style_analyzer.py     # 문체 분석
│           └── content_type_analyzer.py  # 컨텐츠 유형 분석
│
└── manage.py
```

---

## 데이터 모델 (ERD 개요)

### 핵심 모델

| 모델 | 설명 | 주요 필드 |
|------|------|-----------|
| **ClinicGuide** | 병원 정보 | name, doctors[], price_list[], consultants[] |
| **Persona** | 작성자 페르소나 (26개 항목) | age_group, gender, 말투, 경험 등 |
| **CafeProfile** | 타겟 플랫폼 설정 (21개 항목) | platform_type, 글자수, 규칙 등 |
| **ContentTypeProfile** | 컨텐츠 유형 프로필 | 추천받기, 발품, 상담, 시술당일, 1개월후, 2개월+ |
| **GeneratedReview** | 생성된 리뷰 기록 | clinic, persona, cafe, generated_text |

### 모델 관계
```
ClinicGuide ──┬── doctors[] (JSON)
              ├── price_list[] (JSON)
              └── consultants[] (JSON)

GeneratedReview ──┬── ClinicGuide (FK)
                  ├── Persona (FK)
                  └── CafeProfile (FK)
```

---

## 리뷰 생성 모드 비교

| 구분 | Basic | Pro (v2) |
|------|-------|----------|
| **입력 방식** | 자유형 텍스트 | 9단계 구조화된 폼 |
| **DB 연동** | ❌ | ✅ 병원/의료진/시술 자동 로드 |
| **페르소나** | 텍스트 기술 | 26개 항목 드롭다운 선택 |
| **카페 설정** | 텍스트 기술 | 21개 항목 드롭다운 선택 |
| **컨텐츠 유형** | 자유 기술 | 6가지 프리셋 + 세부설정 |
| **프롬프트 사전생성** | ❌ | ✅ |
| **피드백 재생성** | ❌ | ✅ |
| **URL** | /generate/basic/ | /generate/pro/ |

---

## API 엔드포인트

### 리뷰 생성
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/generate-basic/` | Basic 모드 리뷰 생성 |
| POST | `/api/generate/` | Pro 모드 리뷰 생성 |
| POST | `/api/generate-prompt/` | 프롬프트만 생성 (Pro) |
| POST | `/api/regenerate/` | 피드백 반영 재생성 (Pro) |

### 병원 데이터
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/clinic/{id}/doctors/` | 병원별 의료진 목록 |
| GET | `/api/clinic/{id}/procedures/{doctor}/` | 의료진별 시술 목록 |
| POST | `/api/import-clinic/` | MD 파일에서 병원 임포트 |

### 스타일 분석
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/analyze-style/` | 텍스트 문체 분석 |
| POST | `/api/create-persona-from-style/` | 분석결과 → 페르소나 생성 |
| POST | `/api/create-cafe-from-style/` | 분석결과 → 카페프로필 생성 |

### 프리셋 관리
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/persona-presets/` | 페르소나 프리셋 목록 |
| GET | `/api/cafe-presets/` | 카페 프리셋 목록 |
| POST | `/api/load-persona-presets/` | 페르소나 프리셋 로드 |

---

## 데이터 플로우

### Basic 모드
```
[사용자 입력 (텍스트)]
        ↓
[기본 프롬프트 템플릿에 삽입]
        ↓
[Claude API 호출]
        ↓
[리뷰 텍스트 반환]
```

### Pro 모드
```
[병원 선택] → [의료진 선택] → [시술 선택]
        ↓
[컨텐츠 유형 선택] → [페르소나 선택] → [카페 설정 선택]
        ↓
[ReviewPromptBuilder: 멀티섹션 프롬프트 생성]
  ├── 헤더 섹션
  ├── 컨텐츠 유형 섹션
  ├── 페르소나 섹션
  ├── 카페 규칙 섹션
  ├── 병원/의료진/시술 정보 섹션
  ├── 상담 프로세스 섹션
  └── 작성 가이드라인 섹션
        ↓
[Claude API 호출 (llm_service.py)]
        ↓
[리뷰 텍스트 + 토큰/비용 정보 반환]
        ↓
(선택) [피드백 입력 → 재생성]
```

---

## 주요 서비스 모듈

### 1. llm_service.py
Claude API 호출 담당
- `generate_review()`: 리뷰 생성
- 토큰 사용량, 비용 계산
- 캐시 토큰 지원

### 2. prompt_generator.py
프롬프트 빌드 담당
- `ReviewPromptBuilder` 클래스
- `build_review_prompt()`: 전체 프롬프트 조합
- `build_prompt_from_models()`: Django 모델에서 프롬프트 생성

### 3. clinic_parser.py
병원 MD 파일 파싱
- 의료진 정보 추출
- 수가표 파싱
- 상담실장 정보 추출

### 4. style_analyzer.py
리뷰 문체 분석
- 기존 리뷰에서 말투/스타일 추출
- 페르소나/카페 프로필 자동 생성

---

## 페이지 구성

| URL | 페이지 | 설명 |
|-----|--------|------|
| `/` | 대시보드 홈 | 통계 및 바로가기 |
| `/generate/basic/` | Basic 리뷰 생성 | 간단한 텍스트 입력 |
| `/generate/pro/` | Pro 리뷰 생성 | 구조화된 9단계 입력 |
| `/generated/` | 생성 리뷰 목록 | 생성된 리뷰 관리 |
| `/clinics/` | 병원 관리 | 병원 가이드 CRUD |
| `/personas/` | 페르소나 관리 | 페르소나 CRUD |
| `/cafes/` | 카페 프로필 관리 | 카페 설정 CRUD |
| `/content-types/` | 컨텐츠 유형 관리 | 컨텐츠 타입 CRUD |
| `/style-analyzer/` | 스타일 분석기 | 문체 분석 → 프리셋 생성 |

---

## 기술 스택

- **Backend**: Django 4.x
- **Database**: SQLite (개발) / PostgreSQL (운영)
- **AI**: Claude API (Anthropic)
- **Frontend**: HTML + Tailwind CSS + Alpine.js
- **파일 파싱**: Markdown (병원 가이드)

---

## 환경 변수

```env
ANTHROPIC_API_KEY=sk-ant-xxx    # Claude API 키
DEBUG=True                       # 디버그 모드
SECRET_KEY=xxx                   # Django 시크릿 키
```
