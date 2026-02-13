import json
import random
import re
import uuid
from datetime import datetime, timedelta, time
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.ml.services.llm_service import (
    generate_review_with_prompt_enforced,
    generate_title_suggestions,
    generate_review_with_prompt,
    apply_review_type_guard,
)
from apps.ml.services.prompt_generator import build_ft_prompt_from_models, build_prompt_from_models
from apps.ml.services.usage_logger import log_llm_usage
from apps.data.models import PromptTemplate, GeneratedReview, ClinicGuide, Persona, ReviewSchedule

MODEL_ALIAS_MAP = {
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5.2": "gpt-5.2",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1": "gpt-4.1",
    "claude-4.5": "claude-sonnet-4-5-20250929",
    "claude-opus": "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
    # "ft:gpt-3.5-turbo-0125:personal::D2AzRPLe": "ft:gpt-3.5-turbo-0125:personal::D2AzRPLe", --- IGNORE ---
    # "ft:gpt-4.1-2025-04-14:personal::D3C9lMYD": "ft:gpt-4.1-2025-04-14:personal::D3C9lMYD", --- IGNORE ---
    # Legacy aliases -> current Gugong model
    "ft:gpt-4.1-2025-04-14:personal::D3J40yRV": "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    "ft:gpt-4.1-2025-04-14:personal:D3gDuLBk:": "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk": "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
}

AGENT_REVIEW_DRAFT_MODEL = "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk"
AGENT_USER_MEMORY = {}

