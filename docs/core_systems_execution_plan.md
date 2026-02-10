# Core Systems Execution Plan

기준일: 2026-02-09  
대상: `datalab_v3` (Django + Electron)

## 1) 목표

현재 앱 운영 안정성을 위해 아래 3개를 우선 구축한다.

1. 감사 로그(Audit Log)
2. 백그라운드 작업 큐 + 작업 상태 추적
3. 에러 추적 + 헬스 모니터링 통합

---

## 2) 우선순위 (권장 적용 순서)

1. 감사 로그
2. 작업 큐/상태 추적
3. 에러/헬스 모니터링

이 순서가 좋은 이유:
- 감사 로그가 먼저 있어야 권한 변경/실패 작업/관리자 액션의 원인을 남길 수 있다.
- 작업 큐를 붙이면 장시간 작업 안정성이 올라가고, 그다음 모니터링으로 장애 원인 분석이 쉬워진다.

---

## 3) 시스템별 구현 범위

### A. 감사 로그 (Audit Log)

#### A-1. 데이터 모델
- `apps/data/models.py`
- 신규 모델 `AuditEvent` 추가:
  - `actor`(FK User, null 가능)
  - `event_type` (예: `auth.login`, `permission.update`, `review.generate.request`)
  - `target_type`, `target_id`
  - `before_json`, `after_json`
  - `metadata_json` (IP, UA, source_page 등)
  - `created_at`

#### A-2. 기록 유틸
- `apps/data/services/audit_logger.py` 신규:
  - `log_audit_event(actor, event_type, target, before, after, metadata)`
- 예외가 나더라도 본 기능을 막지 않도록 안전하게 실패 처리

#### A-3. 기록 포인트 1차 적용
- `apps/data/views_permissions_api.py`
  - 권한 변경 API 성공 시 `permission.update` 기록
- `apps/dashboard/views.py`
  - 로그 삭제/관리자 작업 API 호출 시 `system.log.clear` 등 기록
- `apps/data/views_api.py` 또는 인증 관련 뷰
  - 로그인/로그아웃 성공 기록

#### A-4. 조회 API + Electron 페이지
- `apps/data/urls_api.py`에 `audit-events/` 추가
- `electron-llm-app/preload.js`에:
  - `getAuditEvents`
- 신규 페이지:
  - `electron-llm-app/renderer/audit_logs.html`
  - `electron-llm-app/renderer/js/audit_logs.js`
  - `electron-llm-app/renderer/css/audit_logs.css`
- 필수 UI: 기간/이벤트타입/사용자 필터, 상세 모달

#### A-5. 완료 기준
- 권한 변경 1건 수행 시 감사 로그가 1건 이상 남아야 함
- 로그 조회 화면에서 필터 + 상세 확인 가능

---

### B. 작업 큐 + 상태 추적

#### B-1. 1단계 방식 (현재 코드베이스 기준 권장)
- 외부 큐(Celery) 즉시 도입 대신 DB 기반 Job 모델로 시작
- 이유: 현재 저장소에서 Celery 운영 흔적이 명확하지 않음

#### B-2. 데이터 모델
- `apps/data/models.py`
- 신규 모델 `AsyncJob`
  - `job_type`, `status`(`queued/running/succeeded/failed/canceled`)
  - `payload_json`, `result_json`, `error_text`
  - `requested_by`, `started_at`, `finished_at`, `created_at`
  - `retry_count`, `max_retries`

#### B-3. 실행 서비스
- `apps/ml/services/job_runner.py` 신규
- 기본 인터페이스:
  - `enqueue_job(job_type, payload, user)`
  - `run_next_job()`
- 우선 대상 작업:
  - 리뷰 생성/대량 생성 요청

#### B-4. API
- `apps/data/urls_api.py`
  - `jobs/` (생성, 목록)
  - `jobs/<id>/` (상세)
  - `jobs/<id>/retry/`, `jobs/<id>/cancel/`

#### B-5. Electron UI
- `electron-llm-app/preload.js`
  - `createJob`, `getJobs`, `getJobDetail`, `retryJob`, `cancelJob`
- 신규 페이지:
  - `renderer/jobs_dashboard.html`, `renderer/js/jobs_dashboard.js`
- 필수 UI:
  - 상태칩, 진행시간, 실패 사유, 재시도 버튼

#### B-6. 완료 기준
- 리뷰 생성 요청이 Job으로 생성되고 상태 전이가 보임
- 실패 Job 재시도 가능

---

### C. 에러 추적 + 헬스 모니터링 통합

#### C-1. 에러 이벤트 수집
- `apps/data/models.py`
- 신규 모델 `ErrorEvent`
  - `source`(`backend`, `electron_renderer`, `electron_main`)
  - `severity`, `message`, `stack`, `context_json`, `created_at`

#### C-2. 백엔드 에러 후킹
- Django 전역 예외 핸들러 또는 middleware에서 `ErrorEvent` 기록
- 민감 정보 마스킹 (토큰/비밀번호)

#### C-3. Electron 에러 수집
- `electron-llm-app/main.js`
  - `uncaughtException`, `unhandledRejection` 캡처
- `electron-llm-app/renderer/js/app.js`
  - `window.onerror`, `unhandledrejection` 캡처
- `preload.js`를 통해 `/api/data/error-events/` 전송

#### C-4. 모니터링 통합
- 기존 `system_monitor` 확장:
  - 최근 24시간 에러 수
  - 심각도별 집계
  - 실패율 상위 API
- 파일:
  - `electron-llm-app/renderer/js/system_monitor.js`
  - `apps/data/views_monitor_api.py`

#### C-5. 완료 기준
- 의도적으로 예외 1건 발생 시 시스템 모니터 화면에서 확인 가능

---

## 4) 2주 실행 단위 (현실적 분할)

### Week 1
1. 감사 로그 모델 + 유틸 + 권한변경/로그인 기록
2. 감사 로그 조회 API + Electron 조회 화면
3. 최소 테스트(권한변경 시 로그 생성)

### Week 2
1. AsyncJob 모델 + API + 기본 runner
2. 리뷰 생성 흐름 Job 전환
3. system_monitor 에러 집계 카드 추가

---

## 5) 리스크와 대응

1. 로그 폭증
- 대응: 보관 주기(예: 90일), 페이지네이션, 인덱스

2. 큐 도입 시 기존 동기 흐름 충돌
- 대응: 기능 플래그로 단계적 전환

3. 민감정보 유출
- 대응: audit/error 저장 시 마스킹 정책 필수

---

## 6) 바로 착수할 첫 작업 (권장)

1. `AuditEvent` 모델/마이그레이션
2. `views_permissions_api.py` 권한 변경 이벤트 기록
3. `audit-events` 조회 API + 간단한 Electron 조회 페이지

