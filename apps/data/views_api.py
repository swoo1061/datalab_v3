from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime
from datetime import date, datetime, time
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
import json
import re

from apps.ml.services.llm.registry import LLM_MODELS
from apps.ml.services.llm_service import generate_review_with_prompt
from apps.data.models import ClinicGuide, ClinicDoctor, ClinicPrice, ClinicPost, ClinicPostPhoto, CalendarMemo

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, BaseAuthentication

from .models import FavoriteClinic, ClinicAssignee
from .serializers import FavoriteClinicSerializer, ClinicPostSerializer, CalendarMemoSerializer


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

        if not url:
            return Response({"message": "url required"}, status=status.HTTP_400_BAD_REQUEST)

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
        qs = CalendarMemo.objects.filter(user=request.user)

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
            memo.remind_at = _parse_datetime_value(remind_raw) if remind_raw else None
            updated_fields.append("remind_at")

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
        qs = (
            CalendarMemo.objects
            .filter(user=request.user, remind_at__isnull=False, remind_at__lte=now)
            .order_by("-remind_at")
        )
        unread_count = qs.filter(is_read=False).count()
        data = CalendarMemoSerializer(qs[:limit], many=True).data
        return Response(
            {"count": qs.count(), "unread_count": unread_count, "results": data},
            status=status.HTTP_200_OK,
        )
