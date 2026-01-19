from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils import timezone
import json
import re

from apps.ml.services.llm.registry import LLM_MODELS
from apps.ml.services.llm_service import generate_review_with_prompt
from apps.data.models import ClinicGuide, ClinicDoctor, ClinicPrice, ClinicPost, ClinicPostPhoto

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.authentication import SessionAuthentication

from .models import FavoriteClinic, ClinicAssignee
from .serializers import FavoriteClinicSerializer, ClinicPostSerializer


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # CSRF 체크 완전히 비활성화

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


def _fallback_classify_post(title, platform):
    title = (title or "").lower()
    review_keywords = ["후기", "리뷰", "수술후기", "상담후기"]
    review_platforms = {"gangnam", "gn_jp", "babytok", "yeoshin", "seongyesa"}

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


class FavoriteClinicView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = FavoriteClinic.objects.filter(user=request.user)
        return Response(
            FavoriteClinicSerializer(qs, many=True).data,
            status=status.HTTP_200_OK
        )

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
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

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
    
        if assignee and assignee != "all":
            if assignee == "me":
                qs = qs.filter(assignee=request.user)
            else:
                qs = qs.filter(assignee_id=int(assignee))

        if month:
            try:
                year, m = map(int, month.split("-"))

                qs = qs.filter(
                    updated_at__year=year,
                    updated_at__month=m
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

        payload = request.data or {}
        payload["clinic"] = clinic.id  # serializer에서 바로 쓰진 않지만 체크용

        post_type = payload.get("type")
        platform = payload.get("platform")
        auto_classify = bool(payload.get("auto_classify"))

        if not platform:
            return Response({"message": "platform required"}, status=status.HTTP_400_BAD_REQUEST)

        title = (payload.get("title") or "").strip()
        url = (payload.get("url") or "").strip()

        if not url:
            return Response({"message": "url required"}, status=status.HTTP_400_BAD_REQUEST)

        if not title:
            title = "미제목"

        review_subtype = payload.get("review_subtype")
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

        if post_type == "review" and review_subtype not in ["text", "photo"]:
            _, review_subtype = _fallback_classify_post(title, platform)

        assignee_id = payload.get("assignee") or request.user.id

        obj = ClinicPost.objects.create(
            clinic=clinic,
            type=post_type,
            review_subtype=review_subtype if post_type == "review" else None,
            platform=platform,
            title=title,
            url=url,
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
    authentication_classes = [CsrfExemptSessionAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, clinic_id, post_id):
        clinic = get_object_or_404(ClinicGuide, id=clinic_id, is_active=True)
        post = get_object_or_404(ClinicPost, id=post_id, clinic=clinic)

        payload = request.data or {}
        updated = False

        if "message_count" in payload:
            post.message_count = int(payload.get("message_count") or 0)
            updated = True

        if "views" in payload:
            post.views = int(payload.get("views") or 0)
            updated = True

        if "comments" in payload:
            post.comments = int(payload.get("comments") or 0)
            updated = True

        if updated:
            post.save(update_fields=["message_count", "views", "comments", "updated_at"])

        return Response(ClinicPostSerializer(post, context={"request": request}).data, status=status.HTTP_200_OK)