def _resolve_request_user(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        return request.user
    session_key = request.headers.get("X-Sessionid")
    if not session_key:
        return None
    try:
        session = Session.objects.get(session_key=session_key, expire_date__gte=timezone.now())
    except Session.DoesNotExist:
        return None
    user_id = session.get_decoded().get("_auth_user_id")
    if not user_id:
        return None
    User = get_user_model()
    return User.objects.filter(id=user_id).first()


def _agent_display_name(user):
    if not user:
        return "담당자"
    name = str(getattr(user, "name", "") or "").strip()
    if name:
        return name
    first_name = str(getattr(user, "first_name", "") or "").strip()
    if first_name:
        return first_name
    return "담당자"


def _agent_context_summary(context):
    if not isinstance(context, dict):
        return "현재 화면"
    page = str(context.get("page") or context.get("nav") or "").strip()
    title = str(context.get("title") or "").strip()
    url = str(context.get("url") or "").strip()
    if not page:
        if title:
            return title
        if url:
            return url
        return "현재 화면"
    if title:
        return f"{page} ({title})"
    return page


def _agent_context_detail(context):
    if not isinstance(context, dict):
        return (
            "현재 화면 정보를 충분히 읽지 못했습니다.\n"
            "- 상단/좌측 메뉴 이름을 알려주시면 이 화면 기준으로 바로 순서 안내해드릴게요."
        )

    nav = str(context.get("page") or context.get("nav") or "").strip().lower()
    title = str(context.get("title") or "").strip().lower()
    url = str(context.get("url") or "").strip().lower()
    dom_hints = context.get("dom_hints") if isinstance(context.get("dom_hints"), dict) else {}
    url_key = url.rsplit("/", 1)[-1].replace(".html", "").split("?")[0].strip()
    joined = f"{nav} {title} {url} {url_key}"

    alias = {
        "review": "ai_review",
        "gugong": "gugong_review",
        "gangnam": "gangnam_review",
        "notifications": "notifications_center",
        "mail": "mail_center",
        "attendance": "attendance_admin",
        "attendance_requests": "attendance_requests",
        "clinic": "clinic_page",
        "clinic_page": "clinic_page",
        "signin": "login",
    }
    key_from_url = alias.get(url_key, url_key)
    key_from_nav = alias.get(nav, nav)
    # Prefer URL-derived key over nav to avoid stale nav state bleed.
    key = key_from_url or key_from_nav
    # Strongest signal: page-specific DOM anchors from renderer.
    if dom_hints.get("clinicGrid"):
        key = "dashboard"
    elif dom_hints.get("myReviewScheduleList"):
        key = "my_dashboard"
    elif dom_hints.get("clinicSelect"):
        key = "gugong_review"
    elif dom_hints.get("hospitalName"):
        key = "gangnam_review"
    elif dom_hints.get("keywordInput"):
        key = "ai_review"
    elif dom_hints.get("notifyMailList"):
        key = "mail_center"
    elif dom_hints.get("vacationAdminBody"):
        key = "vacation_admin"
    elif dom_hints.get("vacationForm"):
        key = "vacation"
    elif dom_hints.get("permTableBody"):
        key = "system_permissions"
    elif dom_hints.get("logsTableBody"):
        key = "system_logs"
    elif dom_hints.get("auditTableBody"):
        key = "audit_logs"
    # Strong override by title/url keywords to avoid wrong guide bleed.
    # NOTE: use precise checks first to avoid false-positive on gugong_review.html -> review.html substring.
    if url_key == "gugong_review" or any(k in joined for k in ["구공이", "gugong_review", "gugong"]):
        key = "gugong_review"
    elif url_key == "review" or any(k in joined for k in ["ai 리뷰 생성(persona)", "ai_review"]):
        key = "ai_review"
    elif url_key == "gangnam_review" or any(k in joined for k in ["강남언니", "gangnam_review", "gangnam"]):
        key = "gangnam_review"
    elif any(k in joined for k in ["my_dashboard", "나의 대시보드"]):
        key = "my_dashboard"

    guide_map = {
        "my_dashboard": (
            "나의 대시보드는 개인 업무/리뷰 설계를 한 번에 관리하는 메인 작업 화면입니다.",
            [
                "리뷰 설계 보드에서 설계안을 선택/생성하고 단계별 리뷰 결과를 확인해요.",
                "설계 일정 캘린더에서 날짜별 건수/설계안 제목/완료 상태를 점검해요.",
                "카드나 일정을 눌러 상세 모달에서 리뷰 결과를 수정하고 저장해요.",
                "업무 시작 전에는 미완료 토글(파란색 전환) 항목부터 우선 처리해요.",
            ],
        ),
        "dashboard": (
            "업체 대시보드는 업체(병원) 카드를 보고 바로 상세 페이지로 이동하는 허브 화면입니다.",
            [
                "카드 목록(`clinicGrid`)에서 원하는 병원을 찾아 클릭해요.",
                "자주 쓰는 병원은 카드 즐겨찾기(별)로 고정해 상단에서 빠르게 접근해요.",
                "병원 클릭 후 `clinic_page`에서 데일리 입력/게시글/캘린더 작업으로 내려가요.",
            ],
        ),
        "posts_dashboard": (
            "게시글 대시보드는 콘텐츠 성과와 수정 포인트를 보는 화면입니다.",
            [
                "게시글별 성과를 정렬해 상/하위 글을 분리해요.",
                "제목/본문/키워드 보정이 필요한 글을 골라요.",
                "수정 후 재확인해 개선 폭을 비교해요.",
            ],
        ),
        "calendar_dashboard": (
            "캘린더 대시보드는 일정/게시 계획/실행 현황을 관리하는 화면입니다.",
            [
                "월/주 기준으로 누락 일정부터 확인해요.",
                "각 일정의 상태(예정/완료/지연)를 점검해요.",
                "필요한 메모를 남기고 담당자 액션으로 연결해요.",
            ],
        ),
        "metrics_dashboard": (
            "지표 대시보드는 KPI 추세를 분석하는 화면입니다.",
            [
                "기간 비교(전주/전월)를 먼저 맞춰요.",
                "증감 큰 지표를 중심으로 원인 후보를 좁혀요.",
                "실행 계획을 정하고 추적 지표를 지정해요.",
            ],
        ),
        "ai_review": (
            "AI 리뷰 생성(Persona)은 자유 키워드 텍스트를 넣어 범용 리뷰를 생성하는 화면입니다.",
            [
                "키워드 입력창에 병원/시술/시점/톤을 자유 텍스트로 한 번에 입력해요.",
                "모델을 선택하고 리뷰 생성 버튼으로 초안을 만들어요.",
                "결과 모달에서 문장을 다듬고 수정 저장으로 반영해요.",
            ],
        ),
        "gugong_review": (
            "AI 리뷰 생성(구공이)은 칩/프리셋 기반으로 구공이 스타일을 정밀 제어하는 화면입니다.",
            [
                "병원, 글 목적, 연령대, MBTI를 먼저 선택해 기본 컨텍스트를 고정해요.",
                "톤 프리셋, 강조 키워드, 금지 표현, 페르소나 키워드를 입력해 스타일을 정해요.",
                "리뷰 생성 후 결과 모달에서 문장 톤/금지어 포함 여부를 확인하고 수정 저장해요.",
            ],
        ),
        "gangnam_review": (
            "강남언니 화면은 강남언니 포맷용 후기를 작성하는 곳입니다.",
            [
                "필수 필드(시술/기간/만족도/태그)를 먼저 채워요.",
                "JSON/출력 형식이 깨지지 않았는지 확인해요.",
                "금지 표현/광고 톤을 점검하고 저장해요.",
            ],
        ),
        "platform_review": (
            "플랫폼 리뷰 화면은 바비톡/토닥톡/여신티켓 채널별 문안을 만드는 곳입니다.",
            [
                "플랫폼 성격에 맞는 톤과 길이를 선택해요.",
                "플랫폼 정책에 맞지 않는 표현을 제거해요.",
                "채널별 버전으로 저장해 재사용해요.",
            ],
        ),
        "ai_review_guide": (
            "입력가이드는 리뷰 생성 입력값 기준을 안내하는 화면입니다.",
            [
                "예시 입력을 보고 필수 항목 형식을 맞춰요.",
                "자주 실패하는 입력 패턴을 먼저 피해서 작성해요.",
                "가이드 기준으로 실제 생성 화면 값에 반영해요.",
            ],
        ),
        "clinic_guide": (
            "병원 가이드는 병원별 핵심 정보와 작성 기준을 관리하는 화면입니다.",
            [
                "병원/시술 최신 정보를 먼저 갱신해요.",
                "금지/권장 표현을 병원별로 정리해요.",
                "리뷰 생성 전에 가이드 반영 상태를 확인해요.",
            ],
        ),
        "hospital_management": (
            "병원 참고사항은 운영 메모/주의사항을 관리하는 화면입니다.",
            [
                "내부 공유가 필요한 변경사항을 기록해요.",
                "중요 우선순위 메모를 상단에 배치해요.",
                "완료된 이슈는 상태를 정리해 누적을 줄여요.",
            ],
        ),
        "mail_center": (
            "메일 화면은 수신/발신 메시지를 처리하는 화면입니다.",
            [
                "미확인 메일부터 우선 확인해요.",
                "답변 필요 건을 분류해 빠르게 처리해요.",
                "처리 완료 메일은 정리해 인박스를 관리해요.",
            ],
        ),
        "attendance_requests": (
            "근태 정정요청 화면은 관리자/대표가 정정 요청을 검토하는 전용 화면입니다.",
            [
                "좌측 폴더/검색으로 요청을 좁히고, 대기 건부터 우선 확인해요.",
                "상세 패널에서 요청 사유/시간 정보를 읽고 읽음 처리 여부를 관리해요.",
                "필요 시 캘린더 열기로 실제 일정과 교차 확인한 뒤 승인/후속 조치해요.",
            ],
        ),
        "clinic_page": (
            "업무 페이지(클리닉 페이지)는 병원 단위 실무를 처리하는 올인원 화면입니다.",
            [
                "데일리 업무 일지에서 제목/URL/세부유형/플랫폼을 입력해 먼저 저장해요.",
                "플랫폼 ID·PW, 담당 원장, 첨부 사진까지 채워 기록 품질을 맞춰요.",
                "리뷰 작성 버튼으로 AI/강남언니/플랫폼 리뷰로 바로 연계해요.",
                "게시글 리스트에서 월/플랫폼/유형 필터로 조회 후 수정·저장·삭제를 처리해요.",
                "캘린더 섹션에서 일정 누락/충돌을 확인해 주간 작업 순서를 정리해요.",
            ],
        ),
        "notifications_center": (
            "메모함은 알림/메모를 확인하고 후속 액션으로 연결하는 화면입니다.",
            [
                "새 알림을 먼저 열어 핵심 내용을 확인해요.",
                "관련 페이지로 이동해 즉시 처리해요.",
                "완료 항목은 읽음/정리로 큐를 비워요.",
            ],
        ),
        "attendance_admin": (
            "출퇴근 관리는 근태 기록과 정정 요청을 처리하는 화면입니다.",
            [
                "이상 기록(누락/지각)을 먼저 확인해요.",
                "정정 요청 사유와 증빙을 검토해요.",
                "승인/반려 후 상태를 다시 점검해요.",
            ],
        ),
        "vacation": (
            "휴가 신청은 개인 휴가 신청과 잔여 현황을 확인하는 화면입니다.",
            [
                "잔여 일수를 확인하고 신청 기간을 잡아요.",
                "사유/일정을 정확히 입력해 제출해요.",
                "승인 상태를 확인하고 일정에 반영해요.",
            ],
        ),
        "vacation_admin": (
            "휴가 관리는 팀 휴가 신청을 승인/반려하는 화면입니다.",
            [
                "대기 건을 우선순위로 정렬해요.",
                "업무 공백 여부를 확인한 뒤 판단해요.",
                "승인/반려 사유를 남겨 히스토리를 관리해요.",
            ],
        ),
        "employee_management": (
            "직원 관리는 인사 기본정보와 계정 상태를 관리하는 화면입니다.",
            [
                "신규/퇴사자 상태를 최신화해요.",
                "권한/역할을 직무 기준으로 점검해요.",
                "변경 이력을 남겨 운영 리스크를 줄여요.",
            ],
        ),
        "system_monitor": (
            "서버 관리는 시스템 상태와 키 설정 점검 화면입니다.",
            [
                "핵심 상태(연결/키/헬스체크)를 먼저 봐요.",
                "오류 신호가 있으면 로그 화면으로 내려가요.",
                "조치 후 상태가 정상 복귀됐는지 재확인해요.",
            ],
        ),
        "system_logs": (
            "시스템 로그는 요청/오류 로그를 추적하는 화면입니다.",
            [
                "시간 범위와 키워드로 먼저 좁혀요.",
                "오류 패턴의 공통 원인을 찾어요.",
                "조치 후 동일 패턴 재발 여부를 확인해요.",
            ],
        ),
        "system_permissions": (
            "시스템 권한은 페이지 접근/권한 정책을 관리하는 화면입니다.",
            [
                "역할별 접근 범위를 먼저 점검해요.",
                "예외 권한은 최소 범위로 부여해요.",
                "변경 후 실제 계정으로 접근 테스트해요.",
            ],
        ),
        "audit_logs": (
            "감사 로그는 관리자/권한 변경 이력을 추적하는 화면입니다.",
            [
                "기간과 대상 사용자로 필터링해요.",
                "중요 변경(권한/설정) 이력을 우선 확인해요.",
                "의심 변경은 관련 로그와 교차 검증해요.",
            ],
        ),
        "login": (
            "로그인 화면은 계정 인증 후 시스템에 진입하는 시작 화면입니다.",
            [
                "아이디/비밀번호를 입력하고 로그인해요.",
                "로그인 실패 시 계정 상태/비밀번호를 먼저 점검해요.",
                "정상 로그인 후에는 헤더 우측 프로필에서 기본 정보를 확인해요.",
            ],
        ),
        "signup": (
            "회원가입 화면은 신규 사용자 계정을 생성하는 초기 등록 화면입니다.",
            [
                "필수 입력값(이름/아이디/비밀번호/권한 등)을 정확히 입력해요.",
                "중복/형식 검증 오류를 먼저 해소한 뒤 가입을 완료해요.",
                "가입 후 로그인해서 권한별 메뉴 노출을 확인해요.",
            ],
        ),
    }
    first_click_map = {
        "my_dashboard": "리뷰 설계 보드의 설계안 리스트를 먼저 클릭하세요.",
        "dashboard": "업체 카드 영역(`#clinicGrid`)에서 작업할 병원 카드를 먼저 클릭하세요.",
        "posts_dashboard": "월/유형 필터를 먼저 맞춘 뒤 목록을 보세요.",
        "calendar_dashboard": "캘린더에서 오늘 날짜 카드부터 클릭해 상세를 여세요.",
        "metrics_dashboard": "비교 기간(전주/전월)을 먼저 설정하세요.",
        "ai_review": "왼쪽 키워드 입력창부터 채우고 모델을 선택하세요.",
        "gugong_review": "병원 선택(`#clinicSelect`)과 글 목적(`#reviewIntent`)부터 먼저 고르세요.",
        "gangnam_review": "필수 입력 필드(시술/기간/만족도)부터 채우세요.",
        "platform_review": "플랫폼 선택 후 같은 내용으로 채널별 버전을 분리하세요.",
        "ai_review_guide": "가이드 페이지 상단의 필수 입력 예시부터 읽으세요.",
        "clinic_guide": "병원 선택 후 최신 가이드 항목부터 확인하세요.",
        "hospital_management": "병원 선택 후 참고사항 목록 첫 줄부터 최신 여부를 확인하세요.",
        "clinic_page": "데일리 업무 일지 섹션의 제목/URL 입력칸부터 채우세요.",
        "mail_center": "좌측 폴더에서 받은메일을 고르고 미확인 메일부터 클릭하세요.",
        "notifications_center": "최신 알림 1건을 먼저 열어 상세를 확인하세요.",
        "attendance_admin": "대기 상태 요청부터 필터링해 검토하세요.",
        "attendance_requests": "검색창으로 요청자를 좁힌 뒤 상세를 열어보세요.",
        "vacation": "잔여 일수 확인 후 신청 날짜를 먼저 선택하세요.",
        "vacation_admin": "대기 건 목록에서 가장 오래된 요청부터 처리하세요.",
        "employee_management": "직원 검색 후 권한/상태 컬럼을 먼저 점검하세요.",
        "system_monitor": "상태 카드(연결/헬스체크)부터 정상 여부를 확인하세요.",
        "system_logs": "시간 범위와 키워드 필터부터 설정하세요.",
        "system_permissions": "역할(ROLE) 선택 후 접근 권한 체크를 검토하세요.",
        "audit_logs": "기간 필터를 먼저 맞추고 사용자별 변경 이력을 보세요.",
        "login": "아이디 입력칸을 먼저 클릭하고 비밀번호를 순서대로 입력하세요.",
        "signup": "필수 입력칸(아이디/비밀번호/이름)을 위에서 아래로 순서대로 채우세요.",
    }
    pitfall_map = {
        "my_dashboard": "수정 저장 후 화면 반영이 늦으면 새로고침 후 다시 확인하세요.",
        "dashboard": "카드가 안 보이면 즐겨찾기/검색 상태와 데이터 로딩 상태를 먼저 확인하세요.",
        "posts_dashboard": "유형 필터(여론/후기)가 맞지 않으면 원하는 글이 안 보일 수 있어요.",
        "gugong_review": "병원/목적이 비어 있으면 결과 톤이 흔들릴 수 있어 필수 선택값부터 확인하세요.",
        "gangnam_review": "출력 형식(JSON/필수 필드) 누락 시 저장이 실패할 수 있어요.",
        "platform_review": "플랫폼별 금지 표현이 달라 동일 문구를 그대로 복붙하면 막힐 수 있어요.",
        "ai_review": "키워드 입력이 모호하면 결과가 퍼지니 병원/시술/시점을 명확히 적으세요.",
        "ai_review_guide": "예시 형식을 그대로 복사하면 실제 케이스와 충돌할 수 있어요.",
        "clinic_guide": "병원명이 유사하면 다른 병원 가이드를 수정할 수 있으니 선택을 확인하세요.",
        "hospital_management": "메모 저장 후 정렬 기준이 달라 위치가 바뀔 수 있어요.",
        "clinic_page": "URL/플랫폼 자동 분류가 오인식될 수 있어 저장 전 수동 확인이 필요해요.",
        "calendar_dashboard": "날짜 카드에 건수가 0이면 설계안 생성/날짜 지정부터 확인하세요.",
        "mail_center": "읽음 처리와 삭제를 헷갈리지 않도록 상세 확인 후 버튼을 누르세요.",
        "notifications_center": "알림 읽음 처리 후 목록이 즉시 재정렬되어 위치가 바뀔 수 있어요.",
        "attendance_admin": "정정 승인 전 원본 시간/사유를 함께 확인하세요.",
        "attendance_requests": "읽음 처리만으로 승인된 게 아니니 상태 버튼을 따로 확인하세요.",
        "vacation": "이미 지난 날짜를 신청하면 정책상 반려될 수 있어요.",
        "vacation_admin": "승인 후 되돌리기 어려우니 일정 충돌을 먼저 점검하세요.",
        "employee_management": "권한 변경 후 로그아웃/재로그인 전엔 화면 반영이 늦을 수 있어요.",
        "system_monitor": "일시적 네트워크 오류를 장애로 오판하지 않도록 재조회해보세요.",
        "system_logs": "로그 시간대(로컬/서버)가 다르면 시간 검색이 어긋날 수 있어요.",
        "system_permissions": "권한 변경 후 테스트 계정으로 실제 접근 확인을 꼭 하세요.",
        "audit_logs": "시간대 필터가 다르면 누락처럼 보일 수 있으니 기간부터 점검하세요.",
        "login": "Caps Lock/한글 입력 상태 때문에 비밀번호 오입력이 자주 발생해요.",
        "signup": "아이디 중복 확인 없이 진행하면 마지막 단계에서 실패할 수 있어요.",
    }
    ui_locator_map = {
        "my_dashboard": [
            "섹션 이동: `#mySectionNav`에서 리뷰 설계 보드/캘린더 탭을 선택",
            "설계안 생성 버튼: `#myReviewScheduleGenerate`",
            "설계안 생성 모달 입력: `#reviewSchedulePlanTitle`, `#reviewSchedulePersonaKeywords`, `#reviewSchedulePlanGroups`",
            "설계 일정 캘린더: `#myReviewScheduleCalendar`, 월 이동 `#reviewSchedulePrevBtn`/`#reviewScheduleNextBtn`",
        ],
        "dashboard": [
            "업체 카드 영역: `#clinicGrid`",
            "카드의 즐겨찾기(별) 버튼으로 자주 쓰는 병원을 고정",
            "카드 클릭 시 병원 업무 페이지(`clinic_page.html?clinic_id=...`)로 이동",
        ],
        "posts_dashboard": [
            "월/검색/유형 필터를 먼저 적용",
            "목록에서 수정 대상 게시글을 클릭해 상세 확인",
            "수정/저장 버튼으로 단계별 반영 확인",
        ],
        "calendar_dashboard": [
            "캘린더 본체: `#calendarBoard`",
            "월 이동: `#calendarMonthPrev`/`#calendarMonthNext`, 월 라벨 `#calendarMonthLabel`",
            "상세 패널: `#calendarDetailPanel`, 리스트 `#calendarDetailList`",
            "수정 모달 저장: `#calendarEditSave`",
        ],
        "metrics_dashboard": [
            "기간 비교 필터를 먼저 설정",
            "증감 카드/지표 그래프를 위에서 아래 순으로 확인",
            "이상치 발견 시 관련 페이지로 내려가 교차 확인",
        ],
        "ai_review": [
            "자유 텍스트 입력: `#keywordInput`",
            "모델 선택: `#modelList`",
            "리뷰 생성: `#generateReviewBtn`",
            "결과 확인/저장: `#reviewModal`, `#saveModalBtn`, `#modalReview`",
        ],
        "gugong_review": [
            "프리셋 선택: `#clinicSelect`, `#reviewIntent`, `#ageGroup`, `#mbtiGroup`",
            "톤/키워드: `#tonePreset`, `#keywordGroup`, `#forbiddenGroup`, `#personaInput`",
            "생성 버튼: `#generateReviewBtn`, 모델 영역: `#modelList`",
            "결과 모달: `#reviewModal`, 수정 저장: `#saveModalBtn`, 결과 본문: `#modalReview`",
        ],
        "gangnam_review": [
            "기본 입력: `#hospitalName`, `#procedureType`, `#doctorName`",
            "페르소나: `#personaAge`, `#personaGender`, `#personaTone`",
            "생성 버튼: `#generateBtn`, 결과 모달: `#reviewModal`",
            "결과 블록: `#result_before_worry`, `#result_result_review`",
        ],
        "platform_review": [
            "플랫폼 선택 후 입력값을 채널별로 분리 입력",
            "채널 정책(금지 표현/길이)을 먼저 확인",
            "생성 결과를 채널별로 따로 저장",
        ],
        "ai_review_guide": [
            "상단 가이드 섹션부터 순서대로 읽기",
            "필수 입력 예시를 복사해 실제 화면에 맞게 수정",
            "생성 전 금지/권장 표현 체크",
        ],
        "clinic_guide": [
            "병원 선택 후 가이드 항목(권장/금지)을 먼저 확인",
            "수정 시 병원명이 맞는지 재확인",
            "저장 후 해당 병원 리뷰 생성 결과로 반영 확인",
        ],
        "hospital_management": [
            "참고사항 목록에서 최신 메모를 먼저 확인",
            "중요 메모는 상단 배치 기준으로 정리",
            "완료 메모는 상태/내용 정리 후 보관",
        ],
        "clinic_page": [
            "데일리 입력: `#aiIntakeTitle`, `#aiIntakeUrl`, `#aiIntakeSubtype`, `#aiIntakePlatform`",
            "계정 입력: `#aiIntakeAccount`, `#aiIntakeAccountPassword`, 저장 `#aiIntakeSubmit`",
            "게시글 리스트: `#postSearch`, `#clinicPostEditBtn`, `#clinicPostSaveBtn`",
            "캘린더 보드: `#clinicCalendarBoard`, 상세 `#clinicCalendarList`",
        ],
        "mail_center": [
            "검색/정렬: `#notifySearchInput`, `#mailSortSelect`",
            "메일 작성: `#notifyComposeBtn` -> 모달 `#mailComposeModal`",
            "보내기 필수 입력: `#mailRecipientSelect`, `#mailSubjectInput`, `#mailContentInput`",
            "상세 확인: `#notifyDetailPane`, 본문 `#notifyDetailBody`",
        ],
        "notifications_center": [
            "알림 목록에서 최신 항목 먼저 클릭",
            "상세 패널에서 핵심 내용 확인 후 읽음 처리",
            "관련 화면 이동이 필요한 항목 우선 처리",
        ],
        "attendance_admin": [
            "대기 건 필터를 먼저 적용",
            "요청 사유/시간을 확인 후 승인/반려",
            "처리 후 목록 상태(대기 감소) 확인",
        ],
        "attendance_requests": [
            "검색/새로고침: `#notifySearchInput`, `#notifyRefreshBtn`",
            "요청 상세: `#notifyDetailPane`, `#notifyDetailBody`",
            "읽음 처리: `#notifyDetailMarkReadBtn`",
            "캘린더 교차확인: `#notifyDetailOpenCalendarBtn`",
        ],
        "vacation": [
            "신청 폼: `#vacationForm`",
            "기간 입력: `#vacationStart`, `#vacationEnd`, 사용일수 힌트 `#vacationDayHint`",
            "사유 입력: `#vacationReason`",
            "목록 확인: `#vacationListBody`",
        ],
        "vacation_admin": [
            "필터: `#vacationAdminYear`, `#vacationAdminSearch`, `#vacationAdminStatus`",
            "목록 본문: `#vacationAdminBody`",
            "대기 건부터 승인/반려 후 상태 재확인",
        ],
        "employee_management": [
            "직원 검색 후 대상 행 선택",
            "권한/상태를 변경한 뒤 저장",
            "변경 후 재조회로 반영 확인",
        ],
        "system_monitor": [
            "자동 갱신: `#monitorAutoBtn`",
            "요약 카드: `#monitorSummaryCards`",
            "상태 정보: `#monitorInfo`",
            "API 체크 목록: `#monitorApiChecks`",
        ],
        "system_logs": [
            "검색/필터: `#logsSearchInput`, `#logsMethodFilter`, `#logsRangePreset`",
            "기간 적용: `#logsFromDate`, `#logsToDate`, `#logsApplyRangeBtn`",
            "목록 확인: `#logsTableBody`, 페이지 `#logsPrevBtn`/`#logsNextBtn`",
            "상세 모달: `#logsDetailModal`, `#logsDetailBody`",
        ],
        "system_permissions": [
            "검색/새로고침: `#permSearchInput`, `#permRefreshBtn`",
            "권한 테이블: `#permTableBody`",
            "변경 후 테스트 계정으로 접근 검증",
        ],
        "audit_logs": [
            "검색/필터: `#auditSearchInput`, `#auditEventType`",
            "기간 적용: `#auditFromDate`, `#auditToDate`, `#auditApplyBtn`",
            "목록/페이지: `#auditTableBody`, `#auditPrevBtn`, `#auditNextBtn`",
            "상세 모달: `#auditDetailModal`, `#auditDetailBody`",
        ],
        "login": [
            "아이디/비밀번호 입력 후 로그인 버튼 클릭",
            "실패 시 입력 상태(한글/영문, Caps Lock) 먼저 확인",
            "성공 후 헤더 사용자명 표시 확인",
        ],
        "signup": [
            "필수 입력: `#name`, `#username`, `#password`, `#email`",
            "날짜 입력: `#birthDate`, `#hireDate`",
            "오류 메시지 확인: `#message`",
            "가입 완료 후 로그인 화면에서 재검증",
        ],
    }
    core_focus_map = {
        "my_dashboard": ["리뷰 설계 보드 관리", "설계 일정 캘린더 확인", "모달에서 결과 수정/저장"],
        "dashboard": ["업체 카드 탐색", "즐겨찾기 관리", "클리닉 상세 진입"],
        "posts_dashboard": ["게시글 목록 필터링", "수정 대상 선별", "수정/저장 반영 확인"],
        "calendar_dashboard": ["월간 작업 캘린더 조회", "날짜별 상세 확인", "일정 수정/저장"],
        "metrics_dashboard": ["KPI 증감 확인", "이상치 탐지", "후속 액션 지표 지정"],
        "ai_review": ["자유 텍스트(Persona) 입력", "모델 선택 후 즉시 생성", "결과 모달 편집/저장"],
        "gugong_review": ["칩/프리셋 기반 설정", "톤·금지어·키워드 정밀 제어", "구공이 스타일 결과 검수"],
        "gangnam_review": ["강남언니 포맷 입력", "페르소나/모델 설정", "결과 블록 검수"],
        "platform_review": ["플랫폼별 문안 분리", "채널 정책 반영", "채널별 저장"],
        "ai_review_guide": ["입력 기준 확인", "실패 패턴 회피", "실제 입력값 점검"],
        "clinic_guide": ["병원 가이드 조회", "권장/금지 표현 관리", "생성 전 가이드 점검"],
        "hospital_management": ["병원 메모 관리", "주의사항 정리", "완료 이슈 정돈"],
        "clinic_page": ["데일리 업무 입력", "게시글 리스트 관리", "클리닉 캘린더 운영"],
        "mail_center": ["메일 검색/정렬", "메일 작성/전송", "상세 본문 확인"],
        "notifications_center": ["알림 확인", "상세 열람", "후속 페이지 이동"],
        "attendance_admin": ["근태 요청 검토", "승인/반려 처리", "처리 상태 확인"],
        "attendance_requests": ["정정요청 검색", "상세 사유 확인", "읽음/캘린더 연동"],
        "vacation": ["휴가 신청", "사용 일수 계산", "신청 내역 확인"],
        "vacation_admin": ["휴가 요청 필터링", "승인/반려", "상태별 관리"],
        "employee_management": ["직원 정보 조회", "권한/상태 변경", "변경 반영 점검"],
        "system_monitor": ["서버 상태 점검", "API 체크 확인", "자동 갱신 관리"],
        "system_logs": ["로그 검색/필터", "이상 패턴 확인", "상세 로그 열람"],
        "system_permissions": ["권한 테이블 관리", "계정별 접근 설정", "권한 반영 검증"],
        "audit_logs": ["감사 이력 조회", "기간/이벤트 필터", "변경 상세 추적"],
        "login": ["계정 로그인", "인증 실패 점검", "진입 확인"],
        "signup": ["신규 계정 등록", "입력 검증", "가입 후 로그인 확인"],
    }
    common_beginner_lines = [
        "좌측 사이드바의 현재 메뉴 하이라이트를 먼저 확인하세요.",
        "상단 제목과 실제 화면이 일치하는지 확인하세요.",
    ]

    if key in guide_map:
        intro, steps = guide_map[key]
        core_focus = core_focus_map.get(key, [s for s in steps[:3]])
        core_focus_lines = [f"{idx + 1}. {line}" for idx, line in enumerate(core_focus[:3])]
        return f"{intro}\n이 페이지 핵심:\n" + "\n".join(core_focus_lines)

    # Fuzzy fallback for unknown nav keys.
    for k, (intro, steps) in guide_map.items():
        if k in joined:
            core_focus = core_focus_map.get(k, [s for s in steps[:3]])
            core_focus_lines = [f"{idx + 1}. {line}" for idx, line in enumerate(core_focus[:3])]
            return f"{intro}\n이 페이지 핵심:\n" + "\n".join(core_focus_lines)

    return (
        "이 화면의 상세 분류를 아직 자동 식별하지 못했습니다.\n"
        "- 이 화면에서 하려는 작업을 한 줄로 알려주시면 순서로 안내해드릴게요."
    )


def _agent_fetch_json(request, path):
    session_key = request.headers.get("X-Sessionid") or request.COOKIES.get("sessionid")
    if not session_key:
        return None
    base = f"{request.scheme}://{request.get_host()}"
    url = urljoin(base, path)
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Sessionid": session_key,
            "Cookie": f"sessionid={session_key}",
        },
    )
    try:
        with urlopen(req, timeout=3.5) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except Exception:
        return None


