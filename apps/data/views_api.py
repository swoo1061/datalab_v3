from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime
from datetime import date, datetime, time, timedelta
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from urllib.parse import urlsplit
import json
import re
import uuid

from apps.ml.services.llm.registry import LLM_MODELS
from apps.ml.services.llm_service import generate_review_with_prompt
from apps.data.models import (
    ClinicGuide,
    ClinicDoctor,
    ClinicPrice,
    ClinicPost,
    ClinicPostPhoto,
    ClinicCommentBundle,
    ClinicMessageLog,
    ClinicNotice,
    ClinicNoticeRead,
    GlobalNotice,
    GlobalNoticeRead,
    CalendarMemo,
    ReviewSchedule,
    AttendanceCorrectionRequest,
    VacationRequest,
    SystemPermission,
)
from apps.data.permissions import get_user_permission, normalize_user_role

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, BaseAuthentication

from .models import FavoriteClinic, ClinicAssignee
from .serializers import (
    FavoriteClinicSerializer,
    ClinicPostSerializer,
    ClinicCommentBundleSerializer,
    ClinicMessageLogSerializer,
    ClinicNoticeSerializer,
    GlobalNoticeSerializer,
    CalendarMemoSerializer,
    ReviewScheduleSerializer,
)

ATTENDANCE_MEMO_PLATFORM = "__attendance_correction__"
VACATION_MEMO_PLATFORM = "__vacation__"
REVIEW_SCHEDULE_PLATFORM = "__review_schedule__"
_REVIEW_SCHEDULE_NEW_RE = re.compile(
    r"^\[리뷰설계\/([^\/\]]+)\/([^\]]+)\]\s*([\s\S]*?)(?:\n(?:리뷰|초안):\s*([\s\S]*))?$"
)
_REVIEW_SCHEDULE_OLD_RE = re.compile(
    r"^\[리뷰설계\/([^\]]+)\]\s*([\s\S]*?)(?:\n(?:리뷰|초안):\s*([\s\S]*))?$"
)


def _split_plan_title_from_detail(raw_detail):
    detail = str(raw_detail or "").strip()
    plan_title = ""
    lines = detail.splitlines()
    kept = []
    for ln in lines:
        s = str(ln or "").strip()
        if s.startswith("설계안 제목:"):
            plan_title = s.split(":", 1)[1].strip()
            continue
        kept.append(ln)
    cleaned = "\n".join(kept).strip()
    return plan_title, cleaned


def _parse_review_schedule_content(raw_content):
    raw = (raw_content or "").strip()
    m_new = _REVIEW_SCHEDULE_NEW_RE.match(raw)
    if m_new:
        plan_title, cleaned_detail = _split_plan_title_from_detail(m_new.group(3))
        return {
            "plan_id": (m_new.group(1) or "").strip(),
            "label": (m_new.group(2) or "").strip(),
            "detail": cleaned_detail,
            "draft": (m_new.group(4) or "").strip(),
            "plan_title": plan_title,
        }
    m_old = _REVIEW_SCHEDULE_OLD_RE.match(raw)
    if m_old:
        plan_title, cleaned_detail = _split_plan_title_from_detail(m_old.group(2))
        return {
            "plan_id": "",
            "label": (m_old.group(1) or "").strip(),
            "detail": cleaned_detail,
            "draft": (m_old.group(3) or "").strip(),
            "plan_title": plan_title,
        }
    plan_title, cleaned_detail = _split_plan_title_from_detail(raw)
    return {
        "plan_id": "",
        "label": "",
        "detail": cleaned_detail,
        "draft": "",
        "plan_title": plan_title,
    }


def _build_review_schedule_content(*, plan_id, label, detail, draft, plan_title=""):
    pid = str(plan_id or "").strip()
    l = str(label or "").strip()
    d = str(detail or "").strip()
    dr = str(draft or "").strip()
    pt = str(plan_title or "").strip()
    content = f"[리뷰설계/{pid}/{l}] {d}" if pid else f"[리뷰설계/{l}] {d}"
    if pt:
        content += f"\n설계안 제목: {pt}"
    if dr:
        content += f"\n초안: {dr}"
    return content


