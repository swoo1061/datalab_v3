# MedViral v3 - AI 리뷰 생성 시스템

병의원 바이럴 마케팅을 위한 AI 기반 리뷰 생성 시스템입니다.

## 주요 기능

- **AI 리뷰 생성**: OpenAI GPT, Claude Sonnet/Opus 지원
- **Basic / PRO 모드**: 간편 입력 또는 상세 설정
- **병원 가이드 관리**: Notion MD Export → 자동 파싱
- **페르소나 시스템**: 다양한 작성자 스타일 설정
- **카페 프로필**: 플랫폼별 글자수, 금지단어 설정
- **스타일 분석**: 기존 글에서 스타일 추출
- **토큰/비용 추적**: 실시간 사용량 및 비용 표시

## 요구사항

- Python 3.10+
- OpenAI API Key 또는 Anthropic API Key

## 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/swoo1061/datalab_v3.git
cd datalab_v3
```

### 2. 가상환경 생성 (권장)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# .env 파일 편집하여 API 키 입력
```

**.env 파일 내용:**
```
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
```

### 5. 데이터베이스 설정

```bash
python manage.py migrate
```

### 6. 초기 데이터 로드 (선택)

```bash
python manage.py shell -c "from apps.data.initial_data import create_all; create_all()"
```

### 7. 서버 실행

```bash
python manage.py runserver
```

브라우저에서 http://127.0.0.1:8000 접속

## 사용 방법

### Basic 모드 (간편)
1. 대시보드 → AI 생성 Basic
2. 텍스트 영역에 자유롭게 입력 (병원명, 시술, 페르소나 등)
3. AI 모델 선택 후 "생성하기" 클릭

### PRO 모드 (상세)
1. 대시보드 → AI 생성 PRO
2. 병원 가이드 선택 → 원장/시술 선택
3. 페르소나, 카페 프로필, 컨텐츠 타입 설정
4. "리뷰 생성하기" 클릭

## AI 모델 및 가격

| 모델 | Input ($/1M) | Output ($/1M) | 특징 |
|------|-------------|---------------|------|
| GPT-5 Mini | $0.25 | $2.00 | 저렴, 기본 품질 |
| GPT-5.2 | $1.75 | $14.00 | 빠름, 고품질 |
| Claude Sonnet 4.5 | $3.00 | $15.00 | 빠름, 고품질 (추천) |
| Claude Opus 4.5 | $5.00 | $25.00 | 최고 품질 |

## 프로젝트 구조

```
datalab_v3/
├── config/              # Django 설정
├── apps/
│   ├── dashboard/       # 웹 UI (뷰, 템플릿)
│   ├── data/            # 데이터 모델
│   └── ml/services/     # LLM 서비스, 파서
├── docs/                # 문서
├── .env.example         # 환경변수 예시
├── requirements.txt     # 의존성
└── manage.py
```

## 환경변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `DJANGO_SECRET_KEY` | Django 시크릿 키 | O |
| `OPENAI_API_KEY` | OpenAI API 키 | △ |
| `ANTHROPIC_API_KEY` | Claude API 키 | △ |
| `DEBUG` | 디버그 모드 | X (기본: True) |

※ OpenAI 또는 Anthropic API 키 중 하나 이상 필요

## 문제 해결

### API 키 오류
```
OPENAI_API_KEY가 설정되지 않았습니다
```
→ `.env` 파일에 API 키가 제대로 설정되었는지 확인

### 마이그레이션 오류
```bash
python manage.py migrate --run-syncdb
```

### 포트 충돌
```bash
# 다른 포트로 실행
python manage.py runserver 8080
```

## 라이선스

내부용 프로젝트