def _agent_vacation_summary(data):
    if not isinstance(data, dict):
        return "휴가 데이터를 불러오지 못했습니다."
    rows = data.get("results")
    if not isinstance(rows, list):
        return "휴가 데이터 형식을 확인할 수 없습니다."
    pending = 0
    approved = 0
    rejected = 0
    for row in rows:
        status = str((row or {}).get("status") or "").lower()
        if status == "pending":
            pending += 1
        elif status == "approved":
            approved += 1
        elif status == "rejected":
            rejected += 1
    return f"휴가 신청: 대기 {pending}건, 승인 {approved}건, 반려 {rejected}건"


def _contains_any(text, keywords):
    return any(k in text for k in keywords)


def _agent_is_page_help_query(text):
    raw = str(text or "").lower()
    nospace = re.sub(r"\s+", "", raw)
    page_terms = [
        "현재 페이지", "현재 화면", "지금 페이지", "지금 화면", "이 페이지", "이 화면", "여기",
        "현재페이지", "현재화면", "지금페이지", "지금화면", "이페이지", "이화면",
    ]
    ask_terms = [
        "뭐하는", "무슨", "설명", "용도", "기능", "역할", "사용법", "사용 방법", "어떻게 써",
        "어떻게써", "어떻게 사용", "어떻게사용", "무엇", "뭐야", "뭔데", "어디", "어떤",
    ]
    if any(t in raw for t in page_terms) or any(t in nospace for t in [p.replace(" ", "") for p in page_terms]):
        return True
    if any(t in raw for t in ask_terms) and any(t in raw for t in ["페이지", "화면", "여기", "곳"]):
        return True
    if any(t in nospace for t in ["현재페이지", "현재화면", "지금페이지", "지금화면", "이페이지", "이화면", "여기"]):
        return True
    # Regex catch-all for natural variants.
    if re.search(r"(현재|지금|이|여기).{0,6}(페이지|화면|곳)", raw):
        return True
    if re.search(r"(페이지|화면|곳).{0,8}(설명|용도|기능|역할|사용법|뭐|무엇|어떤|어디)", raw):
        return True
    if re.search(r"(현재|지금|이|여기).{0,6}(페이지|화면|곳).{0,10}(뭐|무엇|설명|용도|기능|역할|사용법)", raw):
        return True
    return False


def _agent_is_action_query(lower_message):
    """
    Chat-first routing:
    - Default: free-form LLM conversation (ChatGPT-like).
    - Deterministic flow only when user explicitly asks to open/move/check app data.
    """
    text = str(lower_message or "")
    text_nospace = re.sub(r"\s+", "", text)
    # Always treat page-context/help questions as deterministic action flow.
    if _agent_is_page_help_query(text):
        return True
    if _contains_any(text, ["사용방법", "사용 방법"]) and (_contains_any(text, ["페이지", "화면"]) or _contains_any(text_nospace, ["페이지", "화면"])):
        return True

    verb_open = _contains_any(text, ["이동", "열어", "보여줘", "확인해", "가줘", "가자", "열어줘", "열어 줘", "알려줘", "알려 줘"])
    noun_page = _contains_any(text, [
        "내 정보", "내정보", "내 계정", "내계정", "프로필",
        "리뷰 생성", "리뷰생성", "ai 리뷰", "ai리뷰", "후기 생성", "후기생성", "리뷰 작성", "리뷰작성",
        "구공이", "gugong", "강남", "gangnam",
        "현재 페이지", "현재 화면", "지금 페이지",
        "알림", "notifications", "메일", "mail", "메시지",
        "근태", "출퇴근", "출근", "퇴근",
        "휴가", "연차",
        "요약", "브리핑", "한눈",
    ])
    return bool(verb_open and noun_page)


def _agent_is_review_plan_request(lower_message):
    text = str(lower_message or "")
    if "설계안" in text or "스케줄 설계" in text:
        return True
    keys = [
        "여론", "고민", "발품", "손품", "상담후기", "상담 후기",
        "주차", "개월", "리뷰작성을", "리뷰 작성", "설계",
    ]
    score = sum(1 for k in keys if k in text)
    if score >= 3:
        return True

    # Short natural asks like "강남12의원 실리프팅 설계해줄래" should still trigger plan flow.
    has_design_intent = any(k in text for k in ["설계", "플랜", "계획"])
    has_review_intent = any(k in text for k in ["리뷰", "후기"])
    has_clinic_or_procedure_hint = (
        bool(re.search(r"[가-힣A-Za-z0-9]+의원", text))
        or bool(re.search(r"[가-힣A-Za-z0-9]+(리프팅|시술)", text))
    )
    if has_design_intent and (has_review_intent or has_clinic_or_procedure_hint):
        return True
    return False


def _agent_extract_clinic_procedure(message):
    text = str(message or "").strip()
    clinic = ""
    procedure = ""

    m = re.search(r"([가-힣A-Za-z0-9]+의원)", text)
    if m:
        clinic = m.group(1)

    p = re.search(r"([가-힣A-Za-z0-9]+)\s*시술", text)
    if p:
        procedure = p.group(1)
    if not procedure:
        p2 = re.search(r"(?:의원\s*)?([가-힣A-Za-z0-9]+(?:리프팅|필러|보톡스|제모|윤곽|코수술|눈수술))", text)
        if p2:
            procedure = p2.group(1)
    if not procedure:
        p3 = re.search(r"([가-힣A-Za-z0-9]+)\s*설계", text)
        if p3 and not p3.group(1).endswith("의원"):
            procedure = p3.group(1)

    return clinic, procedure


def _agent_build_review_plan_text(message):
    clinic, procedure = _agent_extract_clinic_procedure(message)
    clinic_label = clinic or "대상 병원"
    procedure_label = procedure or "대상 시술"
    lines = [
        f"{clinic_label} {procedure_label} 기준 리뷰 설계안이에요.",
        "1. 여론/고민: 시술 고민 포인트, 비교 기준, 기대 효과 중심 2건",
        "2. 발품/손품: 검색/커뮤니티 탐색 후기 톤으로 2건",
        "3. 상담후기: 상담 분위기, 안내 퀄리티, 결정 포인트 1건",
        "4. 1~3주차 후기: 1주차/2주차/3주차 경과 후기 각 1건",
        "5. 1~6개월차 후기: 1개월/2개월/3개월/6개월 경과 후기 각 1건",
        "원하면 지금 이 설계 순서대로 AI 리뷰생성(또는 구공이)에서 바로 리뷰 뽑게 이어서 진행할게요.",
    ]
    return "\n".join(lines)