def _normalize_url(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        if not parsed.scheme and not parsed.netloc:
            parsed = urlsplit(f"https://{raw.lstrip('/')}")
        host = str(parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host.startswith("m."):
            host = host[2:]
        path = str(parsed.path or "").rstrip("/")
        return f"{host}{path}" if host else path
    except Exception:
        return raw.rstrip("/")


def _normalize_url_host_path(value):
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    try:
        parsed = urlsplit(raw)
        host = str(parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host.startswith("m."):
            host = host[2:]
        path = str(parsed.path or "").rstrip("/")
        return host, path
    except Exception:
        return "", ""


def _find_clinic_post_by_url(clinic, url):
    matches = _get_clinic_posts_by_url(clinic, url)
    if not matches:
        return None
    return matches[0]


def _get_clinic_posts_by_url(clinic, url):
    normalized = _normalize_url(url)
    if not normalized:
        return []

    candidates = ClinicPost.objects.filter(clinic=clinic).only("id", "url", "comments", "message_count", "updated_at")
    target_host, target_path = _normalize_url_host_path(url)
    if not target_host:
        target_host, target_path = _normalize_url_host_path(f"https://{str(url or '').lstrip('/')}")
    target_key = f"{target_host}{target_path}" if target_host else normalized

    matched = []
    for candidate in candidates:
        candidate_key = _normalize_url(candidate.url)
        host, path = _normalize_url_host_path(candidate.url)
        host_path_key = f"{host}{path}" if host else candidate_key
        if candidate_key == normalized or host_path_key == target_key:
            matched.append(candidate)

    if not matched:
        return []
    return sorted(matched, key=lambda x: x.updated_at or timezone.now(), reverse=True)


def _clinic_has_post_url(clinic, url):
    return _find_clinic_post_by_url(clinic, url) is not None


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # CSRF 체크 완전히 비활성화

class HeaderSessionAuthentication(BaseAuthentication):
    def authenticate(self, request):
        session_key = request.headers.get("X-Sessionid")
        if not session_key:
            return None
        try:
            session = Session.objects.get(
                session_key=session_key,
                expire_date__gte=timezone.now()
            )
        except Session.DoesNotExist:
            return None
        user_id = session.get_decoded().get("_auth_user_id")
        if not user_id:
            return None
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        return (user, None)

@csrf_exempt
@require_GET
def clinic_list_api(request):
    qs = (
        ClinicGuide.objects
        .filter(is_active=True)
        .values("id", "name")
        .order_by("name")
    )

    return JsonResponse(
        {
            "count": qs.count(),
            "results": list(qs),
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def clinic_detail_api(request, clinic_id):
    try:
        clinic = ClinicGuide.objects.get(id=clinic_id, is_active=True)
        # print("🔥 RAW CONSULTANTS:", clinic.consultants, type(clinic.consultants)) # 디버깅용
    except ClinicGuide.DoesNotExist:
        raise Http404("Clinic not found")

    doctors = list(
        ClinicDoctor.objects
        .filter(clinic=clinic, is_active=True)
        .order_by("order")
        .values("id", "code", "name", "style", "specialties")
    )

    prices = []
    for p in ClinicPrice.objects.filter(clinic=clinic, is_active=True):
        prices.append({
            "procedure": p.procedure,
            "price_display": p.price_display or "상담 필요",
            "doctor_code": p.doctor.code if p.doctor else None,
            "doctor_name": p.doctor.name if p.doctor else "공통",
        })

    return JsonResponse({
        "clinic": {
            "id": clinic.id,
            "name": clinic.name,
            "location": clinic.location,
            "hours": clinic.hours,
            "parking": clinic.parking,
            "process": clinic.process,
        },
        "doctors": doctors,
        "price_list": prices,
        "consultants": clinic.consultants or [],
        "aftercare": list(clinic.aftercare.values()) if isinstance(clinic.aftercare, dict) else clinic.aftercare,
        "raw_data": clinic.raw_data or {},
    }, json_dumps_params={"ensure_ascii": False})

def normalize_consultants(consultants):
    """
    상담실장 데이터를 UI 친화적 구조로 정규화
    """
    if not consultants:
        return []

    result = []

    def push(name=None, style="", role=""):
        if name:
            result.append({
                "name": name,
                "style": style or "",
                "role": role or "",
            })

    # list 형태
    if isinstance(consultants, list):
        for c in consultants:
            if isinstance(c, str):
                push(name=c)
            elif isinstance(c, dict):
                push(
                    name=c.get("name"),
                    style=c.get("style") or c.get("desc") or c.get("description"),
                    role=c.get("role"),
                )
        return result

    # dict 형태
    if isinstance(consultants, dict):
        for _, v in consultants.items():
            if isinstance(v, str):
                push(name=v)
            elif isinstance(v, dict):
                push(
                    name=v.get("name"),
                    style=v.get("style") or v.get("desc"),
                    role=v.get("role"),
                )
        return result

    # string 형태
    if isinstance(consultants, str):
        return [{
            "name": consultants,
            "style": "",
            "role": "",
        }]

    return []


def _extract_json_payload(text):
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _parse_assignee_param(raw_value):
    if not raw_value or raw_value == "all":
        return None, None
    if raw_value == "me" or raw_value.startswith("me:"):
        return "me", None
    if raw_value.isdigit():
        return "id", int(raw_value)
    return "invalid", None


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _can_manage_global_notice(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = normalize_user_role(user)
    return role in {"admin", "ceo", "leader"}


def _parse_datetime_value(raw):
    if not raw:
        return None
    if isinstance(raw, datetime):
        parsed = raw
    elif isinstance(raw, str):
        parsed = parse_datetime(raw)
        if parsed is None:
            try:
                parsed = datetime.combine(date.fromisoformat(raw), time.min)
            except ValueError:
                return None
    else:
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _fallback_classify_post(title, platform):
    title = (title or "").lower()
    review_keywords = ["후기", "리뷰", "수술후기", "상담후기"]
    review_platforms = {"gangnam", "gn_jp", "babytok", "todaktok", "yeoshin", "seongyesa"}

    is_review = any(k in title for k in review_keywords) or platform in review_platforms
    post_type = "review" if is_review else "opinion"

    if post_type == "review":
        photo_keywords = ["사진", "포토", "셀카", "before", "after"]
        review_subtype = "photo" if any(k in title for k in photo_keywords) else "text"
    else:
        review_subtype = None

    return post_type, review_subtype


def classify_post_type_and_subtype(title, platform, url, model="gpt-5-mini"):
    prompt = f"""
아래 게시글 메타데이터를 보고 분류하세요.
반드시 JSON만 출력합니다.

필드:
- type: "opinion" 또는 "review"
- review_subtype: type이 review일 때 "text" 또는 "photo", 그 외 null

메타:
platform: {platform}
title: {title or ""}
url: {url or ""}

JSON 예시:
{{"type":"review","review_subtype":"text"}}
"""
    try:
        raw = generate_review_with_prompt(
            prompt=prompt,
            model=model,
            max_tokens=120,
            temperature=0.0,
        )
        data = _extract_json_payload(raw)
        if isinstance(data, dict):
            post_type = data.get("type")
            review_subtype = data.get("review_subtype")
            if post_type in ["opinion", "review"]:
                if post_type == "review" and review_subtype not in ["text", "photo"]:
                    review_subtype = "text"
                if post_type == "opinion":
                    review_subtype = None
                return post_type, review_subtype
    except Exception as e:
        print("auto classify failed:", e)

    return _fallback_classify_post(title, platform)
@require_GET
def llm_model_list_api(request):
    return JsonResponse(
        {
            "count": len(LLM_MODELS),
            "results": LLM_MODELS,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
@require_GET
def my_clinic_ids_api(request):
    """
    Return distinct clinic IDs where the current user has posts within recent months.
    Query params:
      - months: int (default 3)
    """
    user = request.user
    if not user or not user.is_authenticated:
        header_session_key = request.headers.get("X-Sessionid")
        if header_session_key:
            try:
                s = Session.objects.get(
                    session_key=header_session_key,
                    expire_date__gte=timezone.now(),
                )
                uid = s.get_decoded().get("_auth_user_id")
                if uid:
                    UserModel = get_user_model()
                    user = UserModel.objects.filter(pk=uid).first() or user
            except Session.DoesNotExist:
                pass
    if not user or not user.is_authenticated:
        return JsonResponse({"error": "not_authenticated"}, status=401)

    try:
        months = int(request.GET.get("months") or 3)
    except Exception:
        months = 3
    months = max(1, min(months, 24))
    cutoff = timezone.now() - timezone.timedelta(days=months * 30)

    qs = ClinicPost.objects.filter(assignee=user).filter(
        Q(published_at__gte=cutoff) | Q(published_at__isnull=True, updated_at__gte=cutoff)
    )
    clinic_ids = list(qs.values_list("clinic_id", flat=True).distinct())
    return JsonResponse({"results": clinic_ids}, status=200)


class FavoriteClinicView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = FavoriteClinic.objects.filter(user=request.user)
        fallback = (request.GET.get("fallback") or "").strip().lower()
        favorites = FavoriteClinicSerializer(qs, many=True).data
        if qs.exists() and fallback != "assignee":
            return Response(favorites, status=status.HTTP_200_OK)

        if fallback == "assignee":
            assignees = (
                ClinicAssignee.objects
                .filter(user=request.user, is_active=True)
                .select_related("clinic")
            )
            assignee_data = [
                {
                    "clinic_id": a.clinic_id,
                    "clinic_name": a.clinic.name if a.clinic else "",
                    "created_at": None,
                }
                for a in assignees
            ]
            combined = {item["clinic_id"]: item for item in favorites}
            for item in assignee_data:
                combined.setdefault(item["clinic_id"], item)
            return Response(list(combined.values()), status=status.HTTP_200_OK)

        return Response(favorites, status=status.HTTP_200_OK)

    def post(self, request):
        clinic_id = request.data.get("clinic_id")
        clinic = get_object_or_404(ClinicGuide, id=clinic_id)

        FavoriteClinic.objects.get_or_create(
            user=request.user,
            clinic=clinic
        )
        return Response({"ok": True}, status=status.HTTP_200_OK)

    def delete(self, request, clinic_id):
        FavoriteClinic.objects.filter(
            user=request.user,
            clinic_id=clinic_id
        ).delete()
        return Response({"ok": True}, status=status.HTTP_200_OK)
    
class ClinicPostListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, clinic_id):
        """
        GET /api/data/clinics/<clinic_id>/posts/?type=opinion&platform=naver&q=검색어
        """
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)

        post_type = request.GET.get("type", "opinion")
        platform = request.GET.get("platform", "all")
        q = (request.GET.get("q") or "").strip()
        month = request.GET.get("month")  # "2026-01"
        assignee = request.GET.get("assignee")

        qs = ClinicPost.objects.filter(clinic=clinic)
    
        assignee_mode, assignee_id = _parse_assignee_param(assignee)
        if assignee_mode == "invalid":
            return Response({"message": "invalid assignee"}, status=status.HTTP_400_BAD_REQUEST)
        if assignee_mode == "me":
            if not request.user or not request.user.is_authenticated:
                return Response({"message": "authentication required for assignee=me"}, status=status.HTTP_401_UNAUTHORIZED)
            qs = qs.filter(assignee=request.user)
        elif assignee_mode == "id":
            qs = qs.filter(assignee_id=assignee_id)

        if month:
            try:
                year, m = map(int, month.split("-"))
                # 월 필터는 "수정일(updated_at)"이 아니라 실제 게시 시점 기준으로 본다.
                # published_at이 있으면 그 값을 우선, 없으면 created_at으로 폴백.
                qs = qs.filter(
                    Q(published_at__year=year, published_at__month=m) |
                    Q(published_at__isnull=True, created_at__year=year, created_at__month=m)
                )
            except ValueError:
                pass

        if post_type in ["opinion", "review"]:
            qs = qs.filter(type=post_type)

        if platform and platform != "all":
            qs = qs.filter(platform=platform)

        if q:
            qs = qs.filter(title__icontains=q)

        data = ClinicPostSerializer(qs[:300], many=True, context={"request": request}).data
        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request, clinic_id):
        """
        POST /api/data/clinics/<clinic_id>/posts/
        body:
        {
          "type": "opinion",
          "platform": "naver",
          "title": "...",
          "url": "...",
          "views": 0,
          "comments": 0,
          "status": "normal"
        }
        """
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)

        payload = request.data.copy() if hasattr(request.data, "copy") else (request.data or {})
        payload["clinic"] = clinic.id  # serializer에서 바로 쓰진 않지만 체크용

        post_type = payload.get("type")
        platform = payload.get("platform")
        auto_classify = _parse_bool(payload.get("auto_classify"))

        if not platform:
            return Response({"message": "platform required"}, status=status.HTTP_400_BAD_REQUEST)

        title = (payload.get("title") or "").strip()
        url = (payload.get("url") or "").strip()
        account = (payload.get("account") or "").strip()
        account_password = (payload.get("account_password") or "").strip()
        memo = (payload.get("memo") or "").strip()
        doctor_name = (payload.get("doctor_name") or "").strip()
        message_type = (payload.get("message_type") or "").strip()

        if not url:
            return Response({"message": "url required"}, status=status.HTTP_400_BAD_REQUEST)

        is_message_like = (
            message_type in {"prev_opinion", "comment_work"}
            or title == "쪽지 작업"
            or memo.startswith("쪽지구분:")
        )
        if is_message_like:
            return Response(
                {"message": "쪽지 작성 데이터는 게시글이 아니라 쪽지 API(/message-logs/)로 저장해야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not title:
            title = "미제목"

        review_subtype = payload.get("review_subtype")
        opinion_subtype = payload.get("opinion_subtype")
        model = payload.get("model") or "gpt-5-mini"

        if auto_classify or post_type not in ["opinion", "review"]:
            post_type, review_subtype = classify_post_type_and_subtype(
                title=title,
                platform=platform,
                url=url,
                model=model,
            )

        if post_type not in ["opinion", "review"]:
            return Response({"message": "type must be opinion|review"}, status=status.HTTP_400_BAD_REQUEST)

        if post_type == "review" and review_subtype not in ["text", "photo", "consultation"]:
            _, review_subtype = _fallback_classify_post(title, platform)
        if post_type == "opinion" and opinion_subtype not in ["concern", "hand", "foot"]:
            opinion_subtype = None

        assignee_id = payload.get("assignee") or request.user.id

        obj = ClinicPost.objects.create(
            clinic=clinic,
            type=post_type,
            review_subtype=review_subtype if post_type == "review" else None,
            opinion_subtype=opinion_subtype if post_type == "opinion" else None,
            platform=platform,
            title=title,
            url=url,
            account=account,
            account_password=account_password,
            memo=memo,
            doctor_name=doctor_name,
            views=int(payload.get("views") or 0),
            comments=int(payload.get("comments") or 0),
            message_count=int(payload.get("message_count") or 0),
            status=payload.get("status") or "normal",
            assignee_id=assignee_id,
            published_at=payload.get("published_at") or timezone.now(),
        )
        photos = request.FILES.getlist("photos")
        for f in photos:
            ClinicPostPhoto.objects.create(post=obj, image=f)

        return Response(ClinicPostSerializer(obj, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ClinicCommentBundleListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        qs = ClinicCommentBundle.objects.filter(clinic=clinic)
        data = ClinicCommentBundleSerializer(qs[:300], many=True, context={"request": request}).data
        for row in data:
            post = _find_clinic_post_by_url(clinic, row.get("url"))
            row["post_id"] = post.id if post else None
        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        raw_urls = request.data.get("comment_urls")
        try:
            parsed_urls = json.loads(raw_urls) if isinstance(raw_urls, str) else raw_urls
        except (TypeError, ValueError):
            parsed_urls = []
        if not isinstance(parsed_urls, list):
            parsed_urls = []

        urls = []
        for row in parsed_urls:
            if isinstance(row, dict):
                value = str(row.get("url") or "").strip()
            else:
                value = str(row or "").strip()
            if value:
                urls.append(value)

        images = request.FILES.getlist("comment_images")
        if not urls or not images:
            return Response({"message": "comment_urls and comment_images required"}, status=status.HTTP_400_BAD_REQUEST)

        invalid_urls = [u for u in urls if not _clinic_has_post_url(clinic, u)]
        if invalid_urls:
            return Response(
                {"message": "게시글 리스트에 없는 URL은 댓글로 저장할 수 없습니다.", "invalid_urls": invalid_urls},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for idx, url in enumerate(urls):
            if idx >= len(images):
                break
            created.append(
                ClinicCommentBundle.objects.create(
                    clinic=clinic,
                    created_by=request.user,
                    url=url,
                    image=images[idx],
                )
            )

        data = ClinicCommentBundleSerializer(created, many=True, context={"request": request}).data
        return Response({"ok": True, "count": len(created), "results": data}, status=status.HTTP_201_CREATED)


class ClinicMessageLogListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        qs = ClinicMessageLog.objects.filter(clinic=clinic)
        data = ClinicMessageLogSerializer(qs[:300], many=True, context={"request": request}).data
        for row in data:
            post = _find_clinic_post_by_url(clinic, row.get("url"))
            row["post_id"] = post.id if post else None
        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        url = str(request.data.get("url") or "").strip()
        platform = str(request.data.get("platform") or "").strip()
        message_type = str(request.data.get("message_type") or "").strip()

        try:
            message_count = int(request.data.get("message_count") or 0)
        except (TypeError, ValueError):
            message_count = 0
        message_count = max(0, message_count)

        if not url:
            return Response({"message": "url required"}, status=status.HTTP_400_BAD_REQUEST)
        matched_posts = _get_clinic_posts_by_url(clinic, url)
        if not matched_posts:
            return Response({"message": "게시글 리스트에 없는 URL은 쪽지로 저장할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        if message_type not in {"prev_opinion", "comment_work"}:
            return Response({"message": "valid message_type required"}, status=status.HTTP_400_BAD_REQUEST)
        if message_count < 1:
            return Response({"message": "쪽지수량은 1 이상이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        obj = ClinicMessageLog.objects.create(
            clinic=clinic,
            created_by=request.user,
            url=url,
            platform=platform,
            message_type=message_type,
            message_count=message_count,
        )
        for matched_post in matched_posts:
            matched_post.message_count = int(matched_post.message_count or 0) + int(message_count or 0)
            matched_post.save(update_fields=["message_count", "updated_at"])
        data = ClinicMessageLogSerializer(obj, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)
    
class ClinicAssigneeListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)

        qs = (
            ClinicAssignee.objects
            .filter(clinic=clinic, is_active=True)
            .select_related("user")
        )

        data = [
            {
                "id": ca.user.id,
                "name": ca.user.get_full_name() or ca.user.username,
            }
            for ca in qs
        ]

        return Response(data)


class ClinicNoticeListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        qs = ClinicNotice.objects.filter(clinic=clinic)
        rows = list(qs[:300])
        data = ClinicNoticeSerializer(rows, many=True, context={"request": request}).data
        ids = [row.id for row in rows]
        read_ids = set(
            ClinicNoticeRead.objects
            .filter(user=request.user, notice_id__in=ids)
            .values_list("notice_id", flat=True)
        )
        for item in data:
            item["is_new"] = int(item.get("id") or 0) not in read_ids
        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request, clinic_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        title = str(request.data.get("title") or "").strip()
        content = str(request.data.get("content") or "").strip()
        is_pinned = _parse_bool(request.data.get("is_pinned"))

        if not title and not content:
            return Response({"message": "title or content required"}, status=status.HTTP_400_BAD_REQUEST)

        obj = ClinicNotice.objects.create(
            clinic=clinic,
            created_by=request.user,
            title=title,
            content=content,
            is_pinned=is_pinned,
        )
        data = ClinicNoticeSerializer(obj, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class ClinicNoticeDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, clinic_id, notice_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        notice = get_object_or_404(ClinicNotice, id=notice_id, clinic=clinic)

        payload = request.data or {}
        updated_fields = []

        if "title" in payload:
            notice.title = str(payload.get("title") or "").strip()
            updated_fields.append("title")

        if "content" in payload:
            notice.content = str(payload.get("content") or "").strip()
            updated_fields.append("content")

        if "is_pinned" in payload:
            notice.is_pinned = _parse_bool(payload.get("is_pinned"))
            updated_fields.append("is_pinned")

        if not notice.title and not notice.content:
            return Response({"message": "title or content required"}, status=status.HTTP_400_BAD_REQUEST)

        if updated_fields:
            notice.save(update_fields=[*set(updated_fields), "updated_at"])

        data = ClinicNoticeSerializer(notice, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, clinic_id, notice_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        notice = get_object_or_404(ClinicNotice, id=notice_id, clinic=clinic)
        notice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClinicNoticeReadView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, clinic_id, notice_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        notice = get_object_or_404(ClinicNotice, id=notice_id, clinic=clinic)
        ClinicNoticeRead.objects.update_or_create(
            notice=notice,
            user=request.user,
            defaults={},
        )
        return Response({"ok": True, "notice_id": notice.id}, status=status.HTTP_200_OK)


class GlobalNoticeListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = GlobalNotice.objects.all()

        pinned_only = _parse_bool(request.GET.get("pinned_only"))
        unread_only = _parse_bool(request.GET.get("unread_only"))
        limit_raw = request.GET.get("limit")

        if pinned_only:
            qs = qs.filter(is_pinned=True)

        rows = list(qs[:300])
        data = GlobalNoticeSerializer(rows, many=True, context={"request": request}).data
        is_manager = _can_manage_global_notice(request.user)
        author_map = {row.id: row.created_by_id for row in rows}
        ids = [row.id for row in rows]
        read_ids = set(
            GlobalNoticeRead.objects
            .filter(user=request.user, notice_id__in=ids)
            .values_list("notice_id", flat=True)
        )
        for item in data:
            item_id = int(item.get("id") or 0)
            is_author = bool(author_map.get(item_id) and author_map.get(item_id) == request.user.id)
            item["is_new"] = item_id not in read_ids
            item["can_edit"] = bool(is_manager or is_author)
            item["can_delete"] = bool(is_manager or is_author)

        if unread_only:
            data = [item for item in data if item.get("is_new")]

        if limit_raw:
            try:
                limit = max(1, min(300, int(limit_raw)))
            except ValueError:
                limit = 50
            data = data[:limit]

        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request):
        if not _can_manage_global_notice(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        title = str(request.data.get("title") or "").strip()
        content = str(request.data.get("content") or "").strip()
        is_pinned = _parse_bool(request.data.get("is_pinned"))

        if not title and not content:
            return Response({"message": "title or content required"}, status=status.HTTP_400_BAD_REQUEST)

        obj = GlobalNotice.objects.create(
            created_by=request.user,
            title=title,
            content=content,
            is_pinned=is_pinned,
        )
        data = GlobalNoticeSerializer(obj, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class GlobalNoticeDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, notice_id):
        notice = get_object_or_404(GlobalNotice, id=notice_id)
        is_author = bool(notice.created_by_id and notice.created_by_id == request.user.id)
        if not (_can_manage_global_notice(request.user) or is_author):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}
        updated_fields = []

        if "title" in payload:
            notice.title = str(payload.get("title") or "").strip()
            updated_fields.append("title")

        if "content" in payload:
            notice.content = str(payload.get("content") or "").strip()
            updated_fields.append("content")

        if "is_pinned" in payload:
            notice.is_pinned = _parse_bool(payload.get("is_pinned"))
            updated_fields.append("is_pinned")

        if not notice.title and not notice.content:
            return Response({"message": "title or content required"}, status=status.HTTP_400_BAD_REQUEST)

        if updated_fields:
            notice.save(update_fields=[*set(updated_fields), "updated_at"])

        data = GlobalNoticeSerializer(notice, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, notice_id):
        notice = get_object_or_404(GlobalNotice, id=notice_id)
        is_author = bool(notice.created_by_id and notice.created_by_id == request.user.id)
        if not (_can_manage_global_notice(request.user) or is_author):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        notice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GlobalNoticeReadView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, notice_id):
        notice = get_object_or_404(GlobalNotice, id=notice_id)
        confirmation_text = str(request.data.get("confirmation_text") or "").strip()
        if notice.is_pinned and confirmation_text != "확인했습니다":
            return Response(
                {"message": "confirmation_text must be '확인했습니다'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        GlobalNoticeRead.objects.update_or_create(
            notice=notice,
            user=request.user,
            defaults={},
        )
        return Response({"ok": True, "notice_id": notice.id}, status=status.HTTP_200_OK)


class ClinicPostDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, clinic_id, post_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        post = get_object_or_404(ClinicPost, id=post_id, clinic=clinic)

        payload = request.data or {}
        updated_fields = []

        if "message_count" in payload:
            post.message_count = int(payload.get("message_count") or 0)
            updated_fields.append("message_count")

        if "views" in payload:
            post.views = int(payload.get("views") or 0)
            updated_fields.append("views")

        if "comments" in payload:
            post.comments = int(payload.get("comments") or 0)
            updated_fields.append("comments")

        if "title" in payload:
            post.title = (payload.get("title") or "").strip()
            updated_fields.append("title")

        if "url" in payload:
            post.url = (payload.get("url") or "").strip()
            updated_fields.append("url")

        if "account" in payload:
            post.account = (payload.get("account") or "").strip()
            updated_fields.append("account")

        if "account_password" in payload:
            post.account_password = (payload.get("account_password") or "").strip()
            updated_fields.append("account_password")

        if "memo" in payload:
            post.memo = (payload.get("memo") or "").strip()
            updated_fields.append("memo")

        if "doctor_name" in payload:
            post.doctor_name = (payload.get("doctor_name") or "").strip()
            updated_fields.append("doctor_name")

        if "platform" in payload:
            post.platform = payload.get("platform")
            updated_fields.append("platform")

        if "type" in payload:
            post_type = payload.get("type")
            if post_type in ["opinion", "review"]:
                post.type = post_type
                updated_fields.append("type")

        if "review_subtype" in payload or post.type == "review":
            review_subtype = payload.get("review_subtype") or post.review_subtype
            if post.type == "opinion":
                if post.review_subtype is not None:
                    post.review_subtype = None
                    updated_fields.append("review_subtype")
            else:
                if review_subtype not in ["text", "photo", "consultation"]:
                    _, review_subtype = _fallback_classify_post(post.title, post.platform)
                if post.review_subtype != review_subtype:
                    post.review_subtype = review_subtype
                    updated_fields.append("review_subtype")

        if "opinion_subtype" in payload or post.type == "opinion":
            opinion_subtype = payload.get("opinion_subtype") or post.opinion_subtype
            if post.type == "review":
                if post.opinion_subtype is not None:
                    post.opinion_subtype = None
                    updated_fields.append("opinion_subtype")
            else:
                if opinion_subtype not in ["concern", "hand", "foot"]:
                    opinion_subtype = None
                if post.opinion_subtype != opinion_subtype:
                    post.opinion_subtype = opinion_subtype
                    updated_fields.append("opinion_subtype")

        if "assignee" in payload:
            assignee_value = payload.get("assignee")
            if assignee_value in [None, ""]:
                post.assignee_id = None
            else:
                post.assignee_id = int(assignee_value)
            updated_fields.append("assignee_id")

        if "published_at" in payload:
            raw = payload.get("published_at")
            parsed = None
            if isinstance(raw, str) and len(raw) == 10:
                try:
                    parsed = datetime.combine(date.fromisoformat(raw), time.min)
                except ValueError:
                    parsed = None
            elif isinstance(raw, datetime):
                parsed = raw
            if parsed:
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed)
                post.published_at = parsed
                updated_fields.append("published_at")

        if updated_fields:
            post.save(update_fields=[*set(updated_fields), "updated_at"])

        return Response(ClinicPostSerializer(post, context={"request": request}).data, status=status.HTTP_200_OK)

    def delete(self, request, clinic_id, post_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        post = get_object_or_404(ClinicPost, id=post_id, clinic=clinic)
        post.delete()
        return Response({"ok": True}, status=status.HTTP_200_OK)


class CalendarMemoListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            CalendarMemo.objects
            .filter(user=request.user)
            .exclude(platform=ATTENDANCE_MEMO_PLATFORM)
            .exclude(platform=VACATION_MEMO_PLATFORM)
            .exclude(platform=REVIEW_SCHEDULE_PLATFORM)
        )

        clinic_id = request.GET.get("clinic_id")
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)

        date_str = request.GET.get("date")
        month_str = request.GET.get("month")
        if date_str:
            parsed = parse_date(date_str)
            if parsed:
                qs = qs.filter(date=parsed)
        elif month_str:
            try:
                year, m = map(int, month_str.split("-"))
                qs = qs.filter(date__year=year, date__month=m)
            except ValueError:
                pass

        unread_only = _parse_bool(request.GET.get("unread"))
        if unread_only:
            qs = qs.filter(is_read=False)

        data = CalendarMemoSerializer(qs, many=True).data
        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request):
        payload = request.data or {}
        date_str = payload.get("date")
        parsed_date = parse_date(date_str) if date_str else None
        if not parsed_date:
            return Response({"message": "date required"}, status=status.HTTP_400_BAD_REQUEST)

        content = (payload.get("content") or "").strip()
        if not content:
            return Response({"message": "content required"}, status=status.HTTP_400_BAD_REQUEST)

        clinic = None
        clinic_id = payload.get("clinic_id")
        if clinic_id:
            clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)

        remind_at = _parse_datetime_value(payload.get("remind_at"))
        platform = (payload.get("platform") or "").strip()
        account = (payload.get("account") or "").strip()
        account_password = (payload.get("account_password") or "").strip()

        memo = CalendarMemo.objects.create(
            user=request.user,
            clinic=clinic,
            date=parsed_date,
            content=content,
            platform=platform,
            account=account,
            account_password=account_password,
            remind_at=remind_at,
            is_read=False,
        )

        return Response(CalendarMemoSerializer(memo).data, status=status.HTTP_201_CREATED)


class CalendarMemoDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, memo_id):
        memo = get_object_or_404(CalendarMemo, id=memo_id, user=request.user)
        payload = request.data or {}
        updated_fields = []

        if "content" in payload:
            memo.content = (payload.get("content") or "").strip()
            updated_fields.append("content")

        if "date" in payload:
            parsed = parse_date(payload.get("date") or "")
            if parsed:
                memo.date = parsed
                updated_fields.append("date")

        if "clinic_id" in payload:
            clinic_id = payload.get("clinic_id")
            if not clinic_id:
                memo.clinic = None
            else:
                memo.clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
            updated_fields.append("clinic")

        if "remind_at" in payload:
            remind_raw = payload.get("remind_at")
            parsed_remind = _parse_datetime_value(remind_raw) if remind_raw else None
            memo.remind_at = parsed_remind
            updated_fields.append("remind_at")
            # Re-scheduling a reminder should surface it again as unread.
            if parsed_remind is not None:
                memo.is_read = False
                updated_fields.append("is_read")

        if "platform" in payload:
            memo.platform = (payload.get("platform") or "").strip()
            updated_fields.append("platform")

        if "account" in payload:
            memo.account = (payload.get("account") or "").strip()
            updated_fields.append("account")

        if "account_password" in payload:
            memo.account_password = (payload.get("account_password") or "").strip()
            updated_fields.append("account_password")

        if "is_read" in payload:
            memo.is_read = _parse_bool(payload.get("is_read"))
            updated_fields.append("is_read")

        if updated_fields:
            memo.save(update_fields=[*set(updated_fields), "updated_at"])

        return Response(CalendarMemoSerializer(memo).data, status=status.HTTP_200_OK)

    def delete(self, request, memo_id):
        memo = get_object_or_404(CalendarMemo, id=memo_id, user=request.user)
        memo.delete()
        return Response({"ok": True}, status=status.HTTP_200_OK)


class ReviewScheduleListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ReviewSchedule.objects.filter(user=request.user)

        clinic_id = request.GET.get("clinic_id")
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)

        date_str = request.GET.get("date")
        month_str = request.GET.get("month")
        if date_str:
            parsed = parse_date(date_str)
            if parsed:
                qs = qs.filter(date=parsed)
        elif month_str:
            try:
                year, m = map(int, month_str.split("-"))
                qs = qs.filter(date__year=year, date__month=m)
            except ValueError:
                pass

        unread_only = _parse_bool(request.GET.get("unread"))
        if unread_only:
            qs = qs.filter(is_read=False)

        data = ReviewScheduleSerializer(qs, many=True).data
        return Response({"count": qs.count(), "results": data}, status=status.HTTP_200_OK)

    def post(self, request):
        payload = request.data or {}
        date_str = payload.get("date")
        parsed_date = parse_date(date_str) if date_str else None
        if not parsed_date:
            return Response({"message": "date required"}, status=status.HTTP_400_BAD_REQUEST)

        label = (payload.get("label") or "").strip()
        detail = (payload.get("detail") or "").strip()
        draft = (payload.get("draft") or "").strip()
        content = (payload.get("content") or "").strip()
        plan_id = (payload.get("plan_id") or "").strip()
        plan_title = (payload.get("plan_title") or "").strip()

        if content:
            parsed = _parse_review_schedule_content(content)
            if not label:
                label = parsed.get("label", "")
            if not detail:
                detail = parsed.get("detail", "")
            if not draft:
                draft = parsed.get("draft", "")
            if not plan_id:
                plan_id = parsed.get("plan_id", "")
            if not plan_title:
                plan_title = parsed.get("plan_title", "")

        if not label:
            return Response({"message": "label required"}, status=status.HTTP_400_BAD_REQUEST)
        if not detail:
            return Response({"message": "detail required"}, status=status.HTTP_400_BAD_REQUEST)
        if not plan_id:
            plan_id = uuid.uuid4().hex[:10]

        if not content:
            content = _build_review_schedule_content(
                plan_id=plan_id,
                label=label,
                detail=detail,
                draft=draft,
                plan_title=plan_title,
            )
        else:
            content = _build_review_schedule_content(
                plan_id=plan_id,
                label=label,
                detail=detail,
                draft=draft,
                plan_title=plan_title,
            )

        clinic = None
        clinic_id = payload.get("clinic_id")
        if clinic_id:
            clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)

        remind_at = _parse_datetime_value(payload.get("remind_at"))

        memo = ReviewSchedule.objects.create(
            user=request.user,
            clinic=clinic,
            date=parsed_date,
            plan_id=plan_id,
            plan_title=plan_title,
            label=label,
            detail=detail,
            draft=draft,
            account=((payload.get("account") or payload.get("platform_account")) or "").strip(),
            account_password=((payload.get("account_password") or payload.get("platform_password")) or "").strip(),
            remind_at=remind_at,
            is_read=False,
        )
        return Response(ReviewScheduleSerializer(memo).data, status=status.HTTP_201_CREATED)


class ReviewScheduleGenerateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        start_date_raw = payload.get("start_date")
        start_date = parse_date(start_date_raw) if start_date_raw else timezone.localdate()
        if not start_date:
            return Response({"message": "start_date invalid"}, status=status.HTTP_400_BAD_REQUEST)

        def _next_business_day(d):
            cur = d
            while cur.weekday() >= 5:  # 5: Saturday, 6: Sunday
                cur = cur + timedelta(days=1)
            return cur

        weeks_raw = payload.get("weeks", 4)
        try:
            weeks = int(weeks_raw)
        except (TypeError, ValueError):
            weeks = 4
        weeks = max(1, min(12, weeks))

        clinic = None
        clinic_id = payload.get("clinic_id")
        if clinic_id:
            clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)

        replace_existing = _parse_bool(payload.get("replace_existing"))
        if payload.get("replace_existing") is None:
            replace_existing = True

        start_date = _next_business_day(start_date)
        plan_id = str(payload.get("plan_id") or "").strip() or uuid.uuid4().hex[:10]

        if replace_existing:
            delete_qs = ReviewSchedule.objects.filter(user=request.user, date__gte=start_date)
            if clinic:
                delete_qs = delete_qs.filter(clinic=clinic)
            delete_qs.delete()

        fixed_plan = [
            (0, "여론 리뷰 작성", "여론/관심사 키워드 정리, 주제 선정"),
            (2, "발품/손품", "검색/커뮤니티 탐색 포인트 정리"),
            (4, "상담 후기", "상담 핵심 포인트 + Q&A 후기 작성"),
        ]
        weekly_plan = [(7 * i, "주단위 후기", f"{i}주차 후기 업로드/점검") for i in range(1, weeks + 1)]
        monthly_plan = [(30, "달단위 후기", "월간 성과 요약 + 다음달 개선안")]
        plan_rows = [*fixed_plan, *weekly_plan, *monthly_plan]

        created = []
        for offset_days, label, detail in plan_rows:
            target_date = _next_business_day(start_date + timedelta(days=offset_days))
            remind_at = timezone.make_aware(datetime.combine(target_date, time(hour=10, minute=0)))
            memo = ReviewSchedule.objects.create(
                user=request.user,
                clinic=clinic,
                date=target_date,
                plan_id=plan_id,
                plan_title=(payload.get("plan_title") or "").strip(),
                label=label,
                detail=detail,
                draft="",
                account=((payload.get("account") or payload.get("platform_account")) or "").strip(),
                account_password=((payload.get("account_password") or payload.get("platform_password")) or "").strip(),
                remind_at=remind_at,
                is_read=False,
            )
            created.append(memo)

        data = ReviewScheduleSerializer(created, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_201_CREATED)


class ReviewScheduleDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, schedule_id):
        memo = get_object_or_404(ReviewSchedule, id=schedule_id, user=request.user)
        payload = request.data or {}
        updated_fields = []

        if "date" in payload:
            parsed = parse_date(payload.get("date") or "")
            if parsed:
                memo.date = parsed
                updated_fields.append("date")

        next_plan_id = (payload.get("plan_id") or "").strip() or memo.plan_id or uuid.uuid4().hex[:10]
        next_label = (payload.get("label") or "").strip() or memo.label or ""
        next_detail = (payload.get("detail") or "").strip() or memo.detail or ""
        next_plan_title = (payload.get("plan_title") or "").strip() or memo.plan_title or ""
        next_draft = (payload.get("draft") or "").strip() or memo.draft or ""

        if "content" in payload:
            raw_content = (payload.get("content") or "").strip()
            parsed_content = _parse_review_schedule_content(raw_content)
            if parsed_content.get("label"):
                next_label = parsed_content.get("label") or next_label
            if parsed_content.get("detail"):
                next_detail = parsed_content.get("detail") or next_detail
            if parsed_content.get("draft"):
                next_draft = parsed_content.get("draft") or next_draft
            if parsed_content.get("plan_id"):
                next_plan_id = parsed_content.get("plan_id") or next_plan_id
            if parsed_content.get("plan_title"):
                next_plan_title = parsed_content.get("plan_title") or next_plan_title

        if "account" in payload:
            memo.account = (payload.get("account") or "").strip()
            updated_fields.append("account")

        if "account_password" in payload:
            memo.account_password = (payload.get("account_password") or "").strip()
            updated_fields.append("account_password")

        if (
            "content" in payload
            or "label" in payload
            or "detail" in payload
            or "draft" in payload
            or "plan_id" in payload
            or "plan_title" in payload
        ) and next_label and next_detail:
            memo.plan_id = next_plan_id
            memo.label = next_label
            memo.detail = next_detail
            memo.draft = next_draft
            memo.plan_title = next_plan_title
            updated_fields.extend(["plan_id", "label", "detail", "draft", "plan_title"])

        if "remind_at" in payload:
            remind_raw = payload.get("remind_at")
            memo.remind_at = _parse_datetime_value(remind_raw) if remind_raw else None
            updated_fields.append("remind_at")

        if "is_read" in payload:
            memo.is_read = _parse_bool(payload.get("is_read"))
            updated_fields.append("is_read")

        if updated_fields:
            memo.save(update_fields=[*set(updated_fields), "updated_at"])
        return Response(ReviewScheduleSerializer(memo).data, status=status.HTTP_200_OK)

    def delete(self, request, schedule_id):
        memo = get_object_or_404(ReviewSchedule, id=schedule_id, user=request.user)
        memo.delete()
        return Response({"ok": True}, status=status.HTTP_200_OK)


class NotificationListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit_raw = request.GET.get("limit") or "20"
        try:
            limit = max(1, min(100, int(limit_raw)))
        except ValueError:
            limit = 20

        now = timezone.now()
        user_role = normalize_user_role(request.user)
        is_attendance_admin = bool(
            request.user.is_superuser
            or user_role in {"admin", "ceo", "leader"}
            or get_user_permission(request.user, SystemPermission.KEY_ATTENDANCE_REQUESTS)
        )
        is_vacation_admin = bool(request.user.is_superuser or user_role in {"admin", "ceo", "leader"})
        memo_qs = (
            CalendarMemo.objects
            .filter(user=request.user, remind_at__isnull=False, remind_at__lte=now)
            .order_by("-remind_at")
        )
        schedule_qs = (
            ReviewSchedule.objects
            .filter(user=request.user, remind_at__isnull=False, remind_at__lte=now)
            .order_by("-remind_at")
        )
        attendance_qs = AttendanceCorrectionRequest.objects.none()
        if is_attendance_admin:
            attendance_qs = AttendanceCorrectionRequest.objects.filter(status="pending").select_related("user", "user__profile").order_by("-created_at")
        vacation_q = Q(user=request.user, status__in=["approved", "rejected"])
        if is_vacation_admin:
            vacation_q |= Q(status="pending")
        vacation_qs = VacationRequest.objects.filter(vacation_q).select_related("user", "user__profile").order_by("-updated_at", "-created_at")

        def _attendance_rows(qs):
            rows = []
            tz = timezone.get_current_timezone()
            for req in qs[:limit]:
                profile = getattr(req.user, "profile", None)
                requester = getattr(profile, "name", None) or req.user.get_full_name() or req.user.username
                in_txt = req.requested_check_in_at.astimezone(tz).strftime("%Y-%m-%d %H:%M") if req.requested_check_in_at else "-"
                out_txt = req.requested_check_out_at.astimezone(tz).strftime("%Y-%m-%d %H:%M") if req.requested_check_out_at else "-"
                rows.append(
                    {
                        "id": req.id,
                        "date": req.work_date.isoformat(),
                        "content": (
                            f"[근태 정정요청] {requester}\n"
                            f"대상일: {req.work_date}\n"
                            f"요청 출근: {in_txt} / 요청 퇴근: {out_txt}\n"
                            f"사유: {req.reason}"
                        ),
                        "platform": ATTENDANCE_MEMO_PLATFORM,
                        "platform_label": "근태 정정요청",
                        "remind_at": req.created_at,
                        "is_read": False,
                        "created_at": req.created_at,
                        "updated_at": req.updated_at,
                    }
                )
            return rows

        def _vacation_rows(qs):
            rows = []
            for req in qs[:limit]:
                profile = getattr(req.user, "profile", None)
                requester = getattr(profile, "name", None) or req.user.get_full_name() or req.user.username
                period = req.start_date if req.start_date == req.end_date else f"{req.start_date} ~ {req.end_date}"
                if req.status == "pending":
                    content = (
                        f"[휴가 신청] {requester}\n"
                        f"기간: {period}\n"
                        f"유형: {req.get_type_display()} / {req.days}일\n"
                        f"사유: {req.reason or '-'}"
                    )
                else:
                    result = "승인" if req.status == "approved" else "반려"
                    content = (
                        f"[휴가 {result}] {req.get_type_display()}\n"
                        f"기간: {period}\n"
                        f"사용일수: {req.days}일\n"
                        f"비고: {req.review_note or '-'}"
                    )
                rows.append(
                    {
                        "id": req.id,
                        "date": req.start_date.isoformat(),
                        "content": content,
                        "platform": VACATION_MEMO_PLATFORM,
                        "platform_label": "휴가 신청",
                        "remind_at": req.updated_at or req.created_at,
                        "is_read": req.status != "pending",
                        "created_at": req.created_at,
                        "updated_at": req.updated_at,
                    }
                )
            return rows

        center = (request.GET.get("center") or "").strip().lower()
        if center == "attendance":
            data = _attendance_rows(attendance_qs)
            unread_count = sum(1 for row in data if not bool(row.get("is_read")))
            return Response({"count": attendance_qs.count(), "unread_count": unread_count, "results": data}, status=status.HTTP_200_OK)
        elif center == "vacation":
            data = _vacation_rows(vacation_qs)
            unread_count = sum(1 for row in data if not bool(row.get("is_read")))
            return Response({"count": vacation_qs.count(), "unread_count": unread_count, "results": data}, status=status.HTTP_200_OK)
        elif center == "schedule":
            qs = schedule_qs
            unread_count = qs.filter(is_read=False).count()
            data = ReviewScheduleSerializer(qs[:limit], many=True).data
            return Response({"count": qs.count(), "unread_count": unread_count, "results": data}, status=status.HTTP_200_OK)
        elif center == "system":
            attendance_rows = _attendance_rows(attendance_qs)
            vacation_rows = _vacation_rows(vacation_qs)
            data = [*attendance_rows, *vacation_rows]
            data.sort(key=lambda x: str(x.get("remind_at") or x.get("created_at") or ""), reverse=True)
            data = data[:limit]
            unread_count = sum(1 for row in data if not bool(row.get("is_read")))
            return Response({"count": len(data), "unread_count": unread_count, "results": data}, status=status.HTTP_200_OK)
        elif center == "memo":
            qs = (
                memo_qs.exclude(platform=ATTENDANCE_MEMO_PLATFORM)
                .exclude(platform=VACATION_MEMO_PLATFORM)
                .exclude(platform=REVIEW_SCHEDULE_PLATFORM)
            )
            unread_count = qs.filter(is_read=False).count()
            data = CalendarMemoSerializer(qs[:limit], many=True).data
            return Response({"count": qs.count(), "unread_count": unread_count, "results": data}, status=status.HTTP_200_OK)

        memo_rows = CalendarMemoSerializer(
            memo_qs.exclude(platform=REVIEW_SCHEDULE_PLATFORM)[:limit],
            many=True,
        ).data
        attendance_rows = _attendance_rows(attendance_qs)
        vacation_rows = _vacation_rows(vacation_qs)
        schedule_rows = ReviewScheduleSerializer(schedule_qs[:limit], many=True).data
        all_rows = [*memo_rows, *attendance_rows, *vacation_rows, *schedule_rows]
        all_rows.sort(key=lambda x: str(x.get("remind_at") or x.get("created_at") or ""), reverse=True)
        all_rows = all_rows[:limit]
        unread_count = sum(1 for row in all_rows if not bool(row.get("is_read")))
        return Response(
            {"count": len(all_rows), "unread_count": unread_count, "results": all_rows},
            status=status.HTTP_200_OK,
        )
