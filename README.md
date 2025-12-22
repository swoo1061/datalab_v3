# MedViral - 병의원 바이럴 마케팅 자동화 시스템

AI 기반 리뷰 생성 시스템으로, Notion에서 관리하는 병원 가이드를 기반으로 자연스러운 리뷰를 생성합니다.

## 주요 기능

- 🏥 **병원 가이드 관리**: Notion MD Export → 자동 파싱 → DB 저장
- 👨‍⚕️ **의료진/시술 정보**: 원장별 스타일, 주력시술, 수가표 관리
- 👤 **페르소나 시스템**: 20대 직장인, 30대 주부 등 다양한 작성자 설정
- 📝 **카페별 설정**: 글자수 제한, 금지 단어, 필수 섹션 등
- ✨ **AI 리뷰 생성**: GPT-4o-mini 기반 자연스러운 리뷰 생성
- 🔄 **피드백 반영**: 수정 요청 후 재생성 기능

## 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
export OPENAI_API_KEY="your-api-key"
export DJANGO_SECRET_KEY="your-secret-key"

# 3. DB 마이그레이션
python manage.py migrate

# 4. 초기 데이터 로드 (페르소나, 카페 프리셋)
python manage.py shell < apps/data/initial_data.py

# 5. 서버 실행
python manage.py runserver
```

## 사용 방법

### 1. 병원 가이드 추가

1. Notion에서 병원 가이드 페이지 열기
2. ⋯ → Export → Markdown & CSV
3. 다운받은 .md 파일 열기
4. 대시보드 → 병원 가이드 추가 → MD 내용 붙여넣기

### 2. 리뷰 생성

1. 대시보드 → AI 리뷰 생성
2. 병원 선택 → 원장님 선택 → 시술 선택
3. (선택) 페르소나, 타겟 카페 설정
4. "리뷰 생성하기" 클릭
5. 결과 복사하여 사용

### 3. 리뷰 수정

1. 생성된 리뷰에서 "수정 요청" 클릭
2. 피드백 입력 (예: "좀 더 짧게", "이모지 추가")
3. "수정 반영하여 재생성" 클릭

## 프로젝트 구조

```
medviral/
├── config/
│   ├── settings.py      # Django 설정
│   ├── urls.py          # URL 라우팅
│   └── wsgi.py
├── apps/
│   ├── data/
│   │   ├── models.py    # 데이터 모델
│   │   ├── admin.py     # Admin 설정
│   │   └── initial_data.py  # 초기 데이터
│   ├── ml/
│   │   └── services/
│   │       ├── clinic_parser.py     # MD 파서
│   │       ├── prompt_generator.py  # 프롬프트 생성
│   │       └── llm_service.py       # LLM 호출
│   └── dashboard/
│       ├── views.py     # 뷰
│       ├── urls.py      # URL
│       └── templates/   # 템플릿
├── manage.py
└── requirements.txt
```

## 데이터 모델

- **ClinicGuide**: 병원 정보 (위치, 의료진, 수가표, 사후관리 등)
- **Persona**: 작성자 페르소나 (말투, 연령대, 이모지 사용 등)
- **CafeProfile**: 카페 설정 (글자수, 금지단어, 필수섹션 등)
- **GeneratedReview**: 생성된 리뷰 기록

## API 엔드포인트

- `GET /dashboard/api/clinic/{id}/doctors/` - 병원 의료진 목록
- `GET /dashboard/api/clinic/{id}/procedures/{doctor_code}/` - 시술 목록
- `POST /dashboard/api/generate/` - 리뷰 생성
- `POST /dashboard/api/regenerate/` - 피드백 반영 재생성
- `POST /dashboard/api/import-clinic/` - 병원 가이드 임포트

## 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 | (필수) |
| `DJANGO_SECRET_KEY` | Django 시크릿 키 | dev용 키 |
| `DEBUG` | 디버그 모드 | True |
| `ALLOWED_HOSTS` | 허용 호스트 | localhost,127.0.0.1 |

## 라이선스

내부용 프로젝트