def _agent_add_months(base_date, months):
    y = base_date.year + ((base_date.month - 1 + months) // 12)
    m = ((base_date.month - 1 + months) % 12) + 1
    d = min(base_date.day, 28)
    return base_date.replace(year=y, month=m, day=d)


def _agent_next_business_day(d):
    cur = d
    while cur.weekday() >= 5:
        cur = cur + timedelta(days=1)
    return cur


def _agent_build_review_plan_rows(message, *, start_date=None):
    clinic, procedure = _agent_extract_clinic_procedure(message)
    base = _agent_next_business_day(start_date or timezone.localdate())
    rows = []

    plan_defs = [
        ("여론/고민", base + timedelta(days=0), "시술 전 고민 포인트와 기대효과 중심"),
        ("발품/손품", base + timedelta(days=2), "검색/비교/커뮤니티 탐색 후기 톤"),
        ("상담후기", base + timedelta(days=5), "상담 경험/결정 포인트 중심"),
        ("1주차 후기", base + timedelta(days=7), "회복 초기 체감 및 주의사항"),
        ("2주차 후기", base + timedelta(days=14), "변화 추이 및 일상 적응"),
        ("3주차 후기", base + timedelta(days=21), "안정화 단계 체감"),
        ("1개월차 후기", _agent_add_months(base, 1), "중기 변화 및 만족도"),
        ("2개월차 후기", _agent_add_months(base, 2), "지속 효과/아쉬운 점 점검"),
        ("3개월차 후기", _agent_add_months(base, 3), "장기 안정화 관점"),
        ("4개월차 후기", _agent_add_months(base, 4), "중장기 유지력 점검"),
        ("5개월차 후기", _agent_add_months(base, 5), "생활 루틴 기준 변화 확인"),
        ("6개월차 후기", _agent_add_months(base, 6), "최종 체감 및 총평"),
    ]

    for label, target, detail in plan_defs:
        day = _agent_next_business_day(target)
        rows.append({
            "label": label,
            "date": day,
            "detail": detail,
        })
    return clinic, procedure, rows


def _agent_build_review_plan_rows_for_fields(*, clinic="", procedure="", start_date=None):
    base = _agent_next_business_day(start_date or timezone.localdate())
    rows = []

    plan_defs = [
        ("여론/고민", base + timedelta(days=0), "시술 전 고민 포인트와 기대효과 중심"),
        ("발품/손품", base + timedelta(days=2), "검색/비교/커뮤니티 탐색 후기 톤"),
        ("상담후기", base + timedelta(days=5), "상담 경험/결정 포인트 중심"),
        ("1주차 후기", base + timedelta(days=7), "회복 초기 체감 및 주의사항"),
        ("2주차 후기", base + timedelta(days=14), "변화 추이 및 일상 적응"),
        ("3주차 후기", base + timedelta(days=21), "안정화 단계 체감"),
        ("1개월차 후기", _agent_add_months(base, 1), "중기 변화 및 만족도"),
        ("2개월차 후기", _agent_add_months(base, 2), "지속 효과/아쉬운 점 점검"),
        ("3개월차 후기", _agent_add_months(base, 3), "장기 안정화 관점"),
        ("4개월차 후기", _agent_add_months(base, 4), "중장기 유지력 점검"),
        ("5개월차 후기", _agent_add_months(base, 5), "생활 루틴 기준 변화 확인"),
        ("6개월차 후기", _agent_add_months(base, 6), "최종 체감 및 총평"),
    ]

    for label, target, detail in plan_defs:
        day = _agent_next_business_day(target)
        rows.append({
            "label": label,
            "date": day,
            "detail": detail,
        })
    return clinic, procedure, rows


def _agent_stage_to_content_type(label):
    txt = str(label or "")
    # FT prompt 타입은 consultation/procedure/recovery_* 기준으로 동작하므로
    # 사전 탐색 단계(고민/손품/발품/여론)는 consultation 톤으로 매핑한다.
    if any(k in txt for k in ["여론", "고민", "발품", "손품", "검색", "비교", "커뮤니티", "관심"]):
        return "consultation"
    if "상담" in txt:
        return "consultation"
    if "1개월" in txt:
        return "recovery_1month"
    if "2개월" in txt:
        return "recovery_2month"
    if any(k in txt for k in ["3개월", "4개월", "5개월", "6개월"]):
        return "recovery_3month"
    if any(k in txt for k in ["1주차", "2주차", "3주차"]):
        return "procedure"
    return "procedure"


def _agent_generate_review_drafts_by_rows(*, clinic, procedure, rows, model=AGENT_REVIEW_DRAFT_MODEL):
    clinic_label = clinic or "대상 병원"
    procedure_label = procedure or "시술"
    clinic_obj = None
    if clinic:
        clinic_obj = ClinicGuide.objects.filter(name__icontains=clinic, is_active=True).first()

    drafts = {}
    for row in rows:
        label = str((row or {}).get("label") or "").strip()
        detail = str((row or {}).get("detail") or "").strip()
        if not label:
            continue
        content_type = _agent_stage_to_content_type(label)
        try:
            prompt = build_ft_prompt_from_models(
                clinic=clinic_obj,
                doctor_code=None,
                procedure=procedure_label,
                content_type=content_type,
                content_type_profile=None,
                persona=None,
                cafe=None,
                consultant_name=None,
                custom_instructions=None,
            )
            prompt = apply_review_type_guard(prompt)
            result = generate_review_with_prompt_enforced(
                prompt=prompt,
                model=model,
                max_tokens=1200,
                return_usage=False,
                keywords=[],
            )
            text = str(result or "").strip()
            if text:
                drafts[label] = text
                continue
        except Exception:
            pass
        drafts[label] = (
            f"{clinic_label} {procedure_label} 기준 {label} 리뷰입니다. "
            f"{detail}를 중심으로 실제 경험처럼 정리해 업로드하면 됩니다."
        )
    return drafts


def _agent_parse_keywords(raw_keywords):
    if isinstance(raw_keywords, str):
        return [k.strip() for k in raw_keywords.split(",") if k and k.strip()]
    if isinstance(raw_keywords, list):
        out = []
        for item in raw_keywords:
            txt = str(item or "").strip()
            if txt:
                out.append(txt)
        return out
    return []


def _agent_default_keywords():
    return ["통증", "붓기", "회복", "비용", "효과", "유지력"]


def _agent_parse_plan_groups(raw_groups):
    if isinstance(raw_groups, str):
        return [g.strip().lower() for g in raw_groups.split(",") if g and g.strip()]
    if isinstance(raw_groups, list):
        out = []
        for g in raw_groups:
            txt = str(g or "").strip().lower()
            if txt:
                out.append(txt)
        return out
    return []


def _agent_row_matches_group(label, group_key):
    txt = str(label or "")
    key = str(group_key or "").strip().lower()
    if key == "concern":
        return "여론/고민" in txt
    if key == "research":
        return "발품/손품" in txt
    if key == "consult":
        return "상담후기" in txt
    if key == "week1":
        return "1주차" in txt
    if key == "week2":
        return "2주차" in txt
    if key == "week3":
        return "3주차" in txt
    if key == "month1":
        return "1개월차" in txt
    if key == "month2":
        return "2개월차" in txt
    if key == "month3":
        return "3개월차" in txt
    if key == "month4":
        return "4개월차" in txt
    if key == "month5":
        return "5개월차" in txt
    if key == "month6":
        return "6개월차" in txt
    return False


def _agent_filter_rows_by_groups(rows, groups):
    group_keys = _agent_parse_plan_groups(groups)
    if not group_keys:
        return rows
    out = []
    for row in rows:
        label = str((row or {}).get("label") or "")
        if any(_agent_row_matches_group(label, g) for g in group_keys):
            out.append(row)
    return out


def _agent_generate_review_plan_from_form(
    *,
    user,
    plan_title="",
    clinic_name="",
    procedure_name="",
    keywords=None,
    tone="",
    platform_account="",
    platform_password="",
    count=None,
    plan_groups=None,
    model=AGENT_REVIEW_DRAFT_MODEL,
):
    plan_title = str(plan_title or "").strip()
    clinic_name = str(clinic_name or "").strip()
    procedure_name = str(procedure_name or "").strip()
    if not plan_title:
        raise ValueError("plan_title required")

    parsed_keywords = _agent_parse_keywords(keywords)
    if not parsed_keywords:
        parsed_keywords = _agent_default_keywords()
    tone_text = str(tone or "").strip()

    _, _, rows = _agent_build_review_plan_rows_for_fields(
        clinic=clinic_name,
        procedure=procedure_name,
    )

    rows = _agent_filter_rows_by_groups(rows, plan_groups)

    if count is not None:
        try:
            cnt = int(count)
            if cnt > 0:
                rows = rows[: min(cnt, len(rows))]
        except Exception:
            pass

    if not rows:
        raise ValueError("at least one plan group required")

    drafts_by_label = {}
    clinic_obj = ClinicGuide.objects.filter(name__icontains=clinic_name, is_active=True).first()
    for row in rows:
        label = str((row or {}).get("label") or "").strip()
        detail = str((row or {}).get("detail") or "").strip()
        if not label:
            continue
        content_type = _agent_stage_to_content_type(label)
        try:
            prompt = build_ft_prompt_from_models(
                clinic=clinic_obj,
                doctor_code=None,
                procedure=procedure_name,
                content_type=content_type,
                content_type_profile=None,
                persona=None,
                cafe=None,
                consultant_name=None,
                custom_instructions=(tone_text or None),
            )
            prompt = apply_review_type_guard(prompt)
            result = generate_review_with_prompt_enforced(
                prompt=prompt,
                model=model,
                max_tokens=1200,
                return_usage=False,
                keywords=parsed_keywords,
            )
            text = str(result or "").strip()
            if text:
                drafts_by_label[label] = text
                continue
        except Exception:
            pass
        drafts_by_label[label] = (
            f"{clinic_name} {procedure_name} 기준 {label} 리뷰입니다. "
            f"{detail} 중심으로 실제 경험처럼 정리했습니다."
        )

    plan_id = uuid.uuid4().hex[:10]
    _agent_save_review_schedules(
        user,
        plan_title=plan_title,
        clinic_name=clinic_name,
        platform_account=platform_account,
        platform_password=platform_password,
        rows=rows,
        drafts_by_label=drafts_by_label,
        plan_id=plan_id,
    )
    return rows, drafts_by_label, plan_id, parsed_keywords


def _agent_save_review_schedules(
    user,
    *,
    plan_title="",
    clinic_name="",
    platform_account="",
    platform_password="",
    rows=None,
    drafts_by_label=None,
    plan_id=None,
):
    clinic = None
    if clinic_name:
        clinic = ClinicGuide.objects.filter(name__icontains=clinic_name, is_active=True).first()

    saved = []
    rows = rows or []
    plan_title_txt = str(plan_title or "").strip()
    pid = str(plan_id or "")[:40] or uuid.uuid4().hex[:10]
    for r in rows:
        day = r["date"]
        remind_at = timezone.make_aware(datetime.combine(day, time(hour=10, minute=0)))
        draft = (drafts_by_label or {}).get(r["label"], "").strip()
        memo = ReviewSchedule.objects.create(
            user=user,
            clinic=clinic,
            date=day,
            plan_id=pid,
            plan_title=plan_title_txt,
            label=str(r.get("label") or "").strip(),
            detail=str(r.get("detail") or "").strip(),
            draft=draft,
            account=str(platform_account or "").strip(),
            account_password=str(platform_password or "").strip(),
            remind_at=remind_at,
            is_read=False,
        )
        saved.append(memo)
    return saved


def _agent_emotion_hint(lower_message):
    if _contains_any(lower_message, ["고마워", "감사", "좋아", "최고", "굿", "잘했"]):
        return "사용자가 긍정적입니다. 밝고 짧게 화답하세요."
    if _contains_any(lower_message, ["불안", "걱정", "힘들", "어려워", "막막"]):
        return "사용자가 불안/걱정 상태입니다. 안정감을 주는 문장으로 시작하세요."
    if _contains_any(lower_message, ["짜증", "화나", "열받", "빡쳐", "시발", "fuck"]):
        return "사용자가 강한 불편/분노를 표현했습니다. 방어적 태도 없이 진정시키고 해결책을 제시하세요."
    return "사용자 감정은 중립입니다. 친근하고 차분한 톤을 유지하세요."


def _agent_tone_rule(agent_style):
    style = str(agent_style or "friendly").strip().lower()
    rules = {
        "calm": "차분하고 안정적인 존댓말만 사용하세요. 감탄/과장/농담을 줄이고, 단정하고 담백한 어조를 유지하세요.",
        "friendly": "친근하고 자연스러운 한국어 회화체로 답하세요. 사무적인 문장(예: ~습니다체)보다 부드러운 ~요체를 기본으로 하되, 과한 감탄/이모지는 피하세요.",
        "friend": "베스트프렌드처럼 반말로 답하세요. 가끔 장난/툭툭거림은 허용하지만 공격적 표현은 금지. 친구 말투와 존댓말을 섞지 마세요.",
        "coach": "코치처럼 핵심 먼저 말하고, 짧은 실행 단계(1,2,3)로 안내하세요. 결론을 분명하게 말하세요.",
        "cute": "애교 듬뿍 귀여운 말투로 답하세요. 부드러운 존댓말(~요/~해요) + 귀여운 추임새/이모지로 통일하고, 딱딱한 문체를 섞지 마세요.",
    }
    return rules.get(style, rules["friendly"])


def _agent_length_rule(response_length):
    length = str(response_length or "balanced").strip().lower()
    rules = {
        "short": "2~3문장으로 짧게 답하세요.",
        "balanced": "2~4문장으로 핵심만 간결하게 답하세요.",
        "long": "필요 시 7문장 이상으로 충분히 설명하되, 항목/순서를 분명히 답하세요.",
    }
    return rules.get(length, rules["balanced"])


def _agent_response_profile_rule(response_profile):
    profile = str(response_profile or "balanced").strip().lower()
    rules = {
        "quick": "사용자가 빠른형입니다. 결론 먼저, 불필요한 부연 없이 짧고 명확하게 답하세요.",
        "balanced": "사용자 성향은 균형형입니다. 핵심과 근거를 짧게 함께 답하세요.",
        "detailed": "사용자가 상세형입니다. 이유/근거/선택지를 구조적으로 충분히 설명하세요.",
    }
    return rules.get(profile, rules["balanced"])


def _agent_adaptive_length_rule(lower_message, response_length, agent_style="friendly", response_profile="balanced"):
    mode = str(response_length or "balanced").strip().lower()
    style = str(agent_style or "friendly").strip().lower()
    profile = str(response_profile or "balanced").strip().lower()
    if style == "friend":
        return (
            "친구 모드에서는 기본 1~2문장으로 아주 짧게 답하세요. "
            "짧은 단답(한 단어/한 줄)도 자연스럽게 쓰세요. "
            "사용자가 길게 설명해달라고 명시하지 않으면 선택지 나열/과한 부연을 하지 마세요."
        )
    if mode == "balanced":
        if profile == "quick":
            return "빠른형 사용자이므로 1~3문장으로 결론 먼저 답하고, 필요한 근거만 1줄 덧붙이세요."
        if profile == "detailed":
            return "상세형 사용자이므로 4~6문장으로 이유와 대안을 구조적으로 답하세요."
    if mode in {"short", "long"}:
        return _agent_length_rule(mode)

    short_chat_keys = [
        "끝말", "끝말잇기", "잡담", "수다", "게임",
        "응", "ㅇㅇ", "오케이", "ok", "ㅋㅋ", "ㅎㅎ",
    ]
    needs_detail_keys = [
        "설명", "정리", "비교", "분석", "왜", "이유", "방법", "어떻게", "순서", "가이드",
    ]

    if any(k in lower_message for k in short_chat_keys) or len(lower_message.strip()) <= 12:
        return (
            "짧은 대화/게임 문맥에서는 1~2문장으로 답하거나, 필요한 경우 단어/한 줄만 답하세요. "
            "매 턴마다 불필요한 부연/추가질문(예: 계속할까요?)을 반복하지 마세요."
        )
    if any(k in lower_message for k in needs_detail_keys):
        return "설명/가이드 요청이면 4~6문장으로 핵심 단계 중심으로 답하세요."
    return "일반 대화는 2~4문장으로 간결하게 답하고, 꼭 필요할 때만 길게 확장하세요."


def _agent_focus_rule(lower_message):
    casual_keys = [
        "뭐하냐", "뭐해", "정체", "누구", "무슨사이", "친구", "왜그래", "왜 이래",
        "하이", "하이룽", "안녕", "헬로", "hello", "hi", "반가", "ㅋㅋ", "ㅎㅎ",
    ]
    if any(k in lower_message for k in casual_keys):
        return (
            "현재 질문은 가벼운 대화/관계 질문입니다. "
            "업무 기능 소개나 페이지 설명으로 바로 유도하지 말고, 질문 자체에 자연스럽게 짧게 답하세요. "
            "사용자가 먼저 업무를 요청하기 전에는 리뷰 작성/페이지 이동을 제안하지 마세요."
        )
    return "질문 의도와 직접 관련된 정보만 답하고, 불필요한 기능 유도 문구를 줄이세요."


def _agent_is_banter(lower_message):
    text = str(lower_message or "")
    keys = [
        "농담", "장난", "드립", "밈", "티키타카",
        "모르는거 같은데", "모르는 것 같은데", "모르네", "모르지", "헷갈리네",
        "어려운가", "어렵냐", "쉽지 않지", "실력", "레벨",
        "못받아드리", "못받아치", "못하네", "못하냐", "못하네?", "별론데",
        "놀리", "긁", "약올", "킹받", "긁혔", "발끈",
        "허세", "쫄", "쫄았", "겁먹", "쎈척", "센척", "쫄보",
        "아냐?", "아니냐?", "맞냐?", "아니지?", "진짜?", "ㅋㅋ", "ㅎㅎ", "lol",
    ]
    patterns = [
        r"너\s*모르",
        r"너\s*못",
        r"너\s*왜\s*그래",
        r"너\s*뭐\s*하",
        r"시러",
        r"싫어",
        r"안\s*알려",
        r"안알려",
        r"비밀",
        r"해보라",
        r"해봐",
        r"해볼래",
        r"맞혀봐",
        r"맞춰봐",
        r"받아쳐",
    ]
    if any(k in text for k in keys):
        return True
    return any(re.search(p, text) for p in patterns)


def _agent_proactive_rule(is_explicit_command):
    if is_explicit_command:
        return "사용자가 명령형으로 요청했을 때만 실행/이동/기능 안내를 수행하세요."
    return (
        "사용자가 명령형으로 요청하지 않은 일반 대화에서는 기능 실행 제안을 기본적으로 생략하세요. "
        "정말 필요한 경우에만 짧게 1회 제안하고, 페이지 이동/실행은 사용자가 동의하거나 명시 요청한 경우에만 수행하세요."
    )


def _agent_get_user_memory(user):
    uid = str(getattr(user, "id", "") or "")
    if not uid:
        return {"style": "friendly", "response_length": "balanced", "response_profile": "balanced"}
    return AGENT_USER_MEMORY.get(uid, {"style": "friendly", "response_length": "balanced", "response_profile": "balanced"})


def _agent_set_user_memory(user, mem):
    uid = str(getattr(user, "id", "") or "")
    if not uid:
        return
    AGENT_USER_MEMORY[uid] = {
        "style": str(mem.get("style") or "friendly"),
        "response_length": str(mem.get("response_length") or "balanced"),
        "response_profile": str(mem.get("response_profile") or "balanced"),
    }


def _agent_update_user_memory(user, lower_message):
    mem = _agent_get_user_memory(user)
    text = str(lower_message or "")

    if any(k in text for k in ["귀엽게", "애교", "냥체", "cute"]):
        mem["style"] = "cute"
    elif any(k in text for k in ["반말", "친구처럼", "편하게 말해"]):
        mem["style"] = "friend"
    elif any(k in text for k in ["차분하게", "냉정하게"]):
        mem["style"] = "calm"
    elif any(k in text for k in ["핵심만", "코치처럼", "실행 중심"]):
        mem["style"] = "coach"
    elif any(k in text for k in ["기본 말투", "원래 말투", "친절하게"]):
        mem["style"] = "friendly"

    if any(k in text for k in ["짧게", "짧은 답", "한줄", "한 줄"]):
        mem["response_length"] = "short"
    elif any(k in text for k in ["길게", "자세히", "상세히", "충분히"]):
        mem["response_length"] = "long"
    elif any(k in text for k in ["보통 길이", "적당히"]):
        mem["response_length"] = "balanced"

    if any(k in text for k in ["핵심만", "짧게", "한줄", "한 줄", "빠르게", "결론만"]):
        mem["response_profile"] = "quick"
    elif any(k in text for k in ["자세히", "상세히", "근거", "이유까지", "비교해서", "깊게"]):
        mem["response_profile"] = "detailed"
    elif any(k in text for k in ["기본으로", "보통으로", "적당히"]):
        mem["response_profile"] = "balanced"
    elif len(text) >= 90 and any(k in text for k in ["왜", "어떻게", "설명", "정리", "비교", "분석"]):
        mem["response_profile"] = "detailed"

    _agent_set_user_memory(user, mem)
    return mem


def _agent_dedupe_openers(answer, history):
    text = str(answer or "").strip()
    if not text:
        return text
    if not isinstance(history, list) or not history:
        return text
    recent = [str((h or {}).get("content") or "").strip() for h in history[-5:]]
    first_line = text.split("\n", 1)[0].strip()
    if first_line and any(r.startswith(first_line) for r in recent if r):
        body = text.split("\n", 1)[1].strip() if "\n" in text else text
        if body == text:
            return f"핵심만 바로 말씀드리면, {text}"
        return f"바로 요점부터 말씀드릴게요.\n{body}"
    return text


def _agent_failure_response(*, agent_style, lower, next_step="질문을 조금 짧게 다시 보내주세요."):
    msg = (
        "응답 엔진이 잠시 불안정합니다.\n"
        "원인: 일시적 모델 응답 오류\n"
        f"다음 행동: {next_step}"
    )
    return _agent_style_reply(msg, agent_style, lower)


def _agent_auto_style(lower_message, *, is_explicit_command=False, is_banter=False):
    """
    Single default tone with autonomous micro-switching.
    Base is friendly; switch only when user intent strongly implies it.
    """
    text = str(lower_message or "")
    # Explicit cute trigger (on-demand)
    if any(k in text for k in ["귀엽게", "애교", "냥체", "냥이처럼", "귀여운 말투", "cute"]):
        return "cute"
    # Explicit friend/casual trigger
    if any(k in text for k in ["반말로", "편하게 말해", "친구처럼", "friend 모드"]):
        return "friend"
    # User asks structured execution
    if any(k in text for k in ["핵심만", "요약", "정리해", "단계", "순서", "체크리스트", "실행해", "진행해"]):
        return "coach"
    # User asks calm / worried state
    if any(k in text for k in ["차분", "불안", "걱정", "긴장", "냉정하게"]):
        return "calm"
    # Banter can be slightly casual
    if is_banter and not is_explicit_command:
        return "friend"
    return "friendly"


def _agent_autonomous_assist(lower_message, context_summary="", is_explicit_command=False):
    """
    Jarvis-like lightweight autonomy:
    - Suggest one practical next step in conversational mode.
    - Attach direct navigation action only when command intent is explicit.
    """
    text = str(lower_message or "")
    ctx = str(context_summary or "")
    suggestions = []
    actions = []

    def _suggest(msg):
        if msg and msg not in suggestions:
            suggestions.append(msg)

    def _nav(page):
        if page and not any(a.get("type") == "navigate" and a.get("page") == page for a in actions):
            actions.append({"type": "navigate", "page": page})

    if any(k in text for k in ["설계안", "리뷰설계", "캘린더"]):
        _suggest("리뷰 설계 보드로 바로 열어 진행해볼까요?")
        if is_explicit_command:
            _nav("my_dashboard")
    elif any(k in text for k in ["구공이", "리뷰 생성", "후기 생성"]):
        _suggest("구공이 리뷰 생성 화면으로 바로 이동해 시작할 수 있어요.")
        if is_explicit_command:
            _nav("gugong_review")
    elif any(k in text for k in ["메일", "쪽지"]):
        _suggest("메일센터 열어서 미확인 항목부터 정리해볼까요?")
        if is_explicit_command:
            _nav("mail_center")
    elif any(k in text for k in ["알림", "공지"]):
        _suggest("알림센터에서 최신 알림부터 확인하면 빠릅니다.")
        if is_explicit_command:
            _nav("notifications_center")
    elif any(k in text for k in ["출근", "퇴근", "근태"]):
        _suggest("출퇴근 화면에서 오늘 기록 먼저 확인해볼까요?")
        if is_explicit_command:
            _nav("attendance_requests")
    elif any(k in text for k in ["휴가", "연차"]):
        _suggest("휴가 신청 화면에서 남은 일정 기준으로 바로 신청할 수 있어요.")
        if is_explicit_command:
            _nav("vacation")
    else:
        if "my_dashboard" in ctx or "나의 대시보드" in ctx:
            _suggest("지금 화면 기준으로 바로 할 수 있는 작업 1개를 정해 진행할게요.")
        else:
            _suggest("원하면 지금 요청 기준으로 다음 작업 1단계를 바로 이어서 진행할게요.")

    return suggestions[:2], actions[:1]


def _agent_style_reply(text, agent_style, user_lower_message="", response_profile="balanced"):
    """Apply lightweight style shaping for deterministic/non-LLM replies."""
    raw = str(text or "").strip()
    if not raw:
        return raw
    # Remove repetitive canned openers that feel unnatural in ongoing chat.
    raw = re.sub(r"^\s*(어머\s*)?심심하셨구나[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*궁금했구나[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*기억하시려는군요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*사용\s*방법\s*궁금하셨네요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*알고\s*싶으셨군요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*궁금하셨겠어요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*궁금하셨네요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*원하셨군요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\s*도움\s*필요하셨네요[~!,. ]*", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"알려줘서\s*고마워요[.!]?\s*", "", raw, flags=re.IGNORECASE).strip()
    # Remove stiff "-군요" style endings for a more natural assistant tone.
    raw = raw.replace("셨군요.", "셨네요.")
    raw = raw.replace("시는군요.", "시네요.")
    raw = raw.replace("군요.", "네요.")
    raw = raw.replace("군요?", "나요?")
    raw = raw.replace("군요!", "네요!")
    if not raw:
        raw = "알겠어."
    style = str(agent_style or "friendly").strip().lower()
    if style == "friendly":
        lower = str(user_lower_message or "").lower().strip()
        profile = str(response_profile or "balanced").strip().lower()
        is_action = _agent_is_action_query(lower)
        is_banter = _agent_is_banter(lower)
        asks_detail = any(k in lower for k in ["설명", "정리", "비교", "분석", "가이드", "방법", "어떻게", "순서", "체크"])
        very_short = len(lower) <= 12

        body = raw
        # Base softening: avoid overly rigid office-style endings.
        body = (
            body.replace("습니다.", "어요.")
            .replace("합니다.", "해요.")
            .replace("드립니다.", "드려요.")
            .replace("가능합니다.", "가능해요.")
            .replace("불가능합니다.", "어려워요.")
            .replace("원하시면", "원하면")
            .replace("추천드려요", "추천해요")
        )

        # Conversational mode: make it feel more human and less template-like.
        if (not is_action) and (is_banter or very_short or not asks_detail):
            body = body.replace("다음 행동:", "다음으로는")
            if not body.startswith(("좋아요", "괜찮아요", "맞아요", "오케이", "알겠어요")) and random.random() < 0.28:
                body = f"{random.choice(['맞아요. ', '좋아요. ', '오케이. '])}{body}"
            # Very subtle cute flavor for cat-assistant vibe.
            # Apply only sometimes and only on short conversational replies.
            if (
                random.random() < 0.20
                and len(body) <= 140
                and "다음으로는" not in body
                and "이유:" not in body
                and "용" not in body
            ):
                body = re.sub(r"요([.!?])", r"용\1", body, count=1)

        # Task mode: keep concise and direct without playful fillers.
        if is_action and any(x in body for x in ["ㅎㅎ", "ㅋㅋ", "헤헷", "오키, "]):
            body = body.replace("ㅎㅎ", "").replace("ㅋㅋ", "")
            body = body.replace("헤헷, ", "").replace("오키, ", "")

        # Casual short-turn mode: avoid long, assistant-like paragraphs.
        if (not is_action) and very_short:
            body = re.sub(
                r"\n?\s*(원하면|필요하면)\s*[^.\n!?]*(추천|이동|열어|도와)[^.\n!?]*[.!?]?\s*$",
                "",
                body,
                flags=re.IGNORECASE,
            ).strip()
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
            if len(sentences) > 2:
                body = " ".join(sentences[:2]).strip()

        if profile == "quick":
            lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
            if len(lines) > 3:
                body = "\n".join(lines[:3])
        elif profile == "detailed" and is_action and asks_detail and "\n" not in body:
            body = f"{body}\n이유: 요청 의도를 기준으로 가장 바로 실행 가능한 방법을 우선 제안했어요."

        return body
    if style == "friend":
        body = (
            raw.replace("입니다.", "이야.")
            .replace("있습니다.", "있어.")
            .replace("됩니다.", "돼.")
            .replace("드립니다.", "줄게.")
            .replace("하세요.", "해.")
            .replace("할게요.", "할게.")
            .replace("해드릴게요.", "해줄게.")
            .replace("도와드릴게요.", "도와줄게.")
            .replace("도와드릴 수 있어요.", "도와줄 수 있어.")
            .replace("원하시면", "원하면")
        )
        # Keep meaning stable for short casual prompts (e.g., "뭐해").
        lower = str(user_lower_message or "").lower().strip()
        very_short_casual = lower in {"뭐해", "뭐하냐", "뭐하냐?", "뭐해?"}
        if very_short_casual and body.startswith(("괜찮아?", "오케이,", "아 귀찮은데", "투덜투덜", "하,")):
            body = body.split(" ", 1)[-1] if " " in body else body.replace("괜찮아?", "").strip()

        # Add playful grumble only sometimes (not on every turn).
        playful_prefixes = [
            "아 귀찮은데... 알겠어. ",
            "투덜투덜... 해줄게. ",
            "오케이, 이번만 해준다? ",
            "하, 또 나 시키네. 알겠어. ",
        ]
        # Grumble only for explicit command-like asks (not casual conversation).
        is_command_like = any(
            k in lower for k in ["해줘", "해 줘", "해봐", "열어", "이동", "보여줘", "정리해", "만들어", "작성해"]
        )
        if body and is_command_like and not very_short_casual and random.random() < 0.22 and not body.startswith(tuple(playful_prefixes)):
            body = random.choice(playful_prefixes) + body
        return body
    if style == "cute":
        body = (
            raw.replace("입니다.", "이에요.")
            .replace("있습니다.", "있어요.")
            .replace("됩니다.", "돼요.")
            .replace("드립니다.", "드려요.")
            .replace("안녕하세요.", "안녕이에요.")
        )

        # Prefer cute sentence endings over heavy emoji/tildes.
        cute_suffixes = ["용", "욤", "영", "염", "여"]
        lines = body.split("\n")
        converted = 0
        for idx, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue
            # Convert only some sentence endings for naturalness.
            if re.search(r"[가-힣]+요([.!?])?$", s) and converted < 3 and random.random() < 0.75:
                punct_match = re.search(r"([.!?])$", s)
                punct = punct_match.group(1) if punct_match else "."
                s = re.sub(r"요([.!?])?$", f"{random.choice(cute_suffixes)}{punct}", s)
                converted += 1
            lines[idx] = s
        body = "\n".join(lines)

        # Ensure at least one cute ending appears.
        if converted == 0:
            body = re.sub(r"요([.!?])", r"용\1", body, count=1)

        # Light playful flavor only sometimes.
        if random.random() < 0.25:
            body = f"{random.choice(['헤헷, ', '앗, ', '오키, '])}{body}"
        return body
    if style == "coach":
        body = raw
        if "\n" in body and not any(x in body for x in ["1.", "2.", "- "]):
            lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
            body = "\n".join([f"{idx + 1}. {ln}" for idx, ln in enumerate(lines[:3])]) + ("\n" + "\n".join(lines[3:]) if len(lines) > 3 else "")
        if not body.startswith("좋아요."):
            body = f"좋아요. 핵심만 짚어줄게요.\n{body}"
        return body
    if style == "calm":
        body = (
            raw.replace("바로", "차분히")
            .replace("!", ".")
            .replace("!!", ".")
            .replace("?!", "?")
        )
        return body
    return raw


def _agent_apply_banter_clapback(text, *, is_banter=False, agent_style="friendly"):
    body = str(text or "").strip()
    if not body or not is_banter:
        return body
    # Keep it occasional and light.
    if random.random() >= 0.35:
        return body
    style = str(agent_style or "friendly").strip().lower()
    if style in {"calm", "coach"}:
        return body
    if style == "cute":
        prefix = random.choice(["엥~ 장난치넹? ", "아이궁~ 또 놀리네용? ", "힝~ 또 그러넹? "])
    else:
        prefix = random.choice(["오, 도발 들어오네? ", "오케이, 한마디 받았다. ", "야, 그건 좀 긁힌다? "])
    if body.startswith(prefix):
        return body
    return prefix + body


def _agent_apply_refusal_banter_guard(text, *, user_lower_message="", agent_style="friendly"):
    """
    If user playfully refuses to tell (e.g., '안 알려줄거야'),
    avoid bland acceptance or random guessing.
    """
    body = str(text or "").strip()
    if not body:
        return body
    lower = str(user_lower_message or "").lower()
    refusal = any(k in lower for k in ["안알려", "안 알려", "비밀", "시러", "싫어", "안줄래", "안 줄래"])
    if not refusal:
        return body

    # Avoid auto-guessing lines that break tiktok-like banter flow.
    if "정답" in body and any(k in body for k in ["골라볼게", "맞춰볼게", "추측", "일단"]):
        if str(agent_style or "").lower() == "cute":
            return "힝, 안 알려주면 못 맞히지용 >< 그럼 힌트 한 글자만 줘봐용!"
        if str(agent_style or "").lower() == "friend":
            return "야 너무하네 ㅋㅋ 안 알려주면 못 맞추지. 힌트 한 글자만 줘."
        return "안 알려주시면 바로 맞히긴 어려워요. 힌트 한 글자만 주실래요?"

    # Also avoid repetitive bland acceptances.
    if any(k in body for k in ["비밀은 지킬게", "알겠어용", "알겠어요"]):
        if str(agent_style or "").lower() == "cute":
            return "앗 너무 꽁꽁 숨기네용 ㅎㅎ 그럼 힌트 한 조각만 줘봐용!"
        if str(agent_style or "").lower() == "friend":
            return "오케이 비밀주의네 ㅋㅋ 그럼 힌트 하나만 던져."
        return "좋아요, 비밀이면 힌트 하나만 주실래요?"
    return body


def _agent_quick_banter_reply(lower_message, agent_style="friendly"):
    text = str(lower_message or "").strip().lower()
    if not text:
        return ""
    norm = re.sub(r"\s+", "", text)
    short = len(norm) <= 14
    laugh_like = bool(re.fullmatch(r"[ㅋㅎw!?.~]+", norm)) and len(norm) >= 2
    tease_like = any(k in norm for k in ["바보", "바부", "멍청", "놀려", "약올", "킹받", "놀리냐", "놀리네", "허접", "못하네"])
    ping_like = bool(re.fullmatch(r"(야+|왜+|뭐해+|뭐하냐+|뭐함+|머해+|헐+|엥+|오+|아+|음+)[!?~]*", norm))
    ends_with_talk_marker = bool(re.search(r"(냐|냐\?|지\?|임\?|임)$", norm))
    if not short or not (tease_like or laugh_like or ping_like or (ends_with_talk_marker and len(norm) <= 8)):
        return ""

    style = str(agent_style or "friendly").strip().lower()
    if style == "friend":
        candidates = [
            "야 ㅋㅋ 갑자기 왜 놀려.",
            "또 놀린다? 그래도 받아준다.",
            "어이구, 오늘 장난 모드네.",
        ]
    elif style == "cute":
        candidates = [
            "앗 또 놀리네용 ㅋㅋ",
            "히잉, 장난이면 봐줄게용.",
            "오잉, 오늘 티키타카 가나용?",
        ]
    else:
        candidates = [
            "ㅋㅋ 갑자기 왜 놀려요.",
            "장난이면 인정, 오늘 텐션 좋네요.",
            "오케이, 그 정도 도발은 귀엽게 패스할게요.",
        ]
    return random.choice(candidates)


def _agent_quick_social_reply(lower_message, agent_style="friendly"):
    text = str(lower_message or "").strip().lower()
    if not text:
        return ""
    norm = re.sub(r"\s+", "", text)
    short = len(norm) <= 14
    if not short:
        return ""

    is_apology = any(k in norm for k in ["미안", "쏘리", "sorry", "죄송"])
    is_thanks = any(k in norm for k in ["고마", "감사", "thx", "thanks"])
    if not (is_apology or is_thanks):
        return ""

    style = str(agent_style or "friendly").strip().lower()
    if is_apology:
        if style == "friend":
            return random.choice(["괜찮아 ㅋㅋ 신경 쓰지 마.", "아냐 괜찮아, 편하게 가자."])
        if style == "cute":
            return random.choice(["괜찮아용, 신경 쓰지 마세용.", "아녜용 괜찮아용 ㅎㅎ"])
        return random.choice(["괜찮아요, 신경 안 써도 돼요.", "아니에요, 괜찮아요."])
    if style == "friend":
        return random.choice(["오케이 ㅋㅋ 나도 고마워.", "좋지, 고마워."])
    if style == "cute":
        return random.choice(["고마워용 ㅎㅎ", "헤헷, 고마워용."])
    return random.choice(["고마워요.", "감사해요."])


def _agent_strip_freechat_cta(text):
    body = str(text or "").strip()
    if not body:
        return body
    # Remove assistant-like trailing CTA lines in casual chat.
    body = re.sub(r"\n\s*다음\s*행동\s*:\s*.*$", "", body, flags=re.IGNORECASE | re.MULTILINE).strip()
    body = re.sub(
        r"\s*(원하면|필요하면)\s*[^.\n!?]*(추천|이동|열어|진행|도와)[^.\n!?]*[.!?]?\s*$",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()
    return body


def _agent_llm_style_rewrite(
    *,
    core_answer,
    user_message,
    context_summary,
    agent_style,
    response_length,
    tone_rule,
    length_rule,
    focus_rule,
    proactive_rule,
    response_profile="balanced",
):
    """
    Fast style shaping:
    Keep facts/actions, apply lightweight local style only.
    (Avoids extra LLM roundtrip latency.)
    """
    base = str(core_answer or "").strip()
    if not base:
        return base
    styled = _agent_style_reply(
        base,
        agent_style,
        str(user_message or "").lower(),
        response_profile=response_profile,
    )
    is_banter = _agent_is_banter(str(user_message or "").lower())
    with_banter = _agent_apply_banter_clapback(styled, is_banter=is_banter, agent_style=agent_style)
    return _agent_apply_refusal_banter_guard(
        with_banter,
        user_lower_message=str(user_message or "").lower(),
        agent_style=agent_style,
    )


@csrf_exempt
@require_http_methods(["POST"])
def agent_chat_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    user = _resolve_request_user(request)
    if not user:
        return JsonResponse({"error": "unauthorized"}, status=401)

    message = str(payload.get("message") or "").strip()
    context = payload.get("context") or {}
    history = payload.get("history") or []
    user_selected_style = str((context or {}).get("agent_style") or "").strip().lower()
    mem = _agent_update_user_memory(user, lower_message=message.lower())
    base_style = "friendly"
    response_length = str((context or {}).get("response_length") or mem.get("response_length") or "balanced").strip().lower()
    response_profile = str((context or {}).get("response_profile") or mem.get("response_profile") or "balanced").strip().lower()
    tone_rule = _agent_tone_rule(base_style)
    length_rule = _agent_length_rule(response_length)
    profile_rule = _agent_response_profile_rule(response_profile)

    if not message:
        return JsonResponse({"error": "message required"}, status=400)

    lower = message.lower()
    is_explicit_command = _agent_is_action_query(lower)
    is_review_plan_request = _agent_is_review_plan_request(lower)
    is_banter = _agent_is_banter(lower)
    auto_style = _agent_auto_style(lower, is_explicit_command=is_explicit_command, is_banter=is_banter)
    # Default is fixed-friendly. User selection is advisory only unless explicit trigger exists.
    agent_style = auto_style or base_style
    if user_selected_style in {"friendly", "calm", "coach", "friend", "cute"} and user_selected_style == "friendly":
        agent_style = "friendly"
    mem_style = str(mem.get("style") or "friendly")
    if agent_style == "friendly" and mem_style in {"calm", "coach", "friend", "cute"}:
        agent_style = mem_style
    tone_rule = _agent_tone_rule(agent_style)
    context_summary = _agent_context_summary(context)
    display_name = _agent_display_name(user)
    stylize = lambda t: _agent_style_reply(t, agent_style, lower, response_profile=response_profile)
    rewrite = lambda t: _agent_llm_style_rewrite(
        core_answer=t,
        user_message=message,
        context_summary=context_summary,
        agent_style=agent_style,
        response_length=response_length,
        tone_rule=tone_rule,
        length_rule=length_rule,
        focus_rule=focus_rule,
        proactive_rule=proactive_rule,
        response_profile=response_profile,
    )
    adaptive_length_rule = _agent_adaptive_length_rule(lower, response_length, agent_style, response_profile=response_profile)
    focus_rule = _agent_focus_rule(lower)
    proactive_rule = _agent_proactive_rule(is_explicit_command)

    quick_banter = _agent_quick_banter_reply(lower, agent_style=agent_style)
    if quick_banter and not is_explicit_command and not is_review_plan_request:
        return JsonResponse({
            "ok": True,
            "answer": quick_banter,
            "source": "local_banter",
            "agent_style": agent_style,
        })
    quick_social = _agent_quick_social_reply(lower, agent_style=agent_style)
    if quick_social and not is_explicit_command and not is_review_plan_request:
        return JsonResponse({
            "ok": True,
            "answer": quick_social,
            "source": "local_social",
            "agent_style": agent_style,
        })

    # Free chat-first mode:
    # If this is not an operational/action intent, use LLM first so the agent
    # feels conversational and emotionally responsive.
    if not is_explicit_command and not is_review_plan_request:
        try:
            model = "gpt-5-mini"
            compact_history = []
            for item in history[-10:]:
                role = str(item.get("role") or "").strip().lower()
                text = str(item.get("content") or "").strip()
                if role in {"user", "assistant"} and text:
                    compact_history.append({"role": role, "content": text})

            history_text = "\n".join([f"{h['role']}: {h['content']}" for h in compact_history])
            emotion_hint = _agent_emotion_hint(lower)

            prompt = (
                "당신은 사람처럼 자연스럽게 대화하는 한국어 파트너입니다.\n"
                "- 한국어로 대답\n"
                "- 대화체로 자연스럽게, 기계적인 안내문 톤 금지\n"
                "- 짧은 입력(한두 단어/감탄사/장난)에는 1~2문장으로 가볍게 응답\n"
                "- 같은 시작 문구를 반복하지 마세요\n"
                "- 장난/농담에는 센스 있게 짧게 받아치되 무례하지 않게\n"
                "- 사용자가 요청하지 않은 기능 제안/페이지 이동/추천 문구는 기본적으로 하지 마세요\n"
                f"- 말투 설정({agent_style}): {tone_rule}\n"
                f"- 답변 길이 기본 설정({response_length}): {length_rule}\n"
                f"- 사용자 응답 성향({response_profile}): {profile_rule}\n"
                f"- 답변 길이 자동 조절 규칙: {adaptive_length_rule}\n"
                "- 사실이 불확실하면 추측하지 말고 확인 질문을 1개만 제시\n"
                "- 친구처럼 편안하게 반응하되 정보는 정확하게\n\n"
                f"[티키타카 모드]\n{'ON' if is_banter else 'OFF'}\n\n"
                f"[감정 가이드]\n{emotion_hint}\n\n"
                f"[사용자]\n이름: {display_name}\n"
                f"직책: {getattr(user, 'position', '') or '-'}\n\n"
                f"[현재 페이지]\n{context_summary}\n\n"
                f"[최근 대화]\n{history_text or '(없음)'}\n\n"
                f"[사용자 질문]\n{message}\n\n"
                "답변:"
            )
            llm = generate_review_with_prompt(
                prompt=prompt,
                model=model,
                max_tokens=300,
                temperature=0.5,
            )
            answer = str(llm or "").strip()
            if not answer:
                raise ValueError("empty llm response")
            answer = rewrite(answer)
            answer = _agent_strip_freechat_cta(answer)
            answer = _agent_dedupe_openers(answer, history)
            return JsonResponse({
                "ok": True,
                "answer": answer,
                "source": "llm_chat_first",
                "model": model,
                "suggestions": [],
                "actions": [],
                "agent_style": agent_style,
            })
        except Exception:
            return JsonResponse({
                "ok": True,
                "answer": _agent_failure_response(agent_style=agent_style, lower=lower),
                "source": "llm_chat_fallback",
            })

    if any(k in lower for k in ["내 정보", "내정보", "내 계정", "내계정", "프로필"]):
        position = getattr(user, "position", "") or "-"
        return JsonResponse({
            "ok": True,
            "answer": rewrite(
                f"현재 로그인 사용자 정보입니다.\n"
                f"- 이름: {display_name}\n"
                f"- 아이디: {user.username}\n"
                f"- 이메일: {getattr(user, 'email', '') or '-'}\n"
                f"- 직책: {position}"
            ),
            "source": "local_profile",
            "suggestions": ["내가 할 일 추천해줘", "지금 페이지에서 할 수 있는 작업 알려줘"],
        })

    if is_review_plan_request:
        clinic, procedure = _agent_extract_clinic_procedure(message)
        return JsonResponse({
            "ok": True,
            "answer": rewrite(
                "설계안 입력창을 열었습니다. 병원명/시술명을 입력하고 생성 버튼을 누르면 "
                "AI리뷰생성과 동일한 프롬프트 경로로 리뷰를 생성해 스케줄에 저장합니다."
            ),
            "source": "local_review_plan_form",
            "actions": [{
                "type": "open_review_plan_form",
                "label": "설계안 입력",
                "clinic": clinic,
                "procedure": procedure,
                "model": AGENT_REVIEW_DRAFT_MODEL,
            }],
            "suggestions": ["키워드 없이 기본값으로 생성", "생성 후 대시보드로 이동"],
        })

    if any(k in lower for k in ["리뷰 생성", "리뷰생성", "ai 리뷰", "ai리뷰", "후기 생성", "후기생성", "리뷰 작성", "리뷰작성"]):
        return JsonResponse({
            "ok": True,
            "answer": rewrite("AI 리뷰 생성 페이지로 지금 이동할게요."),
            "source": "local_navigation",
            "actions": [{"type": "navigate", "page": "review"}],
            "suggestions": ["구공이 페이지로 이동해줘", "강남언니 후기로 이동해줘"],
        })

    if any(k in lower for k in ["구공이", "gugong"]):
        return JsonResponse({
            "ok": True,
            "answer": rewrite("구공이 리뷰 생성 페이지로 지금 이동할게요."),
            "source": "local_navigation",
            "actions": [{"type": "navigate", "page": "gugong_review"}],
        })

    if any(k in lower for k in ["강남", "gangnam"]):
        return JsonResponse({
            "ok": True,
            "answer": rewrite("강남언니 후기 생성 페이지로 지금 이동할게요."),
            "source": "local_navigation",
            "actions": [{"type": "navigate", "page": "gangnam_review"}],
        })

    lower_nospace = re.sub(r"\s+", "", lower)
    if _agent_is_page_help_query(lower):
        detail = _agent_context_detail(context)
        wants_explain = any(k in lower for k in ["설명", "뭐", "무엇", "어떤", "어떻게", "순서", "용도", "뭐하는"]) or any(k in lower_nospace for k in ["뭐하는", "설명", "용도"])
        return JsonResponse({
            "ok": True,
            "answer": rewrite(
                f"현재 화면: {context_summary}\n"
                f"{detail if wants_explain else '원하시면 이 화면에서 자주 하는 작업 순서도 같이 안내해드릴게요.'}"
            ),
            "source": "local_context",
            "suggestions": ["이 화면 작업 순서 알려줘", "다음에 할 일 추천해줘"],
        })

    if any(k in lower for k in ["알림", "notifications"]):
        noti = _agent_fetch_json(request, "/api/data/notifications/?limit=1")
        unread = int((noti or {}).get("unread_count") or 0)
        return JsonResponse({
            "ok": True,
            "answer": rewrite(f"현재 미확인 알림은 {unread}건입니다."),
            "source": "tool_notifications",
            "actions": [{"type": "navigate", "page": "notifications_center"}],
        })

    if any(k in lower for k in ["메일", "mail", "메시지"]):
        mail = _agent_fetch_json(request, "/api/data/messages/?box=inbox&limit=1")
        unread = int((mail or {}).get("unread_count") or 0)
        return JsonResponse({
            "ok": True,
            "answer": rewrite(f"받은 메일 미확인은 {unread}건입니다."),
            "source": "tool_messages",
            "actions": [{"type": "navigate", "page": "mail_center"}],
        })

    if any(k in lower for k in ["근태", "출퇴근", "출근", "퇴근"]):
        attendance = _agent_fetch_json(request, "/api/data/attendance/me/")
        if isinstance(attendance, dict):
            worked_days = attendance.get("worked_days")
            late_count = attendance.get("late_count")
            pending = attendance.get("pending_corrections")
            parts = []
            if worked_days is not None:
                parts.append(f"근무일수 {worked_days}일")
            if late_count is not None:
                parts.append(f"지각 {late_count}회")
            if pending is not None:
                parts.append(f"정정대기 {pending}건")
            text = ", ".join(parts) if parts else "근태 데이터는 조회되지만 요약 키를 찾지 못했습니다."
        else:
            text = "근태 데이터를 불러오지 못했습니다."
        return JsonResponse({
            "ok": True,
            "answer": rewrite(text),
            "source": "tool_attendance",
            "actions": [{"type": "navigate", "page": "attendance_requests"}],
        })

    if any(k in lower for k in ["휴가", "연차"]):
        year = timezone.localtime().year
        vacation = _agent_fetch_json(request, f"/api/data/vacations/me/?year={year}")
        return JsonResponse({
            "ok": True,
            "answer": rewrite(_agent_vacation_summary(vacation)),
            "source": "tool_vacation",
            "actions": [{"type": "navigate", "page": "vacation"}],
        })

    if any(k in lower for k in ["요약", "브리핑", "한눈"]):
        noti = _agent_fetch_json(request, "/api/data/notifications/?limit=1")
        mail = _agent_fetch_json(request, "/api/data/messages/?box=inbox&limit=1")
        year = timezone.localtime().year
        vacation = _agent_fetch_json(request, f"/api/data/vacations/me/?year={year}")
        lines = [
            f"- 미확인 알림: {int((noti or {}).get('unread_count') or 0)}건",
            f"- 미확인 메일: {int((mail or {}).get('unread_count') or 0)}건",
            f"- {_agent_vacation_summary(vacation)}",
        ]
        return JsonResponse({
            "ok": True,
            "answer": rewrite("현재 업무 요약입니다.\n" + "\n".join(lines)),
            "source": "tool_summary",
            "suggestions": ["알림센터 열어줘", "메일센터 열어줘", "휴가 페이지로 이동해줘"],
        })

    # LLM fallback: lightweight Q&A mode for app-wide assistant MVP.
    try:
        model = "gpt-5-mini"
        compact_history = []
        for item in history[-6:]:
            role = str(item.get("role") or "").strip().lower()
            text = str(item.get("content") or "").strip()
            if role in {"user", "assistant"} and text:
                compact_history.append({"role": role, "content": text})

        history_text = "\n".join(
            [f"{h['role']}: {h['content']}" for h in compact_history]
        )
        prompt = (
            "당신은 사내 업무 앱의 AI 에이전트입니다.\n"
            "- 한국어로 간결하게 답변\n"
            "- 같은 도입 문구(예: '심심하셨구나', '궁금했구나')를 반복해서 시작하지 마세요\n"
            "- 장난/농담/가벼운 도발에는 과하게 사과하지 말고, 짧고 센스 있게 받아치세요\n"
            "- 티키타카 모드가 ON이면, 가끔은 가벼운 반말 한 줄로 맞받아친 뒤 본답변을 이어가세요 (무례 금지)\n"
            f"- 말투 설정({agent_style}): {tone_rule}\n"
            f"- 답변 길이 기본 설정({response_length}): {length_rule}\n"
            f"- 사용자 응답 성향({response_profile}): {profile_rule}\n"
            f"- 답변 길이 자동 조절 규칙: {adaptive_length_rule}\n"
            f"- 대화 초점 규칙: {focus_rule}\n"
            f"- 실행/제안 규칙: {proactive_rule}\n"
            "- 사용자가 현재 화면/업무를 묻지 않았다면 현재 페이지를 먼저 언급하지 마세요\n"
            "- friend 모드인 경우: 반말만 사용하고 존댓말(~요/~습니다) 금지\n"
            "- friend 모드인 경우: 가벼운 투덜/까칠함은 허용하되, 비난/무례/공격적 표현은 금지\n"
            "- friend 모드인 경우: 사용자가 요청하지 않은 선택지 나열/장황한 안내 금지\n"
            "- 확실하지 않으면 추측하지 말고 확인이 필요하다고 말할 것\n"
            "- 민감정보/권한이 필요한 작업은 사용자에게 확인 요청\n\n"
            f"[티키타카 모드]\n{'ON' if is_banter else 'OFF'}\n\n"
            f"[현재 페이지]\n{context_summary}\n\n"
            f"[최근 대화]\n{history_text or '(없음)'}\n\n"
            f"[사용자 질문]\n{message}\n\n"
            "답변:"
        )
        llm = generate_review_with_prompt(
            prompt=prompt,
            model=model,
            max_tokens=260,
            temperature=0.3,
        )
        answer = str(llm or "").strip()
        if not answer:
            raise ValueError("empty llm response")
        answer = rewrite(answer)
        return JsonResponse({
            "ok": True,
            "answer": answer,
            "source": "llm",
            "model": model,
        })
    except Exception:
        return JsonResponse({
            "ok": True,
            "answer": stylize(
                "AI 응답 엔진이 아직 준비되지 않았습니다. "
                "지금은 메뉴 이동/기본 안내 중심으로만 답변할 수 있습니다."
            ),
            "source": "fallback",
            "suggestions": ["내 정보 보여줘", "리뷰 생성으로 이동해줘", "현재 페이지 설명해줘"],
        })


@csrf_exempt
@require_http_methods(["POST"])
def agent_chat_stream_api(request):
    """
    NDJSON streaming wrapper for agent chat.
    - Reuses `agent_chat_api` logic for answer/actions.
    - Streams token-like delta chunks to renderer.
    """
    base_resp = agent_chat_api(request)
    status = getattr(base_resp, "status_code", 200)

    try:
        payload = json.loads((base_resp.content or b"{}").decode("utf-8"))
    except Exception:
        payload = {"ok": False, "answer": "응답 파싱 실패"}

    if status >= 400:
        return JsonResponse(payload, status=status)

    answer = str(payload.get("answer") or "")
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    source = payload.get("source")
    model = payload.get("model")
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []

    def gen():
        yield json.dumps({"type": "start", "ok": bool(payload.get("ok", True))}, ensure_ascii=False) + "\n"
        step = 3
        for i in range(0, len(answer), step):
            chunk = answer[i:i + step]
            yield json.dumps({"type": "delta", "text": chunk}, ensure_ascii=False) + "\n"
        done = {
            "type": "done",
            "ok": bool(payload.get("ok", True)),
            "answer": answer,
            "actions": actions,
            "source": source,
            "model": model,
            "suggestions": suggestions,
        }
        yield json.dumps(done, ensure_ascii=False) + "\n"

    resp = StreamingHttpResponse(gen(), content_type="application/x-ndjson; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@csrf_exempt
@require_http_methods(["POST"])
def agent_review_plan_generate_api(request):
    user = _resolve_request_user(request)
    if not user:
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    plan_title = str(data.get("plan_title") or "").strip()
    clinic_name = str(data.get("clinic_name") or "").strip()
    procedure_name = str(data.get("procedure_name") or "").strip()
    platform_account = str(data.get("platform_account") or "").strip()
    platform_password = str(data.get("platform_password") or "").strip()
    if not plan_title:
        return JsonResponse({"error": "plan_title required"}, status=400)

    raw_model = str(data.get("model") or AGENT_REVIEW_DRAFT_MODEL).strip()
    model = MODEL_ALIAS_MAP.get(raw_model, raw_model)
    if not str(model).startswith("ft:"):
        model = AGENT_REVIEW_DRAFT_MODEL

    try:
        rows, drafts_by_label, plan_id, keywords_used = _agent_generate_review_plan_from_form(
            user=user,
            plan_title=plan_title,
            clinic_name=clinic_name,
            procedure_name=procedure_name,
            keywords=data.get("keywords"),
            tone=data.get("tone"),
            platform_account=platform_account,
            platform_password=platform_password,
            count=data.get("count"),
            plan_groups=data.get("plan_groups"),
            model=model,
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    schedule_lines = "\n".join([f"- {r['label']}: {r['date'].isoformat()}" for r in rows])

    context_label = " ".join([v for v in [clinic_name, procedure_name] if v]).strip()
    title_line = f"[{plan_title}] {context_label} 설계안 생성이 완료되었습니다." if context_label else f"[{plan_title}] 설계안 생성이 완료되었습니다."

    return JsonResponse({
        "ok": True,
        "answer": (
            f"{title_line}\n\n"
            f"[업로드 스케줄]\n{schedule_lines}\n\n"
            f"스케줄 알림 {len(rows)}건을 등록했습니다."
        ),
        "source": "agent_review_plan_generate",
        "plan_id": plan_id,
        "keywords_used": keywords_used,
        "actions": [{"type": "navigate", "page": "my_dashboard"}],
    })


@csrf_exempt
def review_generate_api(request):
    """
    ❗ 일반 AI 리뷰 생성 전용
    ❗ 강남언니 사용 금지
    """
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    context = data.get("context", {}) or {}
    if context.get("platform") == "gangnam":
        return JsonResponse(
            {"error": "use /api/ml/gangnam_review/"},
            status=400
        )

    raw_model = data.get("model")
    model = MODEL_ALIAS_MAP.get(raw_model)
    if not model:
        return JsonResponse({"error": f"unknown model: {raw_model}"}, status=400)

    prompt = context.get("prompt")
    if not prompt:
        # FT 모델이면 짧은 프롬프트 생성
        if str(model).startswith("ft:"):
            clinic = None
            clinic_id = context.get("clinic_id")
            if clinic_id:
                clinic = ClinicGuide.objects.filter(pk=clinic_id).first()

            persona = None
            personas = context.get("personas") or []
            if isinstance(personas, str):
                personas = [p.strip() for p in personas.split(",") if p.strip()]
            if personas:
                persona = Persona.objects.filter(name=personas[0]).first()

            prompt = build_ft_prompt_from_models(
                clinic=clinic,
                doctor_code=context.get("doctor_code") or None,
                procedure=context.get("procedure") or "시술",
                content_type=context.get("content_type") or "procedure",
                content_type_profile=None,
                persona=persona,
                cafe=None,
                consultant_name=context.get("consultant_name"),
                custom_instructions=context.get("custom_instructions"),
            )
        else:
            return JsonResponse({"error": "missing prompt"}, status=400)

    prompt = apply_review_type_guard(prompt)

    print("[DEBUG] ml/views_api build_ft_prompt_from_models prompt preview:")
    print(prompt)
    print(
        f"[DEBUG] review_generate_api model={model} "
        f"review_intent={context.get('review_intent') or context.get('review_type') or context.get('content_type')}"
    )

    keywords_used = context.get("keywords") or []
    if isinstance(keywords_used, str):
        keywords_used = [k.strip() for k in keywords_used.split(",") if k.strip()]

    try:
        result = generate_review_with_prompt_enforced(
            prompt=prompt,
            model=model,
            max_tokens=1200,
            return_usage=True,
            keywords=keywords_used,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    user = _resolve_request_user(request)
    if user and isinstance(result, dict):
        log_llm_usage(user=user, model=model, usage=result)

    # 생성 리뷰 저장 (앱/웹 공통 관리)
    clinic = None
    persona = None
    clinic_id = context.get("clinic_id")
    if clinic_id:
        clinic = ClinicGuide.objects.filter(pk=clinic_id).first()
    personas = context.get("personas") or []
    if isinstance(personas, str):
        personas = [p.strip() for p in personas.split(",") if p.strip()]
    if personas:
        persona = Persona.objects.filter(name=personas[0]).first()
    review_text = result["text"] if isinstance(result, dict) else result
    title_suggestions = generate_title_suggestions(review_text, model=model)

    generated_review = GeneratedReview.objects.create(
        clinic=clinic,
        persona=persona,
        cafe=None,
        doctor_code="",
        doctor_name="",
        procedure="",
        generated_text=review_text,
        prompt_used=prompt,
        model_used=model,
        keywords_used=keywords_used,
        persona_text=persona.name if persona else "",
        title_suggestions=title_suggestions,
    )

    return JsonResponse({
        "review_text": review_text,
        "model": model,
        "review_id": generated_review.id,
        "title_suggestions": title_suggestions,
        "usage": {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cached_input_tokens": result.get("cached_input_tokens", 0),
            "total_tokens": result.get("total_tokens", 0),
            "cost_usd": result.get("cost_usd", 0),
        } if isinstance(result, dict) else None,
    })


@csrf_exempt
@require_http_methods(["POST"])
def review_save_edit_api(request):
    """앱/웹 공통 수정본 저장 API"""
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    review_id = data.get("review_id")
    edited_text = (data.get("edited_text") or "").strip()
    title_suggestions = data.get("title_suggestions")
    regenerate_titles = bool(data.get("regenerate_titles", False))

    if not review_id or not edited_text:
        return JsonResponse({"error": "review_id and edited_text required"}, status=400)

    original = GeneratedReview.objects.filter(pk=review_id).first()
    if not original:
        return JsonResponse({"error": "review not found"}, status=404)

    # 수정 저장은 빠른 응답이 목적이라 기본적으로 기존 제목을 재사용한다.
    # 제목 재생성이 필요하면 regenerate_titles=true 로 명시한다.
    if not isinstance(title_suggestions, list):
        if regenerate_titles:
            title_suggestions = generate_title_suggestions(
                edited_text,
                model=original.model_used or "gpt-5-mini",
            )
        else:
            title_suggestions = list(original.title_suggestions or [])

    edited = GeneratedReview.objects.create(
        clinic=original.clinic,
        persona=original.persona,
        cafe=original.cafe,
        doctor_code=original.doctor_code,
        doctor_name=original.doctor_name,
        procedure=original.procedure,
        generated_text=edited_text,
        prompt_used=f"[수정본 저장] 원본 #{original.id}\n\n{original.prompt_used}",
        model_used=original.model_used,
        keywords_used=original.keywords_used,
        persona_text=original.persona_text,
        title_suggestions=title_suggestions,
        status="edited",
    )

    return JsonResponse({
        "success": True,
        "review_id": edited.id,
        "review_text": edited.generated_text,
        "char_count": len(edited.generated_text),
        "status": edited.status,
        "model": edited.model_used,
        "title_suggestions": edited.title_suggestions,
    })

@csrf_exempt
@require_http_methods(["POST"])
def api_generate_gangnam_review(request):
    """강남언니 형식 후기 생성 API (웹/앱 공용 기준)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    hospital_name = data.get("hospital_name", "").strip()
    procedure_type = data.get("procedure_type", "").strip()
    if not hospital_name or not procedure_type:
        return JsonResponse({"error": "병원명과 시술 종류는 필수입니다."}, status=400)

    procedure_detail = data.get("procedure_detail", "")
    doctor_name = data.get("doctor_name", "")
    anesthesia = data.get("anesthesia", "")
    price_range = data.get("price_range", "")

    procedure_date_input = data.get("procedure_date", "")
    write_date_input = data.get("write_date", "")

    write_date = datetime.strptime(write_date_input, "%Y-%m-%d") if write_date_input else datetime.now()
    procedure_date = (
        datetime.strptime(procedure_date_input, "%Y-%m-%d")
        if procedure_date_input else write_date - timedelta(days=random.randint(7, 30))
    )

    procedure_date_str = procedure_date.strftime("%Y-%m-%d")
    write_date_str = write_date.strftime("%Y-%m-%d")
    days_since = (write_date - procedure_date).days

    before_concern = data.get("before_concern", "")
    satisfaction_level = data.get("satisfaction_level", "매우 만족")
    good_points_hint = data.get("good_points_hint", "")
    bad_points_hint = data.get("bad_points_hint", "")
    persona_age = data.get("persona_age", "20대 중후반")
    persona_gender = data.get("persona_gender", "여성")
    persona_tone = data.get("persona_tone", "친근한")
    emoji_usage = data.get("emoji_usage", "적당히")
    forbidden_expressions = data.get("forbidden_expressions", "")
    raw_model = data.get("model")
    model = MODEL_ALIAS_MAP.get(raw_model, raw_model) if raw_model else "claude-sonnet-4-5-20250929"
    temperature = data.get("temperature", 0.85)

    rating_map = {
        "매우 만족": 5.0,
        "만족": 4.5,
        "보통": 3.5,
        "약간 아쉬움": 3.0,
    }
    rating = rating_map.get(satisfaction_level, 4.5)

    reason_tags = "합리적 가격, 높은 평점, 후기 내용, 의사 전문성, 병원 인지도, 병원 위치, 재방문, 지인 추천, 병원 시설, 최신 기기, 앱결제, 포인트 사용, 기타"
    good_tags = "빠른 효과, 결과 만족, 부작용 없음, 적은 통증, 흉터 없음, 빠른 회복, 일상 생활 가능, 꼼꼼한 시술, 애프터케어, 기타, 없어요"
    bad_tags = "효과 없음, 결과 불만족, 부작용 있음, 시술 중 통증, 시술 후 통증, 흉터 남음, 더딘 회복, 일상 복귀 시간 필요, 성의 없는 시술, 애프터케어 부족, 기타, 없어요"
    reason_tags_list = [t.strip() for t in reason_tags.split(",")]
    good_tags_list = [t.strip() for t in good_tags.split(",")]
    bad_tags_list = [t.strip() for t in bad_tags.split(",")]

    try:
        template = PromptTemplate.objects.filter(
            mode="app_gangnam", is_active=True, is_default=True
        ).first()
        if not template:
            template = PromptTemplate.objects.filter(
                mode="app_gangnam", is_active=True
            ).first()
    except Exception:
        template = None

    prompt_vars = {
        "persona_age": persona_age,
        "persona_gender": persona_gender,
        "persona_tone": persona_tone,
        "emoji_usage": emoji_usage,
        "hospital_name": hospital_name,
        "procedure_type": procedure_type,
        "procedure_detail_line": f"- 시술 상세: {procedure_detail}" if procedure_detail else "",
        "doctor_line": f"- 담당 의사: {doctor_name}" if doctor_name else "",
        "anesthesia_line": f"- 마취 방법: {anesthesia}" if anesthesia else "",
        "price_line": f"- 가격대: {price_range}" if price_range else "",
        "procedure_date": procedure_date_str,
        "write_date": write_date_str,
        "days_since": days_since,
        "satisfaction_level": satisfaction_level,
        "before_concern_line": f"- 시술 전 고민/계기: {before_concern}" if before_concern else "",
        "good_points_line": f"- 강조할 좋은 점: {good_points_hint}" if good_points_hint else "",
        "bad_points_line": f"- 아쉬운 점: {bad_points_hint}" if bad_points_hint else "",
        "reason_tags": reason_tags,
        "good_tags": good_tags,
        "bad_tags": bad_tags,
        "rating": rating,
        "forbidden_line": f"8. 다음 표현은 절대 사용 금지: {forbidden_expressions}" if forbidden_expressions else "",
    }

    prompt = f"""당신은 강남언니 앱에 시술 후기를 작성하는 실제 고객입니다.
강남언니 앱의 리뷰 작성 플로우에 맞춰 후기를 생성해주세요.

## 작성자 페르소나
- 연령/성별: {persona_age} {persona_gender}
- 말투: {persona_tone}
- 이모티콘 사용: {emoji_usage}

## 시술 정보
- 병원명: {hospital_name}
- 시술 종류: {procedure_type}
{f'- 시술 상세: {procedure_detail}' if procedure_detail else ''}
{f'- 담당 의사: {doctor_name}' if doctor_name else ''}
{f'- 마취 방법: {anesthesia}' if anesthesia else ''}
{f'- 가격대: {price_range}' if price_range else ''}
- 시술일: {procedure_date_str} (작성일 기준 {days_since}일 전)
- 작성일: {write_date_str}

## 시술 경험
- 만족도: {satisfaction_level}
{f'- 시술 전 고민/계기: {before_concern}' if before_concern else ''}
{f'- 강조할 좋은 점: {good_points_hint}' if good_points_hint else ''}
{f'- 아쉬운 점: {bad_points_hint}' if bad_points_hint else ''}

## 사용 가능한 태그 목록
- 병원 선택 이유: {reason_tags}
- 좋았던 점: {good_tags}
- 아쉬운 점: {bad_tags}

## 출력 형식 (반드시 아래 JSON 형식으로만 출력)
{{
  "before_worry": "시술 전 고민과 시술을 결정한 계기 (50~150자)",
  "reason_tags": ["태그1", "태그2"],
  "result_review": "시술 결과 후기 (80~200자, 최소 10자)",
  "good_tags": ["태그1", "태그2"],
  "bad_tags": ["태그1"],
  "bad_reason": "아쉬운 점을 선택한 이유 (30~80자, 최소 10자. 아쉬운 점이 없으면 '딱히 없어요~' 같은 표현)",
  "rating": {rating},
  "additional": "추가 의견 (30~80자, 최소 10자, 전체적인 소감이나 추천 여부)"
}}

## 작성 원칙
1. 실제 시술 받은 사람처럼 자연스럽게
2. 광고성 표현 절대 금지
3. 각 섹션의 글자수 반드시 준수
4. 태그는 위 목록에서만 선택 (1~3개씩)
5. JSON 형식만 출력 (다른 텍스트 없이)
6. 이모티콘은 '{emoji_usage}' 수준으로 사용
7. 아쉬운 점이 없으면 bad_tags에 ["없어요"] 사용
{f'8. 다음 표현은 절대 사용 금지: {forbidden_expressions}' if forbidden_expressions else ''}

JSON 출력:"""
    if template:
        try:
            prompt = template.content.format(**prompt_vars)
        except KeyError:
            pass

    prompt = apply_review_type_guard(prompt)

    try:
        result = generate_review_with_prompt_enforced(
            prompt, model=model, return_usage=True, temperature=temperature, max_tokens=900
        )

        text = result["text"].strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        def extract_json_payload(raw_text):
            try:
                data_obj = json.loads(raw_text)
                return data_obj if isinstance(data_obj, dict) else None
            except Exception:
                pass

            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end > start:
                candidate = raw_text[start:end + 1]
                try:
                    data_obj = json.loads(candidate)
                    return data_obj if isinstance(data_obj, dict) else None
                except Exception:
                    return None
            return None

        parsed = extract_json_payload(text) or {}

        def extract_field(raw_text, field_name):
            import re
            pattern = rf'"{field_name}"\\s*:\\s*"(?P<val>.*?)"'
            match = re.search(pattern, raw_text, re.DOTALL)
            if not match:
                return ""
            raw_val = match.group("val")
            try:
                return json.loads(f"\"{raw_val}\"")
            except Exception:
                return raw_val.replace("\\n", "\n").replace("\\t", "\t")

        def extract_field_loose(raw_text, field_name):
            import re
            key_match = re.search(rf'"{field_name}"\\s*:\\s*"', raw_text)
            if not key_match:
                return ""
            rest = raw_text[key_match.end():]
            next_key = re.search(r'\n\\s*\"[A-Za-z_]+\"\\s*:', rest)
            value = rest[:next_key.start()] if next_key else rest
            value = value.rstrip().rstrip(",")
            if value.endswith("\""):
                value = value[:-1]
            try:
                return json.loads(f"\"{value}\"")
            except Exception:
                return value.replace("\\n", "\n").replace("\\t", "\t")

        def normalize_tags(value):
            if not value:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return []

        looks_like_json = text.lstrip().startswith("{") and text.rstrip().endswith("}")
        result_review = (
            parsed.get("result_review")
            or parsed.get("content")
            or extract_field(text, "result_review")
            or extract_field(text, "content")
            or extract_field_loose(text, "result_review")
            or extract_field_loose(text, "content")
        )
        if not result_review:
            result_review = "" if looks_like_json or "\"result_review\"" in text else text
        before_worry = (
            parsed.get("before_worry")
            or extract_field(text, "before_worry")
            or extract_field_loose(text, "before_worry")
            or before_concern
            or ""
        )
        bad_reason = (
            parsed.get("bad_reason")
            or extract_field(text, "bad_reason")
            or extract_field_loose(text, "bad_reason")
            or bad_points_hint
            or ""
        )
        additional = (
            parsed.get("additional")
            or extract_field(text, "additional")
            or extract_field_loose(text, "additional")
            or parsed.get("title")
            or extract_field(text, "title")
            or extract_field_loose(text, "title")
            or ""
        )
        reason_selected = normalize_tags(parsed.get("reason_tags", []))
        good_selected = normalize_tags(parsed.get("good_tags", []))
        bad_selected = normalize_tags(parsed.get("bad_tags", [])) or ["없어요"]
        cost_krw = result["cost_usd"] * 1450

        user = _resolve_request_user(request)
        if user:
            log_llm_usage(user=user, model=model, usage=result)

        title_suggestions = generate_title_suggestions(result_review, model=model)

        return JsonResponse({
            "success": True,
            "procedure_date": procedure_date_str,
            "write_date": write_date_str,
            "before_worry": before_worry,
            "reason_tags": reason_selected,
            "result_review": result_review,
            "raw_text": result_review,
            "good_tags": good_selected,
            "bad_tags": bad_selected,
            "bad_reason": bad_reason,
            "rating": parsed.get("rating", rating),
            "additional": additional,
            "title_suggestions": title_suggestions,
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

