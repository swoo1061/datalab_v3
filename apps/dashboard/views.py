"""
대시보드 뷰 - 리뷰 생성 시스템 v2
"""


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from .decorators import dashboard_required
from apps.ml.services.usage_logger import log_llm_usage
import json
import re
from collections import Counter
from urllib.parse import urlparse

from apps.ml.services.llm.registry import LLM_MODELS

import csv
from openpyxl import Workbook
from django.db import models
from datetime import datetime, timedelta
import calendar
from django.utils import timezone
from django.db.models import Sum, Count, Min, Max, Q
from django.db.models.functions import TruncDate, TruncMonth, Coalesce

from apps.data.models import (
    Review, Campaign, ImageAsset,
    Persona, CafeProfile, ClinicGuide, GeneratedReview, ContentTypeProfile, LLMUsageLog, ClinicDoctor, ClinicPrice, AccessLog,
    ClinicPost, CrawledPostContent
)
from apps.data.models_worklog import DailyWorkLog
from accounts.models import UserProfile
from apps.ml.services.clinic_normalizer import normalize_clinic_payload
from apps.ml.services.clinic_md_llm import parse_clinic_md_with_llm
from apps.ml.services.llm_service import (
    generate_review,
    generate_review_advanced,
    generate_review_with_prompt_enforced,
    generate_title_suggestions,
    apply_review_type_guard,
)
from apps.ml.services.prompt_generator import build_review_prompt, build_prompt_from_models, build_ft_prompt_from_models
from apps.ml.services.clinic_parser import parse_clinic_content
from apps.data.permissions import can_access_web_dashboard
from .services.monthly_report_layouts import get_monthly_report_layout

# =====================================================
# 기존 뷰 (호환성 유지)
# =====================================================

def _model_display_map():
    mapping = {}
    try:
        for item in LLM_MODELS:
            key = item.get("key")
            label = item.get("label")
            if key and label:
                mapping[key] = label
    except Exception:
        pass
    return mapping


def _get_model_display(model_id: str) -> str:
    if not model_id:
        return "-"
    mapping = _model_display_map()
    return mapping.get(model_id, model_id)


def _is_internal_user(user):
    return can_access_web_dashboard(user)

@dashboard_required
def is_staff(user):
    return user.groups.filter(name='staff').exists() or user.is_superuser


def _parse_date_param(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _get_usage_range(request, default_days=30):
    today = timezone.now().date()
    start = _parse_date_param(request.GET.get("start")) or (today - timedelta(days=default_days - 1))
    end = _parse_date_param(request.GET.get("end")) or today
    if start > end:
        start, end = end, start
    return start, end


def _get_keywords_used(cafe):
    if not cafe:
        return []
    try:
        return list(cafe.required_keywords or [])
    except Exception:
        return []


def _build_persona_text(persona):
    if not persona:
        return ""
    if isinstance(persona, str):
        return persona.strip()
    if isinstance(persona, dict):
        parts = []
        for key in ("age", "gender", "job", "personality", "tone", "experience"):
            value = persona.get(key)
            if value:
                parts.append(str(value))
        return ", ".join(parts)
    return ""

@dashboard_required
def index(request):
    """대시보드 홈"""
    today = timezone.now().date()
    total_reviews = Review.objects.count()
    generated_count = GeneratedReview.objects.count()
    clinics_count = ClinicGuide.objects.filter(is_active=True).count()

    recent_generated = GeneratedReview.objects.all()[:5]
    campaigns = Campaign.objects.all()[:6]
    recent_posts = ClinicPost.objects.select_related("clinic", "assignee").order_by("-created_at")[:6]
    recent_llm = LLMUsageLog.objects.select_related("user").order_by("-created_at")[:8]

    today_posts_qs = ClinicPost.objects.filter(created_at__date=today)
    today_posts = today_posts_qs.count()
    today_opinion = today_posts_qs.filter(type="opinion").count()
    today_review = today_posts_qs.filter(type="review").count()

    llm_today = LLMUsageLog.objects.filter(created_at__date=today).aggregate(
        calls=Count("id"),
        tokens=Sum("total_tokens"),
        cost_krw=Sum("cost_krw"),
    )

    context = {
        "total_reviews": total_reviews,
        "generated_reviews": generated_count,
        "clinics_count": clinics_count,
        "model_version": "v2.0",
        "campaigns": campaigns,
        "recent_generated": recent_generated,
        "recent_posts": recent_posts,
        "recent_llm": recent_llm,
        "today": today,
        "today_posts": today_posts,
        "today_opinion": today_opinion,
        "today_review": today_review,
        "today_generated": GeneratedReview.objects.filter(created_at__date=today).count(),
        "today_llm_calls": llm_today.get("calls") or 0,
        "today_llm_tokens": llm_today.get("tokens") or 0,
        "today_llm_cost": llm_today.get("cost_krw") or 0,
    }
    for review in recent_generated:
        review.model_display = _get_model_display(review.model_used)
    for log in recent_llm:
        log.model_display = _get_model_display(log.model)
    return render(request, "dashboard/index.html", context)


@login_required
def monthly_report(request):
    today = timezone.localdate()
    is_internal_user = _is_internal_user(request.user)
    month_str = (request.GET.get("month") or today.strftime("%Y-%m")).strip()
    clinic_id = (request.GET.get("clinic") or "").strip()
    clear_clinic = (request.GET.get("clear_clinic") or "").strip() == "1"
    session_key = "monthly_report_clinic_id"

    # 원장(외부) 계정은 본인 병원만 강제 적용
    if not is_internal_user:
        assigned = (
            ClinicGuide.objects.filter(
                assignees__user=request.user,
                assignees__is_active=True,
                is_active=True,
            )
            .order_by("name")
            .first()
        )
        clinic_id = str(assigned.id) if assigned else ""
    else:
        # 내부 사용자: 월간보고서 첫 진입은 항상 병원 선택 화면으로 시작
        if clear_clinic:
            request.session.pop(session_key, None)
        if clinic_id and clinic_id.isdigit():
            request.session[session_key] = int(clinic_id)
        elif not clinic_id:
            clinic_id = ""

    try:
        month_start = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
    except Exception:
        month_start = today.replace(day=1)
        month_str = month_start.strftime("%Y-%m")

    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1, day=1)
    if month_start.month == 1:
        prev_month_start = month_start.replace(year=month_start.year - 1, month=12, day=1)
    else:
        prev_month_start = month_start.replace(month=month_start.month - 1, day=1)

    clinics = ClinicGuide.objects.filter(is_active=True).order_by("name")
    selected_clinic = ClinicGuide.objects.filter(pk=clinic_id).first() if clinic_id else None

    base_post_qs = ClinicPost.objects.select_related("clinic", "assignee", "assignee__profile").filter(
        created_at__date__gte=month_start,
        created_at__date__lt=next_month,
    )
    if selected_clinic:
        post_qs = base_post_qs.filter(clinic=selected_clinic)
    else:
        post_qs = ClinicPost.objects.none()

    layout = get_monthly_report_layout(selected_clinic.name if selected_clinic else None)

    # 병원 선택 카드(내부 사용자용)
    clinic_picker_rows = list(
        clinics.annotate(
            month_posts=Count(
                "posts",
                filter=Q(posts__created_at__date__gte=month_start, posts__created_at__date__lt=next_month),
            ),
            month_views=Coalesce(
                Sum("posts__views", filter=Q(posts__created_at__date__gte=month_start, posts__created_at__date__lt=next_month)),
                0,
            ),
            month_comments=Coalesce(
                Sum("posts__comments", filter=Q(posts__created_at__date__gte=month_start, posts__created_at__date__lt=next_month)),
                0,
            ),
            month_messages=Coalesce(
                Sum("posts__message_count", filter=Q(posts__created_at__date__gte=month_start, posts__created_at__date__lt=next_month)),
                0,
            ),
        )
    )

    total = {
        "posts": post_qs.count(),
        "comments": post_qs.aggregate(v=Coalesce(Sum("comments"), 0))["v"] or 0,
        "views": post_qs.aggregate(v=Coalesce(Sum("views"), 0))["v"] or 0,
        "messages": post_qs.aggregate(v=Coalesce(Sum("message_count"), 0))["v"] or 0,
    }

    EXCLUDED_PLATFORM_CODES = {"dadamo", "all"}
    NAVER_CAFE_NAME_BY_KEY = {
        "feko": "여우야",
        "fox5282": "A+ 여우야",
        "juliett00": "성형위키",
        "luxury009": "가아사",
        "knife67": "재잘재잘",
        "suddes": "여생남정",
        "newsmaker": "지살사",
        "imsanbu": "맘스홀릭",
        "cosmania": "파우더룸",
        "parisienlook": "시트먼트",
        "geahwa73": "안양군의왕과천맘",
    }

    def _extract_naver_cafe_key(url):
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            if "cafe.naver.com" not in (parsed.netloc or "").lower():
                return ""
            path = (parsed.path or "").strip("/")
            if not path:
                return ""
            return path.split("/")[0].strip().lower()
        except Exception:
            return ""

    def _normalize_platform(code):
        raw = (code or "").strip()
        low = raw.lower()
        if low in EXCLUDED_PLATFORM_CODES:
            return None
        if raw in {"네이버"} or "naver" in low:
            return "naver"
        if raw in {"성예사"} or "sung" in low or "seong" in low:
            return "seongyesa"
        if raw in {"유튜브"} or "youtube" in low:
            return "youtube"
        if raw in {"전체"} or low == "all":
            return "all"
        return low or "etc"

    raw_platform_rows = list(
        post_qs.order_by().values("platform").annotate(
            total=Count("id"),
            views=Coalesce(Sum("views"), 0),
            comments=Coalesce(Sum("comments"), 0),
            messages=Coalesce(Sum("message_count"), 0),
        ).order_by("-total", "platform")
    )
    platform_code_groups = {}
    platform_rows_map = {}
    for row in raw_platform_rows:
        raw_code = row.get("platform")
        norm = _normalize_platform(raw_code)
        if not norm:
            continue
        platform_code_groups.setdefault(norm, set()).add(raw_code)
        bucket = platform_rows_map.setdefault(
            norm,
            {"platform": norm, "total": 0, "views": 0, "comments": 0, "messages": 0},
        )
        bucket["total"] += row.get("total") or 0
        bucket["views"] += row.get("views") or 0
        bucket["comments"] += row.get("comments") or 0
        bucket["messages"] += row.get("messages") or 0
    platform_rows = sorted(
        list(platform_rows_map.values()),
        key=lambda r: (-r["total"], r["platform"]),
    )
    # 선택 월 데이터가 0이어도, 해당 병원이 실제 사용하는 플랫폼 탭은 유지
    if selected_clinic and not platform_rows:
        used_platforms = list(
            ClinicPost.objects.filter(clinic=selected_clinic)
            .order_by()
            .values_list("platform", flat=True)
            .distinct()
        )
        for raw_code in used_platforms:
            norm = _normalize_platform(raw_code)
            if not norm:
                continue
            platform_code_groups.setdefault(norm, set()).add(raw_code)
        platform_rows = [{"platform": p, "total": 0, "views": 0, "comments": 0, "messages": 0} for p in platform_code_groups.keys()]

    context = {
        "month": month_str,
        "clinic_id": clinic_id,
        "clinics": clinics,
        "selected_clinic": selected_clinic,
        "clinic_picker_rows": clinic_picker_rows,
        "total": total,
        "layout": layout,
        "platform_rows": platform_rows,
        "is_internal_user": is_internal_user,
        "clear_clinic": clear_clinic,
    }

    # 게시글 리스트 데이터와 동일 소스 기반: 플랫폼별 탭 데이터 구성
    if selected_clinic:
        platform_label_map = dict(ClinicPost.PLATFORM_CHOICES)
        display_label_map = {
            "naver": "네이버",
            "seongyesa": "성예사",
            "youtube": "유튜브",
            "all": "전체",
            "etc": "기타",
        }
        platform_sections = []

        def _platform_delta(platform_codes):
            codes = platform_codes if isinstance(platform_codes, (list, tuple, set)) else [platform_codes]
            cur = post_qs.filter(platform__in=codes)
            prev = ClinicPost.objects.filter(
                clinic=selected_clinic,
                platform__in=codes,
                created_at__date__gte=prev_month_start,
                created_at__date__lt=month_start,
            )
            current = {
                "posts": cur.count(),
                "comments": cur.aggregate(v=Coalesce(Sum("comments"), 0))["v"] or 0,
                "views": cur.aggregate(v=Coalesce(Sum("views"), 0))["v"] or 0,
                "messages": cur.aggregate(v=Coalesce(Sum("message_count"), 0))["v"] or 0,
            }
            prev_vals = {
                "posts": prev.count(),
                "comments": prev.aggregate(v=Coalesce(Sum("comments"), 0))["v"] or 0,
                "views": prev.aggregate(v=Coalesce(Sum("views"), 0))["v"] or 0,
                "messages": prev.aggregate(v=Coalesce(Sum("message_count"), 0))["v"] or 0,
            }
            delta = {}
            for key in ("posts", "comments", "views", "messages"):
                pv = prev_vals[key]
                cv = current[key]
                delta[key] = round(((cv - pv) / pv) * 100, 1) if pv else None
            return current, delta

        def _monthly_series(platform_codes, months=6):
            codes = platform_codes if isinstance(platform_codes, (list, tuple, set)) else [platform_codes]
            cursor = month_start
            points = []
            for _ in range(months):
                points.append(cursor)
                if cursor.month == 1:
                    cursor = cursor.replace(year=cursor.year - 1, month=12, day=1)
                else:
                    cursor = cursor.replace(month=cursor.month - 1, day=1)
            points.reverse()

            views_points = []
            comments_points = []
            message_points = []
            for s in points:
                if s.month == 12:
                    e = s.replace(year=s.year + 1, month=1, day=1)
                else:
                    e = s.replace(month=s.month + 1, day=1)
                q = ClinicPost.objects.filter(
                    clinic=selected_clinic,
                    platform__in=codes,
                    created_at__date__gte=s,
                    created_at__date__lt=e,
                )
                views = q.aggregate(v=Coalesce(Sum("views"), 0))["v"] or 0
                comments = q.aggregate(v=Coalesce(Sum("comments"), 0))["v"] or 0
                messages = q.aggregate(v=Coalesce(Sum("message_count"), 0))["v"] or 0
                month_label = f"{s.month}월"
                is_current = s.year == month_start.year and s.month == month_start.month
                views_points.append({
                    "label": month_label,
                    "value": views,
                    "is_current": is_current,
                })
                comments_points.append({
                    "label": month_label,
                    "value": comments,
                    "is_current": is_current,
                })
                message_points.append({
                    "label": month_label,
                    "value": messages,
                    "is_current": is_current,
                })

            return {
                "views_points": views_points,
                "comments_points": comments_points,
                "message_points": message_points,
                "views_max": max([p["value"] for p in views_points] + [1]),
                "comments_max": max([p["value"] for p in comments_points] + [1]),
                "message_max": max([p["value"] for p in message_points] + [1]),
            }

        for prow in platform_rows:
            code = prow.get("platform")
            raw_codes = list(platform_code_groups.get(code, []))
            cur_qs = post_qs.filter(platform__in=raw_codes).select_related("assignee", "assignee__profile") if raw_codes else post_qs.none()
            current, delta = _platform_delta(raw_codes if raw_codes else [code])
            series = _monthly_series(raw_codes if raw_codes else [code])
            views_total = sum(p["value"] for p in series.get("views_points", []))
            comments_total = sum(p["value"] for p in series.get("comments_points", []))
            messages_total = sum(p["value"] for p in series.get("message_points", []))
            detail_rows = list(cur_qs.order_by("-created_at")[:40])
            if code == "naver":
                for post in detail_rows:
                    cafe_key = _extract_naver_cafe_key(getattr(post, "url", ""))
                    setattr(post, "cafe_key", cafe_key)
                    setattr(post, "cafe_name", NAVER_CAFE_NAME_BY_KEY.get(cafe_key, cafe_key or "네이버"))
            platform_sections.append({
                "code": code,
                "label": display_label_map.get(code, platform_label_map.get(code, code)),
                "current": current,
                "delta": delta,
                "series": series,
                "series_totals": {
                    "views": views_total,
                    "comments": comments_total,
                    "messages": messages_total,
                },
                "detail_rows": detail_rows,
                "opinion_rows": cur_qs.filter(type="opinion").order_by("-created_at")[:20],
                "review_rows": cur_qs.filter(type="review").order_by("-created_at")[:20],
            })

        # 분위기/현황 텍스트용: 최근 제목 키워드
        titles = list(post_qs.values_list("title", flat=True)[:120])
        token_counter = Counter()
        for title in titles:
            if not title:
                continue
            for tok in re.findall(r"[가-힣A-Za-z0-9]{2,}", title):
                if tok.lower() in {"후기", "병원", "상담", "진행", "작성", "리뷰"}:
                    continue
                token_counter[tok] += 1
        top_keywords = [k for k, _ in token_counter.most_common(12)]

        # 탭은 실제 데이터가 있는 플랫폼만 (원하는 순서로 정렬)
        preferred_order = {"naver": 0, "seongyesa": 1, "youtube": 2, "gn_jp": 3, "gangnam": 4, "all": 5, "etc": 99}
        platform_sections.sort(key=lambda s: (preferred_order.get(s["code"], 50), s["label"]))
        context["platform_sections"] = platform_sections
        context["top_keywords"] = top_keywords
    else:
        context["platform_sections"] = []
        context["top_keywords"] = []

    return render(request, "dashboard/monthly_report.html", context)

@dashboard_required
def upload_view(request):
    return render(request, "dashboard/upload.html")

@dashboard_required
def review_list(request):
    reviews_qs = Review.objects.all().order_by("-created_at")
    crawled_qs = (
        CrawledPostContent.objects
        .select_related("post")
        .order_by("-fetched_at")
    )

    from django.core.paginator import Paginator
    reviews_page = request.GET.get("reviews_page") or 1
    crawled_page = request.GET.get("crawled_page") or 1
    reviews = Paginator(reviews_qs, 50).get_page(reviews_page)
    crawled = Paginator(crawled_qs, 50).get_page(crawled_page)
    return render(
        request,
        "dashboard/review_list.html",
        {"reviews": reviews, "crawled": crawled},
    )

@dashboard_required
def review_detail(request, pk):
    review = get_object_or_404(Review, pk=pk)
    return render(request, "dashboard/review_detail.html", {"r": review})

@dashboard_required
def post_manage(request):
    type_filter = "all"
    clinic_id = request.GET.get("clinic", "")
    sort = request.GET.get("sort", "latest")

    order_by = "-created_at" if sort != "oldest" else "created_at"
    qs = ClinicPost.objects.select_related("clinic", "assignee").order_by(order_by)
    if clinic_id:
        qs = qs.filter(clinic_id=clinic_id)

    clinic_map = {}
    for post in qs:
        clinic_key = post.clinic_id or 0
        bucket = clinic_map.get(clinic_key)
        if not bucket:
            bucket = {
                "clinic": post.clinic,
                "posts": [],
                "total": 0,
                "opinion": 0,
                "review": 0,
            }
            clinic_map[clinic_key] = bucket
        bucket["posts"].append(post)
        bucket["total"] += 1
        if post.type == "opinion":
            bucket["opinion"] += 1
        else:
            bucket["review"] += 1

    clinic_groups = list(clinic_map.values())
    clinic_groups.sort(key=lambda r: (-r["total"], r["clinic"].name if r["clinic"] else ""))

    clinics = ClinicGuide.objects.filter(is_active=True).order_by("name")

    context = {
        "type_filter": type_filter,
        "clinic_id": clinic_id,
        "sort": sort,
        "clinics": clinics,
        "clinic_groups": clinic_groups,
    }
    return render(request, "dashboard/post_manage.html", context)

@dashboard_required
def review_generate_legacy(request):
    """기존 리뷰 생성 (호환용)"""
    if request.method == 'GET':
        return render(request, "dashboard/review_generate_legacy.html")
    
    clinic = request.POST.get("hospital")
    service = request.POST.get("service")
    tone = request.POST.get("tone", "친절한 톤")
    
    if not clinic or not service:
        return JsonResponse({"error": "hospital and service required"}, status=400)
    
    try:
        generated = generate_review(clinic_name=clinic, treatment=service, tone=tone)
    except Exception as e:
        return JsonResponse({"error": "LLM failed", "detail": str(e)}, status=500)
    
    rev = Review.objects.create(
        original_text=generated,
        cleaned_text=generated[:1000],
        metadata={"generated_by": "llm", "clinic": clinic}
    )
    title_suggestions = generate_title_suggestions(
        generated,
        model="ft:gpt-4.1-2025-04-14:personal::D3C9lMYD",
    )
    return JsonResponse({
        "review": generated,
        "review_id": rev.id,
        "title_suggestions": title_suggestions,
        "model_used": "ft:gpt-4.1-2025-04-14:personal::D3C9lMYD",
        "model_label": _get_model_display("ft:gpt-4.1-2025-04-14:personal::D3C9lMYD"),
    })

@dashboard_required
def image_browser(request):
    images = ImageAsset.objects.all().order_by("-created_at")[:200]
    return render(request, "dashboard/image_browser.html", {"images": images})


# =====================================================
# 새로운 리뷰 생성 시스템 v2
# =====================================================
@dashboard_required
def review_generate_v2(request):
    """개선된 리뷰 생성 페이지 (PRO)"""
    from apps.data.models import ContentTypeProfile
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    clinics = ClinicGuide.objects.filter(is_active=True)
    personas = Persona.objects.filter(is_active=True)
    cafes = CafeProfile.objects.filter(is_active=True)
    content_types = ContentTypeProfile.objects.filter(is_active=True)

    # 템플릿용 형식으로 변환
    content_types_list = [
        {
            "value": ct.value,
            "label": ct.label,
            "desc": ct.description
        }
        for ct in content_types
    ]

    # 모델 목록 변환
    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    context = {
        "clinics": clinics,
        "personas": personas,
        "cafes": cafes,
        "content_types": content_types_list,
        "models": models_list,
    }
    return render(request, "dashboard/review_generate_v2.html", context)

@dashboard_required
def review_generate_basic(request):
    """간단한 리뷰 생성 페이지 (Basic)"""
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    # 모델 목록 변환
    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    context = {
        "models": models_list,
    }
    return render(request, "dashboard/review_generate_basic.html", context)


@dashboard_required
def review_generate_gugong(request):
    """구공이 전용 리뷰 생성 페이지"""
    return render(request, "dashboard/review_generate_gugong.html")

@dashboard_required
@require_http_methods(["POST"])
def api_generate_review_basic(request):
    """Basic 모드 리뷰 생성 API - 사용자 입력을 기본 프롬프트에 결합"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    user_input = data.get("user_input", "").strip()
    model = data.get("model", "claude-sonnet-4-5-20241022")
    template_id = data.get("template_id")  # 선택적 템플릿 ID

    if not user_input:
        return JsonResponse({"error": "리뷰 정보를 입력해주세요."}, status=400)

    # DB에서 프롬프트 템플릿 조회
    from apps.data.models import PromptTemplate

    if template_id:
        template = PromptTemplate.objects.filter(pk=template_id, mode='basic').first()
    else:
        template = PromptTemplate.objects.filter(mode='basic', is_default=True).first()

    # 기본 프롬프트 (템플릿이 없는 경우 폴백)
    DEFAULT_BASIC_PROMPT = """당신은 실제로 시술을 받았거나 받을 환자로서 자연스러운 시술후기, 경험, 상담후기, 질문, 고민, 의견, 잡담들을 작성합니다.
광고가 아닌 진짜 의견과 사실, 경험담처럼 작성해주세요.
아래 정보를 바탕으로 자연스럽고 진정성 있는 후기를 작성해주세요.

## 작성 원칙
1. 실제 환자가 쓴 것처럼 자연스러운 말투 사용
2. 구체적인 경험과 감정 묘사
3. 과장 없이 솔직하게 작성
4. 적절한 길이 (600~1000자)
5. 광고성 문구 사용 금지

## 사용자 제공 정보
{user_input}

자연스러운 후기를 작성해주세요:"""

    # 길이 힌트 파싱 (예: "700자 이상")
    length_hint = None
    min_len = None
    max_len = None
    m_len = re.search(r"(\d+)\s*자\s*(이내|이하|내외|정도|이상|부터)?", user_input)
    if m_len:
        length_hint = f"{m_len.group(1)}자 {m_len.group(2) or ''}".strip()
        n = int(m_len.group(1))
        suffix = m_len.group(2) or ""
        if suffix in {"이상", "부터"}:
            min_len = n
        elif suffix in {"이내", "이하"}:
            max_len = n
        elif suffix in {"내외", "정도"}:
            min_len = max(50, int(n * 0.7))
            max_len = int(n * 1.3)

    # 길이 규칙을 사용자 입력에 보강
    if length_hint:
        extra = [f"길이: {length_hint}"]
        if min_len:
            extra.append(f"규칙: 최소 {min_len}자 이상")
        if max_len:
            extra.append(f"규칙: 최대 {max_len}자 이하")
        user_input = f"{user_input}\n" + "\n".join(extra)

    base_prompt = template.content if template else DEFAULT_BASIC_PROMPT
    prompt = base_prompt.format(user_input=user_input)

    prompt = apply_review_type_guard(prompt)

    print("[DEBUG] api_generate_review_basic prompt preview:")
    print(prompt)

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        from apps.ml.services.usage_logger import log_llm_usage

        # 🔥 LLM 호출
        result = generate_review_with_prompt_enforced(
            prompt,
            model=model,
            return_usage=True
        )
        review_text = result["text"]

        # 길이 최소 기준 미달 시 1회 재생성
        if min_len and len(review_text) < min_len:
            retry_prompt = (
                prompt
                + f"\n\n[중요] 이전 결과가 {len(review_text)}자로 너무 짧습니다. "
                  f"반드시 {min_len}자 이상으로 다시 작성하세요."
            )
            retry_result = generate_review_with_prompt_enforced(
                retry_prompt,
                model=model,
                return_usage=True
            )
            review_text = retry_result["text"]
            result = retry_result

        # ✅ STEP 3 핵심: 사용량 로그 기록
        log_llm_usage(
            user=request.user,
            model=model,
            usage=result
        )

        title_suggestions = generate_title_suggestions(review_text, model=model)

        # DB 저장
        generated_review = GeneratedReview.objects.create(
            generated_text=review_text,
            prompt_used=prompt,
            model_used=model,
            keywords_used=[],
            persona_text="",
            title_suggestions=title_suggestions,
        )

        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "review_id": generated_review.id,
            "review": review_text,
            "char_count": len(review_text),
            "model_used": model,
            "model_label": _get_model_display(model),
            "title_suggestions": title_suggestions,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cached_input_tokens": result.get("cached_input_tokens", 0),
            "total_tokens": result["total_tokens"],
            "cost_usd": round(result["cost_usd"], 6),
            "cost_krw": round(cost_krw, 2),
        })

    except Exception as e:
        return JsonResponse({
            "error": f"생성 실패: {str(e)}"
        }, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_clinic_doctors(request, clinic_id):
    """특정 병원의 의료진 목록 API"""
    clinic = get_object_or_404(ClinicGuide, pk=clinic_id)
    return JsonResponse({
        "doctors": clinic.doctors,
        "consultants": clinic.consultants,
    })

@dashboard_required
@require_http_methods(["POST"])
def api_clinic_procedures(request, clinic_id, doctor_code):
    """특정 의료진의 시술 목록 API"""
    clinic = get_object_or_404(ClinicGuide, pk=clinic_id)
    procedures = clinic.get_procedures_by_doctor(doctor_code)
    return JsonResponse({"procedures": procedures})

@dashboard_required
@require_http_methods(["POST"])
def api_generate_review(request):
    """리뷰 생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        # form data로 시도
        data = request.POST.dict()

    clinic_id = data.get("clinic_id")
    doctor_code = data.get("doctor_code")
    procedure = data.get("procedure")
    content_type = data.get("content_type", "procedure")
    persona_id = data.get("persona_id")
    cafe_id = data.get("cafe_id")
    consultant_name = data.get("consultant_name")
    custom_instructions = data.get("custom_instructions", "")
    model = data.get("model", "gpt-5-mini")  # 모델 선택

    # Pro 템플릿 ID (헤더 & 가이드라인)
    header_template_id = data.get("header_template_id")
    guidelines_template_id = data.get("guidelines_template_id")
    # 문자열을 int로 변환 (빈 문자열 또는 None 처리)
    header_template_id = int(header_template_id) if header_template_id else None
    guidelines_template_id = int(guidelines_template_id) if guidelines_template_id else None

    # 직접입력 값 처리
    clinic_custom = data.get("clinic_custom", "")
    doctor_custom = data.get("doctor_custom", "")
    content_type_custom = data.get("content_type_custom", "")
    persona_custom = data.get("persona_custom", "")
    cafe_custom = data.get("cafe_custom", "")

    # 직접입력 시 custom_instructions에 추가
    custom_parts = []
    if clinic_id == "__custom__" and clinic_custom:
        custom_parts.append(f"병원: {clinic_custom}")
        clinic_id = None
    if doctor_code == "__custom__" and doctor_custom:
        custom_parts.append(f"원장님: {doctor_custom}")
        doctor_code = None
    if content_type == "__custom__" and content_type_custom:
        custom_parts.append(f"컨텐츠 유형: {content_type_custom}")
        content_type = "procedure"  # 기본값 사용
    if persona_id == "__custom__" and persona_custom:
        custom_parts.append(f"작성자 설정: {persona_custom}")
        persona_id = None
    if cafe_id == "__custom__" and cafe_custom:
        custom_parts.append(f"카페/플랫폼: {cafe_custom}")
        cafe_id = None

    if custom_parts:
        custom_instructions = "\n".join(custom_parts) + ("\n" + custom_instructions if custom_instructions else "")

    # 데이터 로드 (직접입력이 아닌 경우에만)
    clinic = None
    if clinic_id and clinic_id not in ["", "__none__", "__custom__"]:
        clinic = ClinicGuide.objects.filter(pk=clinic_id).first()

    persona = None
    if persona_id and persona_id not in ["", "__none__", "__custom__"]:
        persona = Persona.objects.filter(pk=persona_id).first()

    cafe = None
    if cafe_id and cafe_id not in ["", "__none__", "__custom__"]:
        cafe = CafeProfile.objects.filter(pk=cafe_id).first()

    # ContentTypeProfile 조회
    content_type_profile = None
    if content_type and content_type not in ["", "__none__", "__custom__"]:
        content_type_profile = ContentTypeProfile.objects.filter(value=content_type).first()

    # doctor_code 정리
    if doctor_code in ["", "__none__", "__custom__"]:
        doctor_code = None

    # procedure 정리
    if procedure in ["", "__none__"]:
        procedure = None

    # consultant_name 정리
    if consultant_name in ["", "__none__"]:
        consultant_name = None

    try:
        # 프롬프트 생성
        is_ft_model = str(model).startswith("ft:")
        if is_ft_model:
            prompt = build_ft_prompt_from_models(
                clinic=clinic,
                doctor_code=doctor_code,
                procedure=procedure,
                content_type=content_type if content_type not in ["", "__none__"] else "procedure",
                content_type_profile=content_type_profile,
                persona=persona,
                cafe=cafe,
                consultant_name=consultant_name,
                custom_instructions=custom_instructions,
            )
        else:
            prompt = build_prompt_from_models(
                clinic=clinic,
                doctor_code=doctor_code,
                procedure=procedure,
                content_type=content_type if content_type not in ["", "__none__"] else "procedure",
                content_type_profile=content_type_profile,  # ContentTypeProfile 모델 전달
                persona=persona,
                cafe=cafe,
                consultant_name=consultant_name,
                custom_instructions=custom_instructions,
                header_template_id=header_template_id,
                guidelines_template_id=guidelines_template_id,
            )

        prompt = apply_review_type_guard(prompt)

        print("[DEBUG] build_ft_prompt_from_models prompt preview:")
        print(prompt)

        # 리뷰 생성 (선택된 모델 사용)
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        keywords_used = _get_keywords_used(cafe)
        result = generate_review_with_prompt_enforced(
            prompt,
            model=model,
            keywords=keywords_used,
            return_usage=True,
        )
        review_text = result["text"] if isinstance(result, dict) else str(result)
        if isinstance(result, dict):
            log_llm_usage(user=request.user, model=model, usage=result)

        # DB 저장
        doctor_name = ""
        if clinic and doctor_code:
            doctor = clinic.get_doctor_by_code(doctor_code)
            doctor_name = doctor.get('name', '') if doctor else ''

        title_style = cafe.title_style if cafe else ""
        title_suggestions = generate_title_suggestions(
            review_text,
            model=model,
            title_style=title_style,
        )

        generated_review = GeneratedReview.objects.create(
            clinic=clinic,
            persona=persona,
            cafe=cafe,
            doctor_code=doctor_code or "",
            doctor_name=doctor_name,
            procedure=procedure or "",
            generated_text=review_text,
            prompt_used=prompt,
            model_used=model,
            keywords_used=keywords_used,
            persona_text=persona.name if persona else "",
            title_suggestions=title_suggestions,
        )

        return JsonResponse({
            "success": True,
            "review_id": generated_review.id,
            "review": review_text,
            "prompt_preview": prompt,  # 전체 프롬프트 전송
            "char_count": len(review_text),
            "model_used": model,
            "model_label": _get_model_display(model),
            "title_suggestions": title_suggestions,
            "input_tokens": result.get("input_tokens", 0) if isinstance(result, dict) else 0,
            "output_tokens": result.get("output_tokens", 0) if isinstance(result, dict) else 0,
            "cached_input_tokens": result.get("cached_input_tokens", 0) if isinstance(result, dict) else 0,
            "total_tokens": result.get("total_tokens", 0) if isinstance(result, dict) else 0,
            "cost_usd": round(result.get("cost_usd", 0), 6) if isinstance(result, dict) else 0,
            "cost_krw": round(result.get("cost_usd", 0) * 1450, 2) if isinstance(result, dict) else 0,
        })

    except Exception as e:
        return JsonResponse({
            "error": f"생성 실패: {str(e)}"
        }, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_regenerate_review(request):
    """피드백 반영 리뷰 재생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    review_id = data.get("review_id")
    feedback = data.get("feedback")
    model = data.get("model", "gpt-5-mini")  # 모델 선택

    if not review_id or not feedback:
        return JsonResponse({"error": "review_id와 feedback은 필수입니다."}, status=400)

    original = get_object_or_404(GeneratedReview, pk=review_id)

    try:
        from apps.ml.services.llm_service import regenerate_with_feedback

        new_text = regenerate_with_feedback(
            original_prompt=original.prompt_used,
            original_review=original.generated_text,
            feedback=feedback,
            model=model,
        )

        title_suggestions = generate_title_suggestions(new_text, model=model)

        # 새 버전으로 저장
        new_review = GeneratedReview.objects.create(
            clinic=original.clinic,
            persona=original.persona,
            cafe=original.cafe,
            doctor_code=original.doctor_code,
            doctor_name=original.doctor_name,
            procedure=original.procedure,
            generated_text=new_text,
            prompt_used=f"[재생성] 피드백: {feedback}\n\n{original.prompt_used}",
            model_used=model,
            keywords_used=original.keywords_used,
            persona_text=original.persona_text,
            title_suggestions=title_suggestions,
            status="edited",
        )

        return JsonResponse({
            "success": True,
            "review_id": new_review.id,
            "review": new_text,
            "char_count": len(new_text),
            "model_used": model,
            "model_label": _get_model_display(model),
            "title_suggestions": title_suggestions,
        })

    except Exception as e:
        return JsonResponse({"error": f"재생성 실패: {str(e)}"}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_generate_prompt(request):
    """프롬프트만 생성하는 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    clinic_id = data.get("clinic_id")
    doctor_code = data.get("doctor_code")
    procedure = data.get("procedure")
    content_type = data.get("content_type", "procedure")
    persona_id = data.get("persona_id")
    cafe_id = data.get("cafe_id")
    consultant_name = data.get("consultant_name")
    custom_instructions = data.get("custom_instructions", "")

    # Pro 템플릿 ID (헤더 & 가이드라인)
    header_template_id = data.get("header_template_id")
    guidelines_template_id = data.get("guidelines_template_id")
    # 문자열을 int로 변환 (빈 문자열 또는 None 처리)
    header_template_id = int(header_template_id) if header_template_id else None
    guidelines_template_id = int(guidelines_template_id) if guidelines_template_id else None

    # 직접입력 값 처리
    clinic_custom = data.get("clinic_custom", "")
    doctor_custom = data.get("doctor_custom", "")
    content_type_custom = data.get("content_type_custom", "")
    persona_custom = data.get("persona_custom", "")
    cafe_custom = data.get("cafe_custom", "")

    # 직접입력 시 custom_instructions에 추가
    custom_parts = []
    if clinic_id == "__custom__" and clinic_custom:
        custom_parts.append(f"병원: {clinic_custom}")
        clinic_id = None
    if doctor_code == "__custom__" and doctor_custom:
        custom_parts.append(f"원장님: {doctor_custom}")
        doctor_code = None
    if content_type == "__custom__" and content_type_custom:
        custom_parts.append(f"컨텐츠 유형: {content_type_custom}")
        content_type = ""
    if persona_id == "__custom__" and persona_custom:
        custom_parts.append(f"작성자 설정: {persona_custom}")
        persona_id = None
    if cafe_id == "__custom__" and cafe_custom:
        custom_parts.append(f"카페/플랫폼: {cafe_custom}")
        cafe_id = None

    if custom_parts:
        custom_instructions = "\n".join(custom_parts) + ("\n" + custom_instructions if custom_instructions else "")

    # 데이터 로드
    clinic = None
    if clinic_id and clinic_id not in ["", "__none__", "__custom__"]:
        clinic = ClinicGuide.objects.filter(pk=clinic_id).first()

    persona = None
    if persona_id and persona_id not in ["", "__none__", "__custom__"]:
        persona = Persona.objects.filter(pk=persona_id).first()

    cafe = None
    if cafe_id and cafe_id not in ["", "__none__", "__custom__"]:
        cafe = CafeProfile.objects.filter(pk=cafe_id).first()

    # ContentTypeProfile 조회
    content_type_profile = None
    if content_type and content_type not in ["", "__none__", "__custom__"]:
        content_type_profile = ContentTypeProfile.objects.filter(value=content_type).first()

    # doctor_code 정리
    if doctor_code in ["", "__none__", "__custom__"]:
        doctor_code = None

    # procedure 정리
    if procedure in ["", "__none__"]:
        procedure = None

    # consultant_name 정리
    if consultant_name in ["", "__none__"]:
        consultant_name = None

    try:
        # 프롬프트 생성
        prompt = build_prompt_from_models(
            clinic=clinic,
            doctor_code=doctor_code,
            procedure=procedure,
            content_type=content_type if content_type not in ["", "__none__"] else "",
            content_type_profile=content_type_profile,
            persona=persona,
            cafe=cafe,
            consultant_name=consultant_name,
            custom_instructions=custom_instructions,
            header_template_id=header_template_id,
            guidelines_template_id=guidelines_template_id,
        )

        return JsonResponse({
            "success": True,
            "prompt": prompt,
        })

    except Exception as e:
        return JsonResponse({
            "error": f"프롬프트 생성 실패: {str(e)}"
        }, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_generate_review_from_prompt(request):
    """프롬프트를 직접 받아서 리뷰 생성하는 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    prompt = data.get("prompt")
    model = data.get("model", "gpt-5-mini")

    if not prompt:
        return JsonResponse({"error": "prompt는 필수입니다."}, status=400)

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        prompt = apply_review_type_guard(prompt)
        result = generate_review_with_prompt_enforced(prompt, model=model, return_usage=True)
        review_text = result["text"]
        log_llm_usage(user=request.user, model=model, usage=result)

        title_suggestions = generate_title_suggestions(review_text, model=model)

        # DB 저장
        generated_review = GeneratedReview.objects.create(
            generated_text=review_text,
            prompt_used=prompt,
            model_used=model,
            keywords_used=[],
            persona_text="",
            title_suggestions=title_suggestions,
        )

        # 원화 환산 (1 USD = 약 1,450 KRW)
        cost_krw = result["cost_usd"] * 1450
        return JsonResponse({
            "success": True,
            "review_id": generated_review.id,
            "review": review_text,
            "char_count": len(review_text),
            "model_used": model,
            "model_label": _get_model_display(model),
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
            "title_suggestions": title_suggestions,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cached_input_tokens": result.get("cached_input_tokens", 0),
            "total_tokens": result["total_tokens"],
            "cost_usd": round(result["cost_usd"], 6),
            "cost_krw": round(cost_krw, 2),
        })

    except Exception as e:
        return JsonResponse({
            "error": f"생성 실패: {str(e)}"
        }, status=500)


# =====================================================
# 생성된 리뷰 관리
# =====================================================
@dashboard_required
def generated_review_list(request):
    """생성된 리뷰 목록"""
    kind = (request.GET.get("kind") or "all").strip().lower()
    base_qs = GeneratedReview.objects.select_related('clinic', 'persona', 'cafe')
    if kind == "edited":
        reviews = base_qs.filter(status="edited")[:100]
    elif kind == "original":
        reviews = base_qs.exclude(status="edited")[:100]
    else:
        reviews = base_qs.all()[:100]

    counts = {
        "all": base_qs.count(),
        "original": base_qs.exclude(status="edited").count(),
        "edited": base_qs.filter(status="edited").count(),
    }
    for review in reviews:
        review.model_display = _get_model_display(review.model_used)
    return render(
        request,
        "dashboard/generated_review_list.html",
        {"reviews": reviews, "kind": kind, "counts": counts},
    )

@dashboard_required
def generated_review_detail(request, pk):
    """생성된 리뷰 상세"""
    review = get_object_or_404(GeneratedReview, pk=pk)
    review.model_display = _get_model_display(review.model_used)
    return render(request, "dashboard/generated_review_detail.html", {"review": review})

@dashboard_required
@require_http_methods(["POST"])
def api_save_edited_review(request):
    """생성 결과를 수정본으로 저장"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    review_id = data.get("review_id")
    edited_text = (data.get("edited_text") or "").strip()
    title_suggestions = data.get("title_suggestions")
    regenerate_titles = bool(data.get("regenerate_titles", False))

    if not review_id or not edited_text:
        return JsonResponse({"error": "review_id와 edited_text는 필수입니다."}, status=400)

    original = get_object_or_404(GeneratedReview, pk=review_id)
    # 수정 저장은 즉시 응답이 중요하므로 기본값은 기존 제목 재사용.
    # 필요할 때만 regenerate_titles=true 로 제목을 재생성한다.
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
        "review": edited.generated_text,
        "char_count": len(edited.generated_text),
        "status": edited.status,
        "model_used": edited.model_used,
        "model_label": _get_model_display(edited.model_used),
        "title_suggestions": edited.title_suggestions,
    })

@dashboard_required
@require_http_methods(["POST"])
def api_generated_bulk_delete(request):
    """생성된 리뷰 일괄 삭제 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    ids = data.get("ids", [])

    if not ids:
        return JsonResponse({"error": "삭제할 항목이 없습니다."}, status=400)

    try:
        deleted_count, _ = GeneratedReview.objects.filter(pk__in=ids).delete()
        return JsonResponse({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개 삭제됨"
        })
    except Exception as e:
        return JsonResponse({"error": f"삭제 실패: {str(e)}"}, status=500)


# =====================================================
# 병원 가이드 관리
# =====================================================
@dashboard_required
def clinic_list(request):
    """병원 가이드 목록"""
    clinics = ClinicGuide.objects.all().order_by('-created_at')
    return render(request, "dashboard/clinic_list.html", {"clinics": clinics})

@dashboard_required
def clinic_detail(request, pk):
    clinic = get_object_or_404(ClinicGuide, pk=pk)

    # 1️⃣ 이 병원의 원장 목록
    doctors = clinic.doctor_objects.filter(is_active=True).order_by("order")

    # 2️⃣ URL 파라미터
    selected_code = request.GET.get("doctor")

    # 3️⃣ 선택된 원장 결정 (🔥 핵심)
    if selected_code:
        selected_doctor = doctors.filter(
            models.Q(code=selected_code) |
            models.Q(name=selected_code)
        ).first()
    else:
        # 👉 자동 선택
        selected_doctor = doctors.first()

    # 4️⃣ 수가 조회
    if selected_doctor:
        price_list = selected_doctor.prices.filter(
            is_active=True
        ).order_by("order")
        selected_code = selected_doctor.code or selected_doctor.name
    else:
        price_list = []

    return render(request, "dashboard/clinic_detail.html", {
        "clinic": clinic,
        "doctors": doctors,
        "selected_doctor": selected_doctor,
        "selected_code": selected_code,
        "price_list": price_list,
    })

@dashboard_required
@require_http_methods(["POST"])
def api_import_clinic_md(request):
    """MD 파일로 병원 가이드 임포트"""
    md_content = request.POST.get("md_content")
    clinic_name = request.POST.get("clinic_name")
    
    if not md_content:
        return JsonResponse({"error": "md_content는 필수입니다."}, status=400)
    
    try:
        # 파싱
        data = parse_clinic_md_with_llm(md_content)
        data = normalize_clinic_payload(data)
        
        # 저장
        clinic, created = ClinicGuide.objects.update_or_create(
            name=clinic_name or "새 병원",
            defaults={
                'location': data["basic_info"].get("location", ""),
                'hours': data["basic_info"].get("hours", ""),
                'parking': data["basic_info"].get("parking", ""),
                'doctors': data["doctors"],
                'consultants': data["consultants"],
                'price_list': data["price_list"],
                'process': data["process"],
                'aftercare': data["aftercare"],
                'post_care': data["post_care"],
                'features': data["features"],
                'allowed_hospitals': data["allowed_hospitals"],
                'blocked_hospitals': data["blocked_hospitals"],
                'raw_data': data["raw_data"],
            }
        )
        
        return JsonResponse({
            "success": True,
            "clinic_id": clinic.id,
            "clinic_name": clinic.name,
            "created": created,
            "doctors_count": len(data["doctors"]),
            "procedures_count": len(data["price_list"]),
        })
        
    except Exception as e:
        return JsonResponse({"error": f"임포트 실패: {str(e)}"}, status=500)

@dashboard_required
def clinic_import(request):
    """병원 가이드 MD 임포트 페이지"""
    if request.method == 'GET':
        return render(request, "dashboard/clinic_import.html")

    # POST 처리는 api_import_clinic_md에서
    return api_import_clinic_md(request)

@dashboard_required
@require_http_methods(["POST"])
def api_clinic_delete(request, pk):
    """병원 가이드 삭제"""
    clinic = get_object_or_404(ClinicGuide, pk=pk)
    clinic.delete()
    return JsonResponse({"success": True})

@dashboard_required
@require_http_methods(["POST"])
def api_clinic_toggle(request, pk):
    """병원 가이드 활성화/비활성화"""
    clinic = get_object_or_404(ClinicGuide, pk=pk)
    clinic.is_active = not clinic.is_active
    clinic.save()
    return JsonResponse({"success": True, "is_active": clinic.is_active})


# =====================================================
# 스타일 분석 기능
# =====================================================
@dashboard_required
def style_analyzer(request):
    """스타일 분석 페이지"""
    personas = Persona.objects.filter(is_active=True)
    cafes = CafeProfile.objects.filter(is_active=True)
    
    return render(request, "dashboard/style_analyzer.html", {
        "personas": personas,
        "cafes": cafes,
    })

@dashboard_required
@require_http_methods(["POST"])
def api_analyze_style(request):
    """스타일 분석 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()
    
    texts_raw = data.get("texts", "")
    
    # 텍스트 분리 (구분자: ---, ===, 또는 빈 줄 2개 이상)
    if isinstance(texts_raw, str):
        texts = re.split(r'\n---+\n|\n===+\n|\n{3,}', texts_raw)
        texts = [t.strip() for t in texts if t.strip() and len(t.strip()) > 50]
    else:
        texts = texts_raw
    
    if not texts:
        return JsonResponse({"error": "분석할 텍스트가 없습니다. 최소 50자 이상의 후기를 입력해주세요."}, status=400)
    
    if len(texts) < 2:
        return JsonResponse({"error": "최소 2개 이상의 후기가 필요합니다. '---'로 구분해주세요."}, status=400)
    
    try:
        from apps.ml.services.style_analyzer import analyze_style
        result = analyze_style(texts)
        
        return JsonResponse({
            "success": True,
            "sample_count": len(texts),
            **result
        })
        
    except Exception as e:
        return JsonResponse({"error": f"분석 실패: {str(e)}"}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_create_persona_from_style(request):
    """스타일 분석 결과로 페르소나 생성"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()
    
    persona_data = data.get("persona")
    custom_name = data.get("name")
    
    if not persona_data:
        return JsonResponse({"error": "페르소나 데이터가 없습니다."}, status=400)
    
    try:
        name = custom_name or persona_data.get("name", "추출된 페르소나")
        
        persona = Persona.objects.create(
            name=name,
            description=persona_data.get("description", "스타일 분석으로 추출됨"),
            age_group=persona_data.get("age_group", ""),
            gender=persona_data.get("gender", ""),
            speech_style=persona_data.get("speech_style", ""),
            detail_level=persona_data.get("detail_level", "moderate"),
            emoji_usage=persona_data.get("emoji_usage", False),
            example_phrases=persona_data.get("example_phrases", []),
            keywords=persona_data.get("keywords", []),
        )
        
        return JsonResponse({
            "success": True,
            "persona_id": persona.id,
            "persona_name": persona.name,
        })
        
    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_create_cafe_from_style(request):
    """스타일 분석 결과로 카페 프로필 생성"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    cafe_data = data.get("cafe_profile")
    custom_name = data.get("name")

    if not cafe_data:
        return JsonResponse({"error": "카페 프로필 데이터가 없습니다."}, status=400)

    if not custom_name:
        return JsonResponse({"error": "카페 이름을 입력해주세요."}, status=400)

    try:
        cafe = CafeProfile.objects.create(
            name=custom_name,
            length_range=cafe_data.get("length_range", "800_1500"),
            required_elements=cafe_data.get("required_elements", []),
            forbidden_keywords=cafe_data.get("forbidden_words", []),
            tips=cafe_data.get("tips", ""),
        )

        return JsonResponse({
            "success": True,
            "cafe_id": cafe.id,
            "cafe_name": cafe.name,
        })

    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_create_content_type_from_style(request):
    """스타일 분석 결과로 컨텐츠 타입 생성"""
    from apps.data.models import ContentTypeProfile

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST.dict()

    label = data.get("label")
    value = data.get("value")
    analysis = data.get("analysis", {})

    if not label:
        return JsonResponse({"error": "컨텐츠 타입 이름을 입력해주세요."}, status=400)

    if not value:
        value = label.lower().replace(" ", "_").replace("/", "_")

    try:
        quant = analysis.get("quantitative", {})
        qual = analysis.get("qualitative", {})

        avg_chars = quant.get("avg_char_count", 800)
        min_length = int(avg_chars * 0.7)
        max_length = int(avg_chars * 1.3)

        content_type = ContentTypeProfile.objects.create(
            value=value,
            label=label,
            description=f"스타일 분석으로 추출됨",
            tone=qual.get("tone", ""),
            structure=[qual.get("structure_pattern", "")],
            common_expressions=qual.get("common_expressions", [])[:5],
            min_length=min_length,
            max_length=max_length,
        )

        return JsonResponse({
            "success": True,
            "content_type_id": content_type.id,
            "content_type_name": content_type.label,
        })

    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)


# =====================================================
# 이미지 OCR 기능
# =====================================================
@dashboard_required
@require_http_methods(["POST"])
def api_extract_text_from_images(request):
    """이미지에서 텍스트 추출 API (GPT-4o Vision)"""
    from apps.ml.services.llm_service import extract_texts_from_images

    files = request.FILES.getlist('images')

    if not files:
        return JsonResponse({"error": "이미지 파일을 업로드해주세요."}, status=400)

    if len(files) > 10:
        return JsonResponse({"error": "최대 10개까지 업로드 가능합니다."}, status=400)

    # 이미지 데이터 수집
    images = []
    for f in files:
        # 파일 타입 확인
        content_type = f.content_type
        if not content_type.startswith('image/'):
            continue

        # 파일 크기 제한 (10MB)
        if f.size > 10 * 1024 * 1024:
            continue

        image_data = f.read()
        images.append((image_data, content_type))

    if not images:
        return JsonResponse({"error": "유효한 이미지 파일이 없습니다."}, status=400)

    try:
        # GPT-4o Vision으로 텍스트 추출
        texts = extract_texts_from_images(images)

        if not texts:
            return JsonResponse({
                "error": "이미지에서 텍스트를 추출하지 못했습니다. 텍스트가 포함된 이미지인지 확인해주세요."
            }, status=400)

        return JsonResponse({
            "success": True,
            "texts": texts,
            "count": len(texts),
            "combined": "\n\n---\n\n".join(texts),
        })

    except Exception as e:
        return JsonResponse({"error": f"텍스트 추출 실패: {str(e)}"}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_analyze_style_from_images(request):
    """이미지에서 텍스트 추출 후 스타일 분석까지 한 번에"""
    from apps.ml.services.llm_service import extract_texts_from_images
    from apps.ml.services.style_analyzer import analyze_style

    files = request.FILES.getlist('images')

    if not files:
        return JsonResponse({"error": "이미지 파일을 업로드해주세요."}, status=400)

    if len(files) > 10:
        return JsonResponse({"error": "최대 10개까지 업로드 가능합니다."}, status=400)

    # 이미지 데이터 수집
    images = []
    for f in files:
        content_type = f.content_type
        if not content_type.startswith('image/'):
            continue
        if f.size > 10 * 1024 * 1024:
            continue
        image_data = f.read()
        images.append((image_data, content_type))

    if not images:
        return JsonResponse({"error": "유효한 이미지 파일이 없습니다."}, status=400)

    try:
        # 1. 이미지에서 텍스트 추출
        texts = extract_texts_from_images(images)

        if not texts:
            return JsonResponse({
                "error": "이미지에서 텍스트를 추출하지 못했습니다."
            }, status=400)

        if len(texts) < 2:
            return JsonResponse({
                "error": f"최소 2개 이상의 후기가 필요합니다. 현재 {len(texts)}개 추출됨."
            }, status=400)

        # 2. 스타일 분석
        result = analyze_style(texts)

        return JsonResponse({
            "success": True,
            "extracted_count": len(texts),
            "extracted_texts": texts,
            **result
        })

    except Exception as e:
        return JsonResponse({"error": f"분석 실패: {str(e)}"}, status=500)


# =====================================================
# 페르소나 관리
# =====================================================
@dashboard_required
def persona_list(request):
    """페르소나 목록"""
    personas = Persona.objects.all().order_by('-is_active', '-created_at')
    return render(request, "dashboard/persona_list.html", {"personas": personas})

@dashboard_required
def persona_edit(request, pk=None):
    """페르소나 생성/수정"""
    if pk:
        persona = get_object_or_404(Persona, pk=pk)
    else:
        persona = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, "dashboard/persona_edit.html", {
                "persona": persona,
                "error": "페르소나 이름을 입력해주세요."
            })

        # example_phrases와 keywords 파싱
        example_phrases_raw = request.POST.get('example_phrases', '')
        example_phrases = [p.strip() for p in example_phrases_raw.split('\n') if p.strip()]

        keywords_raw = request.POST.get('keywords', '')
        keywords = [k.strip() for k in keywords_raw.replace(',', '\n').split('\n') if k.strip()]

        data = {
            'name': name,
            'description': request.POST.get('description', ''),
            'age_group': request.POST.get('age_group', ''),
            'gender': request.POST.get('gender', ''),
            'speech_style': request.POST.get('speech_style', ''),
            'detail_level': request.POST.get('detail_level', 'moderate'),
            'emoji_usage': request.POST.get('emoji_usage') == 'on',
            'example_phrases': example_phrases,
            'keywords': keywords,
            'is_active': request.POST.get('is_active') == 'on',
        }

        if persona:
            for key, value in data.items():
                setattr(persona, key, value)
            persona.save()
        else:
            persona = Persona.objects.create(**data)

        return render(request, "dashboard/persona_edit.html", {
            "persona": persona,
            "success": "저장되었습니다."
        })

    return render(request, "dashboard/persona_edit.html", {"persona": persona})

@dashboard_required
@require_http_methods(["POST"])
def api_persona_delete(request, pk):
    """페르소나 삭제 API"""
    persona = get_object_or_404(Persona, pk=pk)
    name = persona.name
    persona.delete()
    return JsonResponse({"success": True, "message": f"'{name}' 페르소나가 삭제되었습니다."})

@dashboard_required
@require_http_methods(["POST"])
def api_persona_toggle(request, pk):
    """페르소나 활성화 토글 API"""
    persona = get_object_or_404(Persona, pk=pk)
    persona.is_active = not persona.is_active
    persona.save()
    return JsonResponse({
        "success": True,
        "is_active": persona.is_active,
        "message": f"'{persona.name}' {'활성화' if persona.is_active else '비활성화'}됨"
    })


# =====================================================
# 카페 프로필 관리
# =====================================================
@dashboard_required
def cafe_list(request):
    """카페 프로필 목록"""
    cafes = CafeProfile.objects.all().order_by('-is_active', '-created_at')
    return render(request, "dashboard/cafe_list.html", {"cafes": cafes})

@dashboard_required
def cafe_edit(request, pk=None):
    """카페 프로필 생성/수정"""
    if pk:
        cafe = get_object_or_404(CafeProfile, pk=pk)
    else:
        cafe = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, "dashboard/cafe_edit.html", {
                "cafe": cafe,
                "error": "카페 이름을 입력해주세요."
            })

        # 리스트 필드 파싱
        required_sections_raw = request.POST.get('required_sections', '')
        required_sections = [s.strip() for s in required_sections_raw.split('\n') if s.strip()]

        forbidden_words_raw = request.POST.get('forbidden_words', '')
        forbidden_words = [w.strip() for w in forbidden_words_raw.replace(',', '\n').split('\n') if w.strip()]

        recommended_words_raw = request.POST.get('recommended_words', '')
        recommended_words = [w.strip() for w in recommended_words_raw.replace(',', '\n').split('\n') if w.strip()]

        try:
            min_length = int(request.POST.get('min_length', 500))
            max_length = int(request.POST.get('max_length', 1500))
        except ValueError:
            min_length = 500
            max_length = 1500

        data = {
            'name': name,
            'url': request.POST.get('url', ''),
            'category': request.POST.get('category', ''),
            'vibe': request.POST.get('vibe', ''),
            'min_length': min_length,
            'max_length': max_length,
            'required_sections': required_sections,
            'forbidden_words': forbidden_words,
            'recommended_words': recommended_words,
            'title_style': request.POST.get('title_style', ''),
            'image_required': request.POST.get('image_required') == 'on',
            'tips': request.POST.get('tips', ''),
            'is_active': request.POST.get('is_active') == 'on',
        }

        if cafe:
            for key, value in data.items():
                setattr(cafe, key, value)
            cafe.save()
        else:
            cafe = CafeProfile.objects.create(**data)

        return render(request, "dashboard/cafe_edit.html", {
            "cafe": cafe,
            "success": "저장되었습니다."
        })

    return render(request, "dashboard/cafe_edit.html", {"cafe": cafe})

@dashboard_required
@require_http_methods(["POST"])
def api_cafe_delete(request, pk):
    """카페 프로필 삭제 API"""
    cafe = get_object_or_404(CafeProfile, pk=pk)
    name = cafe.name
    cafe.delete()
    return JsonResponse({"success": True, "message": f"'{name}' 카페 프로필이 삭제되었습니다."})

@dashboard_required
@require_http_methods(["POST"])
def api_cafe_toggle(request, pk):
    """카페 프로필 활성화 토글 API"""
    cafe = get_object_or_404(CafeProfile, pk=pk)
    cafe.is_active = not cafe.is_active
    cafe.save()
    return JsonResponse({
        "success": True,
        "is_active": cafe.is_active,
        "message": f"'{cafe.name}' {'활성화' if cafe.is_active else '비활성화'}됨"
    })


# =====================================================
# 프리셋 불러오기 API
# =====================================================
@dashboard_required
@require_http_methods(["POST"])
def api_load_persona_presets(request):
    """페르소나 프리셋 불러오기"""
    from apps.data.initial_data import PERSONA_PRESETS

    created_count = 0
    updated_count = 0

    for preset in PERSONA_PRESETS:
        persona, created = Persona.objects.update_or_create(
            name=preset['name'],
            defaults=preset
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    return JsonResponse({
        "success": True,
        "message": f"{created_count}개 생성, {updated_count}개 업데이트됨",
        "created": created_count,
        "updated": updated_count
    })

@dashboard_required
@require_http_methods(["POST"])
def api_load_cafe_presets(request):
    """카페 프로필 프리셋 불러오기"""
    from apps.data.initial_data import CAFE_PRESETS

    created_count = 0
    updated_count = 0

    for preset in CAFE_PRESETS:
        cafe, created = CafeProfile.objects.update_or_create(
            name=preset['name'],
            defaults=preset
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    return JsonResponse({
        "success": True,
        "message": f"{created_count}개 생성, {updated_count}개 업데이트됨",
        "created": created_count,
        "updated": updated_count
    })


# =====================================================
# 프리셋 미리보기 및 개별 추가 API
# =====================================================
@dashboard_required
@require_http_methods(["GET"])
def api_get_persona_presets(request):
    """페르소나 프리셋 목록 조회 (이미 추가된 것 표시)"""
    from apps.data.initial_data import PERSONA_PRESETS

    existing_names = set(Persona.objects.values_list('name', flat=True))

    presets = []
    for idx, preset in enumerate(PERSONA_PRESETS):
        presets.append({
            "index": idx,
            "name": preset['name'],
            "description": preset.get('description', ''),
            "age_group": preset.get('age_group', ''),
            "gender": preset.get('gender', ''),
            "speech_style": preset.get('speech_style', ''),
            "detail_level": preset.get('detail_level', 'moderate'),
            "emoji_usage": preset.get('emoji_usage', False),
            "example_phrases": preset.get('example_phrases', []),
            "keywords": preset.get('keywords', []),
            "already_exists": preset['name'] in existing_names
        })

    return JsonResponse({"success": True, "presets": presets})

@dashboard_required
@require_http_methods(["get"])
def api_get_cafe_presets(request):
    """카페 프리셋 목록 조회 (이미 추가된 것 표시)"""
    from apps.data.initial_data import CAFE_PRESETS

    existing_names = set(CafeProfile.objects.values_list('name', flat=True))

    presets = []
    for idx, preset in enumerate(CAFE_PRESETS):
        presets.append({
            "index": idx,
            "name": preset['name'],
            "category": preset.get('category', ''),
            "vibe": preset.get('vibe', ''),
            "min_length": preset.get('min_length', 500),
            "max_length": preset.get('max_length', 1500),
            "required_sections": preset.get('required_sections', []),
            "forbidden_words": preset.get('forbidden_words', []),
            "recommended_words": preset.get('recommended_words', []),
            "title_style": preset.get('title_style', ''),
            "image_required": preset.get('image_required', False),
            "tips": preset.get('tips', ''),
            "already_exists": preset['name'] in existing_names
        })

    return JsonResponse({"success": True, "presets": presets})

@dashboard_required
@require_http_methods(["POST"])
def api_add_persona_preset(request):
    """개별 페르소나 프리셋 추가"""
    from apps.data.initial_data import PERSONA_PRESETS

    try:
        data = json.loads(request.body)
        index = data.get('index')

        if index is None or index < 0 or index >= len(PERSONA_PRESETS):
            return JsonResponse({"success": False, "error": "잘못된 프리셋 인덱스"}, status=400)

        preset = PERSONA_PRESETS[index]
        persona, created = Persona.objects.update_or_create(
            name=preset['name'],
            defaults=preset
        )

        return JsonResponse({
            "success": True,
            "created": created,
            "message": f"'{preset['name']}' {'추가됨' if created else '업데이트됨'}",
            "persona_id": persona.pk
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_add_cafe_preset(request):
    """개별 카페 프리셋 추가"""
    from apps.data.initial_data import CAFE_PRESETS

    try:
        data = json.loads(request.body)
        index = data.get('index')

        if index is None or index < 0 or index >= len(CAFE_PRESETS):
            return JsonResponse({"success": False, "error": "잘못된 프리셋 인덱스"}, status=400)

        preset = CAFE_PRESETS[index]
        cafe, created = CafeProfile.objects.update_or_create(
            name=preset['name'],
            defaults=preset
        )

        return JsonResponse({
            "success": True,
            "created": created,
            "message": f"'{preset['name']}' {'추가됨' if created else '업데이트됨'}",
            "cafe_id": cafe.pk
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# =====================================================
# 컨텐츠 타입 관리
# =====================================================

from apps.data.models import ContentTypeProfile
@dashboard_required
def content_type_list(request):
    """컨텐츠 타입 목록"""
    content_types = ContentTypeProfile.objects.all()
    return render(request, "dashboard/content_type_list.html", {"content_types": content_types})

@dashboard_required
def content_type_edit(request, pk=None):
    """컨텐츠 타입 생성/수정"""
    if pk:
        content_type = get_object_or_404(ContentTypeProfile, pk=pk)
    else:
        content_type = None

    if request.method == "POST":
        data = request.POST

        # JSON 필드 파싱
        def parse_list(field_name):
            val = data.get(field_name, "").strip()
            if not val:
                return []
            return [item.strip() for item in val.split("\n") if item.strip()]

        fields = {
            "value": data.get("value", "").strip(),
            "label": data.get("label", "").strip(),
            "description": data.get("description", "").strip(),
            "structure": parse_list("structure"),
            "required_sections": parse_list("required_sections"),
            "common_expressions": parse_list("common_expressions"),
            "opening_patterns": parse_list("opening_patterns"),
            "closing_patterns": parse_list("closing_patterns"),
            "forbidden_elements": parse_list("forbidden_elements"),
            "recommended_elements": parse_list("recommended_elements"),
            "tone": data.get("tone", "").strip(),
            "emotion_flow": parse_list("emotion_flow"),
            "min_length": int(data.get("min_length") or 400),
            "max_length": int(data.get("max_length") or 1200),
            "image_required": data.get("image_required") == "on",
            "tips": data.get("tips", "").strip(),
            "is_active": data.get("is_active") == "on",
        }

        if content_type:
            for key, val in fields.items():
                setattr(content_type, key, val)
            content_type.save()
        else:
            content_type = ContentTypeProfile.objects.create(**fields)

        return JsonResponse({"success": True, "redirect": "/dashboard/content-types/"})

    return render(request, "dashboard/content_type_edit.html", {"content_type": content_type})

@dashboard_required
@require_http_methods(["POST"])
def api_content_type_delete(request, pk):
    """컨텐츠 타입 삭제"""
    content_type = get_object_or_404(ContentTypeProfile, pk=pk)
    content_type.delete()
    return JsonResponse({"success": True})

@dashboard_required
@require_http_methods(["POST"])
def api_content_type_toggle(request, pk):
    """컨텐츠 타입 활성화/비활성화"""
    content_type = get_object_or_404(ContentTypeProfile, pk=pk)
    content_type.is_active = not content_type.is_active
    content_type.save()
    return JsonResponse({"success": True, "is_active": content_type.is_active})

@dashboard_required
@require_http_methods(["GET"])
def api_get_content_type_presets(request):
    """컨텐츠 타입 프리셋 목록 조회"""
    from apps.data.initial_data import CONTENT_TYPE_PRESETS

    existing_values = set(ContentTypeProfile.objects.values_list('value', flat=True))

    presets = []
    for idx, preset in enumerate(CONTENT_TYPE_PRESETS):
        presets.append({
            "index": idx,
            "value": preset['value'],
            "label": preset['label'],
            "description": preset.get('description', ''),
            "structure": preset.get('structure', []),
            "required_sections": preset.get('required_sections', []),
            "tone": preset.get('tone', ''),
            "min_length": preset.get('min_length', 400),
            "max_length": preset.get('max_length', 1200),
            "image_required": preset.get('image_required', False),
            "tips": preset.get('tips', ''),
            "already_exists": preset['value'] in existing_values
        })

    return JsonResponse({"success": True, "presets": presets})

@dashboard_required
@require_http_methods(["POST"])
def api_add_content_type_preset(request):
    """개별 컨텐츠 타입 프리셋 추가"""
    from apps.data.initial_data import CONTENT_TYPE_PRESETS

    try:
        data = json.loads(request.body)
        index = data.get('index')

        if index is None or index < 0 or index >= len(CONTENT_TYPE_PRESETS):
            return JsonResponse({"success": False, "error": "잘못된 프리셋 인덱스"}, status=400)

        preset = CONTENT_TYPE_PRESETS[index]
        content_type, created = ContentTypeProfile.objects.update_or_create(
            value=preset['value'],
            defaults=preset
        )

        return JsonResponse({
            "success": True,
            "created": created,
            "message": f"'{preset['label']}' {'추가됨' if created else '업데이트됨'}",
            "content_type_id": content_type.pk
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@dashboard_required
@require_http_methods(["POST"])
def api_load_content_type_presets(request):
    """컨텐츠 타입 프리셋 전체 불러오기"""
    from apps.data.initial_data import CONTENT_TYPE_PRESETS

    created_count = 0
    updated_count = 0

    for preset in CONTENT_TYPE_PRESETS:
        content_type, created = ContentTypeProfile.objects.update_or_create(
            value=preset['value'],
            defaults=preset
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    return JsonResponse({
        "success": True,
        "message": f"{created_count}개 생성, {updated_count}개 업데이트됨",
        "created": created_count,
        "updated": updated_count
    })

@dashboard_required
def llm_usage_dashboard(request):
    start_date, end_date = _get_usage_range(request, default_days=30)

    qs = LLMUsageLog.objects.select_related("user").filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    total_stats = qs.aggregate(
        total_cost=Sum("cost_krw"),
        total_tokens=Sum("total_tokens"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        count=Count("id"),
    )

    # =========================
    # 📈 날짜별 사용량 (그래프)
    # =========================
    daily_stats = (
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total_cost=Sum("cost_krw"),
            total_tokens=Sum("total_tokens"),
            input_tokens=Sum("input_tokens"),
            output_tokens=Sum("output_tokens"),
        )
        .order_by("day")
    )

    daily_map = {d["day"]: d for d in daily_stats}
    range_days = max((end_date - start_date).days + 1, 1)
    daily_labels = []
    daily_costs = []
    daily_total_tokens = []
    daily_input_tokens = []
    daily_output_tokens = []

    for offset in range(range_days):
        day = start_date + timedelta(days=offset)
        data = daily_map.get(day)
        daily_labels.append(day.strftime("%m/%d"))
        daily_costs.append(float(data["total_cost"] or 0) if data else 0)
        daily_total_tokens.append(int(data["total_tokens"] or 0) if data else 0)
        daily_input_tokens.append(int(data["input_tokens"] or 0) if data else 0)
        daily_output_tokens.append(int(data["output_tokens"] or 0) if data else 0)

    total_tokens = int(total_stats.get("total_tokens") or 0)
    total_cost = float(total_stats.get("total_cost") or 0)
    total_count = int(total_stats.get("count") or 0)

    avg_daily_tokens = total_tokens / range_days if range_days else 0
    avg_daily_cost = total_cost / range_days if range_days else 0
    avg_tokens_per_call = total_tokens / total_count if total_count else 0
    avg_cost_per_call = total_cost / total_count if total_count else 0

    peak_day_label = "-"
    peak_day_tokens = 0
    if daily_total_tokens:
        peak_day_tokens = max(daily_total_tokens)
        peak_index = daily_total_tokens.index(peak_day_tokens)
        peak_day_label = (start_date + timedelta(days=peak_index)).strftime("%Y-%m-%d")

    next_month = end_date.month + 1
    next_year = end_date.year
    if next_month == 13:
        next_month = 1
        next_year += 1
    next_month_days = calendar.monthrange(next_year, next_month)[1]
    forecast_next_month_tokens = avg_daily_tokens * next_month_days
    forecast_next_month_cost = avg_daily_cost * next_month_days

    # =========================
    # 📊 모델별 비용
    context = {
        "start_date": start_date,
        "end_date": end_date,
        "total": total_stats,
        "daily_labels": daily_labels,
        "daily_costs": daily_costs,
        "daily_total_tokens": daily_total_tokens,
        "daily_input_tokens": daily_input_tokens,
        "daily_output_tokens": daily_output_tokens,
        "avg_daily_tokens": avg_daily_tokens,
        "avg_daily_cost": avg_daily_cost,
        "avg_tokens_per_call": avg_tokens_per_call,
        "avg_cost_per_call": avg_cost_per_call,
        "peak_day_label": peak_day_label,
        "peak_day_tokens": peak_day_tokens,
        "forecast_next_month_tokens": forecast_next_month_tokens,
        "forecast_next_month_cost": forecast_next_month_cost,
    }
    return render(request, "dashboard/llm_usage_dashboard.html", context)


@dashboard_required
def llm_usage_users(request):
    start_date, end_date = _get_usage_range(request, default_days=30)
    qs = LLMUsageLog.objects.select_related("user").filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    by_user = (
        qs.values("user__username")
        .annotate(
            total_cost=Sum("cost_krw"),
            total_tokens=Sum("total_tokens"),
            input_tokens=Sum("input_tokens"),
            output_tokens=Sum("output_tokens"),
            count=Count("id"),
        )
        .order_by("-total_tokens")
    )

    by_user_list = list(by_user)
    top_users = by_user_list[:10]
    user_labels = [u["user__username"] or "-" for u in top_users]
    user_tokens = [int(u["total_tokens"] or 0) for u in top_users]
    user_costs = [float(u["total_cost"] or 0) for u in top_users]

    total_calls = sum(int(u["count"] or 0) for u in by_user_list)
    total_tokens = sum(int(u["total_tokens"] or 0) for u in by_user_list)
    total_cost = sum(float(u["total_cost"] or 0) for u in by_user_list)
    user_count = len(by_user_list)
    top_user = by_user_list[0] if by_user_list else None

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "by_user": by_user_list,
        "user_labels": user_labels,
        "user_tokens": user_tokens,
        "user_costs": user_costs,
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "user_count": user_count,
        "top_user": top_user,
    }
    return render(request, "dashboard/llm_usage_users.html", context)


@dashboard_required
def llm_usage_models(request):
    start_date, end_date = _get_usage_range(request, default_days=30)
    qs = LLMUsageLog.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    by_model = (
        qs.values("model")
        .annotate(
            total_cost=Sum("cost_krw"),
            total_tokens=Sum("total_tokens"),
            input_tokens=Sum("input_tokens"),
            output_tokens=Sum("output_tokens"),
            count=Count("id"),
        )
        .order_by("-total_tokens")
    )

    by_model_list = list(by_model)
    for row in by_model_list:
        row["model_display"] = _get_model_display(row.get("model"))

    model_labels = [m.get("model_display") or m.get("model") for m in by_model_list]
    model_tokens = [int(m["total_tokens"] or 0) for m in by_model_list]
    model_costs = [float(m["total_cost"] or 0) for m in by_model_list]

    total_calls = sum(int(m["count"] or 0) for m in by_model_list)
    total_tokens = sum(int(m["total_tokens"] or 0) for m in by_model_list)
    total_cost = sum(float(m["total_cost"] or 0) for m in by_model_list)
    model_count = len(by_model_list)
    top_model = by_model_list[0] if by_model_list else None

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "by_model": by_model_list,
        "model_labels": model_labels,
        "model_tokens": model_tokens,
        "model_costs": model_costs,
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "model_count": model_count,
        "top_model": top_model,
    }
    return render(request, "dashboard/llm_usage_models.html", context)


@dashboard_required
def post_usage_stats(request):
    """직원/병원별 여론·후기 월별 통계"""
    has_date_filter = bool(request.GET.get("start") or request.GET.get("end"))
    start_date, end_date = (None, None)
    if has_date_filter:
        start_date, end_date = _get_usage_range(request, default_days=90)
    clinic_id = request.GET.get("clinic") or ""
    assignee_id = request.GET.get("assignee") or ""

    qs = ClinicPost.objects.select_related("clinic", "assignee").annotate(
        posted_at=Coalesce("published_at", "created_at"),
        month=TruncMonth(Coalesce("published_at", "created_at")),
    )

    if has_date_filter and start_date and end_date:
        qs = qs.filter(
            posted_at__date__gte=start_date,
            posted_at__date__lte=end_date,
        )

    if clinic_id:
        qs = qs.filter(clinic_id=clinic_id)
    if assignee_id:
        qs = qs.filter(assignee_id=assignee_id)

    if not has_date_filter:
        date_range = qs.aggregate(
            min_date=Min("posted_at"),
            max_date=Max("posted_at"),
        )
        min_date = date_range.get("min_date")
        max_date = date_range.get("max_date")
        if min_date and max_date:
            start_date = min_date.date()
            end_date = max_date.date()
        else:
            today = timezone.now().date()
            start_date = today
            end_date = today

    by_group = (
        qs.values("assignee_id", "assignee__username", "clinic_id", "clinic__name", "month", "type")
        .annotate(count=Count("id"))
        .order_by("assignee__username", "clinic__name", "month")
    )

    # 월 리스트 생성
    months = []
    cursor = start_date.replace(day=1)
    end_cursor = end_date.replace(day=1)
    while cursor <= end_cursor:
        months.append(cursor)
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    # 집계 구조 구성
    month_keys = [m.strftime("%Y-%m") for m in months]
    rows = {}
    for item in by_group:
        key = (item["assignee_id"], item["clinic_id"])
        row = rows.get(key)
        if not row:
            row = {
                "assignee_id": item["assignee_id"],
                "assignee": item["assignee__username"] or "-",
                "clinic_id": item["clinic_id"],
                "clinic": item["clinic__name"] or "-",
                "months": {mk: {"opinion": 0, "review": 0} for mk in month_keys},
                "total_opinion": 0,
                "total_review": 0,
                "total": 0,
            }
            rows[key] = row

        month_key = item["month"].strftime("%Y-%m") if item["month"] else None
        if month_key and month_key in row["months"]:
            row["months"][month_key][item["type"]] = item["count"]
        if item["type"] == "opinion":
            row["total_opinion"] += item["count"]
        else:
            row["total_review"] += item["count"]
        row["total"] += item["count"]

    rows_list = []
    for row in rows.values():
        row["month_cells"] = [row["months"][mk] for mk in month_keys]
        rows_list.append(row)
    rows_list.sort(key=lambda r: (-r["total"], r["assignee"], r["clinic"]))

    total_opinion = sum(r["total_opinion"] for r in rows_list)
    total_review = sum(r["total_review"] for r in rows_list)
    total_posts = total_opinion + total_review

    # Top clinic / assignee
    clinic_totals = {}
    assignee_totals = {}
    for r in rows_list:
        clinic_totals[r["clinic"]] = clinic_totals.get(r["clinic"], 0) + r["total"]
        assignee_totals[r["assignee"]] = assignee_totals.get(r["assignee"], 0) + r["total"]
    top_clinic = max(clinic_totals.items(), key=lambda x: x[1]) if clinic_totals else ("-", 0)
    top_assignee = max(assignee_totals.items(), key=lambda x: x[1]) if assignee_totals else ("-", 0)

    # 월별 합계
    month_labels = [m.strftime("%Y-%m") for m in months]
    month_opinion = [0 for _ in month_labels]
    month_review = [0 for _ in month_labels]
    month_index = {label: idx for idx, label in enumerate(month_labels)}
    for row in rows_list:
        for label, cell in row["months"].items():
            idx = month_index.get(label)
            if idx is None:
                continue
            month_opinion[idx] += int(cell["opinion"] or 0)
            month_review[idx] += int(cell["review"] or 0)

    # 직원별 합계 (전체) - assignee_id 기준으로 통합
    assignee_map = {}
    role_counts = {}
    excluded_names = {"강미선", "문나래", "홍채이", "admin", "-"}
    assignee_aliases = {
        "차예나매니저": "차예나",
    }
    suffixes = ("매니저", "실장", "팀장", "직원", "담당", "담당자", "관리자")

    def _normalize_assignee_name(name):
        if not name:
            return "-"
        value = str(name).strip()
        value = assignee_aliases.get(value, value)
        # 공백/특수문자 제거 (한글/영문/숫자만 유지)
        value = re.sub(r"[^0-9A-Za-z가-힣]", "", value)
        value = assignee_aliases.get(value, value)
        # 직책 접미사 제거
        for suffix in suffixes:
            if value.endswith(suffix):
                value = value[: -len(suffix)]
                break
        return value or "-"

    def _extract_role(name):
        if not name:
            return ""
        value = str(name).strip()
        value = assignee_aliases.get(value, value)
        # 공백/특수문자 제거
        value = re.sub(r"[^0-9A-Za-z가-힣]", "", value)
        for suffix in suffixes:
            if value.endswith(suffix):
                return suffix
        return ""
    for row in rows_list:
        if row["assignee"] in excluded_names:
            continue
        assignee_id = row["assignee_id"]
        raw_name = row["assignee"] or "-"
        display_name = _normalize_assignee_name(raw_name)
        key = display_name
        role = _extract_role(raw_name)
        if role:
            role_counts.setdefault(key, {})
            role_counts[key][role] = role_counts[key].get(role, 0) + 1
        if key not in assignee_map:
            assignee_map[key] = {
                "id": assignee_id,
                "name": display_name,
                "months": {mk: {"opinion": 0, "review": 0} for mk in month_keys},
            }
        # 이름 갱신 (빈값이면 기존 유지)
        if display_name and assignee_map[key]["name"] == "-":
            assignee_map[key]["name"] = display_name
        for mk in month_keys:
            cell = row["months"].get(mk, {"opinion": 0, "review": 0})
            assignee_map[key]["months"][mk]["opinion"] += int(cell.get("opinion", 0))
            assignee_map[key]["months"][mk]["review"] += int(cell.get("review", 0))

    # 직원별 병원/월별 상세
    assignee_detail_map = {}
    for row in rows_list:
        raw_name = row["assignee"] or "-"
        display_name = _normalize_assignee_name(raw_name)
        if raw_name in excluded_names or display_name in excluded_names:
            continue
        clinic_name = row["clinic"] or "-"
        detail = assignee_detail_map.setdefault(display_name, {"clinics": {}})
        clinic_bucket = detail["clinics"].setdefault(
            clinic_name,
            {
                "name": clinic_name,
                "months": {mk: {"opinion": 0, "review": 0} for mk in month_keys},
                "total_opinion": 0,
                "total_review": 0,
                "total": 0,
            },
        )
        for mk in month_keys:
            cell = row["months"].get(mk, {"opinion": 0, "review": 0})
            clinic_bucket["months"][mk]["opinion"] += int(cell.get("opinion", 0))
            clinic_bucket["months"][mk]["review"] += int(cell.get("review", 0))
        clinic_bucket["total_opinion"] += row["total_opinion"]
        clinic_bucket["total_review"] += row["total_review"]
        clinic_bucket["total"] += row["total"]

    assignee_charts = []
    assignee_ids = [r["assignee_id"] for r in rows_list if r.get("assignee_id")]
    role_label_map = dict(UserProfile.POSITION_CHOICES)
    role_by_user = {
        p["user_id"]: role_label_map.get(p["position"], p["position"])
        for p in UserProfile.objects.filter(user_id__in=assignee_ids).values("user_id", "position")
    }
    for key, data in assignee_map.items():
        opinion_series = [data["months"][mk]["opinion"] for mk in month_keys]
        review_series = [data["months"][mk]["review"] for mk in month_keys]
        opinion_total = sum(opinion_series)
        review_total = sum(review_series)
        role = role_by_user.get(data["id"], "")
        if not role and key in role_counts:
            role = max(role_counts[key].items(), key=lambda x: x[1])[0]
        clinics_payload = []
        detail = assignee_detail_map.get(data["name"], {})
        for clinic in detail.get("clinics", {}).values():
            clinics_payload.append({
                "name": clinic["name"],
                "opinion": [clinic["months"][mk]["opinion"] for mk in month_keys],
                "review": [clinic["months"][mk]["review"] for mk in month_keys],
                "opinion_total": clinic["total_opinion"],
                "review_total": clinic["total_review"],
                "total": clinic["total"],
            })
        clinics_payload.sort(key=lambda r: (-r["total"], r["name"]))
        assignee_charts.append({
            "name": data["name"],
            "role": role,
            "opinion": opinion_series,
            "review": review_series,
            "opinion_total": opinion_total,
            "review_total": review_total,
            "total": opinion_total + review_total,
            "clinics": clinics_payload,
        })
    assignee_charts.sort(key=lambda r: (r["name"] == "-", r["name"]))

    clinics = ClinicGuide.objects.filter(is_active=True).order_by("name")
    assignees = (
        ClinicPost.objects.select_related("assignee")
        .values("assignee_id", "assignee__username")
        .distinct()
        .order_by("assignee__username")
    )

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "months": months,
        "month_keys": month_keys,
        "rows": rows_list,
        "total_columns": 5 + len(months),
        "total_posts": total_posts,
        "total_opinion": total_opinion,
        "total_review": total_review,
        "top_clinic": top_clinic,
        "top_assignee": top_assignee,
        "month_labels": month_labels,
        "month_opinion": month_opinion,
        "month_review": month_review,
        "assignee_charts": assignee_charts,
        "clinics": clinics,
        "assignees": assignees,
        "selected_clinic": clinic_id,
        "selected_assignee": assignee_id,
    }
    return render(request, "dashboard/post_usage_stats.html", context)

@dashboard_required
def export_llm_usage_csv(request):
    response = HttpResponse(
        content_type="text/csv; charset=utf-8-sig"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="llm_usage_{timezone.now().date()}.csv"'
    )

    # ⭐ 핵심: utf-8-sig (BOM 포함)
    writer = csv.writer(response)
    writer.writerow(["날짜", "유저", "모델", "토큰", "비용(원)"])

    logs = LLMUsageLog.objects.select_related("user").order_by("-created_at")

    for log in logs:
        writer.writerow([
            log.created_at.strftime("%Y-%m-%d %H:%M"),
            log.user.username if log.user else "-",
            log.model,
            log.total_tokens,
            int(log.cost_krw),
        ])

    return response

@dashboard_required
def export_llm_usage_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "LLM Usage"

    # 헤더
    headers = ["날짜", "유저", "모델", "토큰", "비용(원)"]
    ws.append(headers)

    logs = LLMUsageLog.objects.select_related("user").order_by("-created_at")

    for log in logs:
        ws.append([
            log.created_at.strftime("%Y-%m-%d %H:%M"),
            log.user.username if log.user else "-",
            log.model,
            log.total_tokens,
            int(log.cost_krw),
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="llm_usage_{timezone.now().date()}.xlsx"'
    )

    wb.save(response)
    return response

# =====================================================
# 서버 설정
# =====================================================

def server_settings(request):
    """서버 설정 페이지"""
    import socket
    import subprocess

    # 현재 서버 IP 정보 가져오기
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "알 수 없음"

    # 최근 접속 로그 (최근 100건)
    recent_logs = AccessLog.objects.all()[:100]

    # 고유 IP 목록 (오늘)
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    today_logs = AccessLog.objects.filter(created_at__date=today)
    unique_ips_today = today_logs.values('ip_address').distinct().count()

    context = {
        "local_ip": local_ip,
        "recent_logs": recent_logs,
        "total_logs": AccessLog.objects.count(),
        "unique_ips_today": unique_ips_today,
    }
    return render(request, "dashboard/server_settings.html", context)


@require_http_methods(["GET"])
def api_firewall_status(request):
    """방화벽 규칙 상태 확인 API"""
    import subprocess

    try:
        # netsh 명령어로 dtlab90 규칙 확인
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=dtlab90'],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='cp949',  # Windows 한글 인코딩
            errors='ignore'
        )

        # 규칙이 존재하면 출력에 "dtlab90"이 포함됨
        rule_exists = 'dtlab90' in result.stdout or result.returncode == 0

        # 더 정확한 확인: "사용" 또는 "Enabled" 체크
        is_enabled = False
        if rule_exists:
            output_lower = result.stdout.lower()
            if '사용' in result.stdout or 'enabled' in output_lower or 'yes' in output_lower:
                is_enabled = True

        return JsonResponse({
            "success": True,
            "rule_exists": rule_exists,
            "is_enabled": is_enabled,
            "status": "open" if (rule_exists and is_enabled) else "closed",
            "rule_name": "dtlab90",
        })

    except subprocess.TimeoutExpired:
        return JsonResponse({
            "success": False,
            "error": "명령어 실행 시간 초과",
            "status": "unknown"
        })
    except FileNotFoundError:
        return JsonResponse({
            "success": False,
            "error": "netsh 명령어를 찾을 수 없습니다",
            "status": "unknown"
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
            "status": "unknown"
        })


@require_http_methods(["GET"])
def api_access_logs(request):
    """접속 로그 목록 API"""
    limit = int(request.GET.get('limit', 50))
    offset = int(request.GET.get('offset', 0))

    logs = AccessLog.objects.all()[offset:offset + limit]

    logs_data = [
        {
            "id": log.id,
            "ip_address": log.ip_address,
            "path": log.path,
            "method": log.method,
            "user_agent": log.user_agent[:100] if log.user_agent else "",
            "created_at": log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        for log in logs
    ]

    return JsonResponse({
        "success": True,
        "logs": logs_data,
        "total": AccessLog.objects.count(),
    })


@require_http_methods(["POST"])
def api_clear_access_logs(request):
    """접속 로그 전체 삭제 API"""
    deleted_count, _ = AccessLog.objects.all().delete()
    return JsonResponse({
        "success": True,
        "deleted_count": deleted_count,
    })


# =====================================================
# Basic Plus - 시리즈 생성 및 스타일 기반 생성
# =====================================================

def review_generate_basic_plus(request):
    """Basic Plus 리뷰 생성 페이지"""
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    return render(request, "dashboard/review_generate_basic_plus.html", {
        "models": models_list,
    })


@require_http_methods(["POST"])
def api_generate_series(request):
    """컨텐츠 시리즈 한번에 생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    user_input = data.get("user_input", "").strip()
    content_types = data.get("content_types", [])
    content_lengths = data.get("content_lengths", {})  # 각 컨텐츠별 글자수
    model = data.get("model", "claude-sonnet-4-5-20250929")
    template_id = data.get("template_id")  # 선택적 템플릿 ID

    # 다양성 설정
    temperature = data.get("temperature", 0.85)
    persona = data.get("persona", {})
    situation = data.get("situation", {})

    if not user_input:
        return JsonResponse({"error": "기본 정보를 입력해주세요."}, status=400)

    if not content_types:
        return JsonResponse({"error": "최소 하나의 컨텐츠를 선택해주세요."}, status=400)

    # 컨텐츠 타입 이름 매핑
    type_names = {
        'question': '고민 & 질문',
        'research': '발품/손품',
        'consultation': '방문상담 후기',
        'day0': '시술 당일 후기',
        'month1': '시술 후 1개월 후기',
        'month2': '시술 후 2개월 후기',
        'month3': '시술 후 3개월 후기',
    }

    type_descriptions = {
        'question': '시술 전 커뮤니티에 올리는 고민/질문글. 아직 시술을 받기 전이라 결과를 모름.',
        'research': '병원 비교, 검색 과정 공유. 여러 병원을 알아보고 비교하는 과정.',
        'consultation': '상담 받고 온 후기. 병원 방문 후 느낌, 상담 내용 공유.',
        'day0': '시술 직후 생생한 후기. 당일의 긴장감, 시술 과정, 직후 상태.',
        'month1': '시술 후 1개월 경과. 회복 과정, 변화 느낌.',
        'month2': '시술 후 2개월 경과. 안정화 단계, 주변 반응.',
        'month3': '시술 후 3개월 경과. 최종 결과, 만족도, 재방문 의향.',
    }

    # 생성할 컨텐츠 목록 (길이 포함)
    content_list = []
    for ct in content_types:
        length = content_lengths.get(ct, 500)
        content_list.append(f"- [{type_names.get(ct, ct)}] ({length}자 내외): {type_descriptions.get(ct, '')}")

    # 페르소나 정보 구성
    persona_desc = ""
    if persona:
        persona_parts = []
        if persona.get("age"):
            persona_parts.append(persona["age"])
        if persona.get("gender"):
            persona_parts.append(persona["gender"])
        if persona.get("job"):
            persona_parts.append(persona["job"])
        if persona.get("personality"):
            persona_parts.append(f"성격: {persona['personality']}")
        if persona.get("tone"):
            persona_parts.append(f"말투: {persona['tone']}")
        if persona.get("experience"):
            persona_parts.append(f"시술 경험: {persona['experience']}")
        if persona_parts:
            persona_desc = f"\n## 글쓴이 페르소나 (반드시 반영)\n" + ", ".join(persona_parts)

    # 상황 변수 정보 구성
    situation_desc = ""
    if situation:
        sit_parts = []
        if situation.get("consult"):
            sit_parts.append(f"상담 분위기: {situation['consult']}")
        if situation.get("pain"):
            sit_parts.append(f"시술 통증: {situation['pain']}")
        if situation.get("downtime"):
            sit_parts.append(f"다운타임: {situation['downtime']}")
        if situation.get("satisfaction"):
            sit_parts.append(f"만족도: {situation['satisfaction']}")
        if situation.get("price"):
            sit_parts.append(f"가격 느낌: {situation['price']}")
        if situation.get("revisit"):
            sit_parts.append(f"재방문 의향: {situation['revisit']}")
        if sit_parts:
            situation_desc = f"\n## 상황 변수 (해당 시점 글에 반영)\n" + "\n".join(sit_parts)

    # DB에서 프롬프트 템플릿 조회
    from apps.data.models import PromptTemplate

    if template_id:
        template = PromptTemplate.objects.filter(pk=template_id, mode='basic_plus').first()
    else:
        template = PromptTemplate.objects.filter(mode='basic_plus', is_default=True).first()

    # 기본 프롬프트 (템플릿이 없는 경우 폴백)
    DEFAULT_BASIC_PLUS_PROMPT = """당신은 실제로 미용 시술을 받는 사람의 관점에서 시간 순서대로 일련의 글을 작성합니다.
한 사람이 시술을 결심하고, 알아보고, 상담받고, 시술받고, 회복하는 전 과정을 자연스럽게 기록합니다.

## 핵심 원칙
1. **일관된 페르소나**: 모든 글에서 동일한 사람의 말투, 성격, 걱정, 기대가 느껴져야 합니다.
2. **시간적 연속성**: 앞선 글에서 언급한 내용(병원명, 원장님, 가격, 경험 등)이 이후 글에 자연스럽게 연결됩니다.
3. **감정의 흐름**: 처음 걱정/기대 → 상담 후 안심 → 시술 당일 긴장 → 회복 과정의 변화
4. **시점 준수**: 각 글은 해당 시점에서만 알 수 있는 정보만 포함. 미래 결과 언급 금지.
5. **자연스러운 문체**: 광고가 아닌 실제 경험담, 카페/커뮤니티 글처럼.

## 표현 다양화 가이드
- 문장 시작 다양하게: "솔직히", "진짜", "근데", "아", "흠", "일단", "뭔가", "사실" 등
- 감탄/추임새: "헐", "오", "와", "대박", "ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "..." 활용
- 불필요한 수식어 빼기: 간결하고 직관적인 표현
- 구어체 표현: "~거든요", "~잖아요", "~같아요", "~더라고요" 자연스럽게
- 개인적 감정: "솔직히 좀 무서웠는데", "은근 기대됨", "약간 후회될뻔" 등
{persona_desc}{situation_desc}

## 사용자 제공 정보
{user_input}

## 생성할 컨텐츠 (순서대로, 지정된 글자수 준수!)
{content_list}

## 출력 형식 (반드시 준수)
각 컨텐츠를 아래 형식으로 구분하여 작성:

[고민 & 질문]
(해당 글자수에 맞는 내용)

=======

[발품/손품]
(해당 글자수에 맞는 내용)

=======

(이하 동일한 형식으로 계속)

## 주의사항
- 각 컨텐츠의 지정된 글자수를 최대한 맞춰주세요
- 구분선은 반드시 ======= (등호 7개 이상) 사용
- 이모지는 적당히 (과하지 않게)
- 자연스러운 구어체, 오타 가능
- 줄바꿈(엔터)은 최소화: 문단 사이는 한 줄만 띄우기. 연속 빈 줄 금지.

지금부터 시리즈를 작성해주세요:"""

    prompt_template = template.content if template else DEFAULT_BASIC_PLUS_PROMPT
    series_prompt = prompt_template.format(
        persona_desc=persona_desc,
        situation_desc=situation_desc,
        user_input=user_input,
        content_list=chr(10).join(content_list)
    )

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        series_prompt = apply_review_type_guard(series_prompt)
        # max_tokens를 8000으로 늘려서 긴 시리즈도 생성 가능
        # temperature 파라미터 추가로 창의성 조절
        result = generate_review_with_prompt_enforced(
            series_prompt,
            model=model,
            max_tokens=8000,
            return_usage=True,
            temperature=temperature
        )
        generated_text = result["text"]
        log_llm_usage(user=request.user, model=model, usage=result)

        # 파싱: ======= 구분자로 분리
        parts = re.split(r'\n=+\n', generated_text)

        series = []
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            # [타입] 형식 추출 시도
            type_match = re.match(r'\[([^\]]+)\]', part)
            if type_match:
                detected_type = type_match.group(1)
                content = part[type_match.end():].strip()
            else:
                detected_type = content_types[i] if i < len(content_types) else f"part_{i}"
                content = part

            # 타입 이름 -> 코드 변환
            type_code = None
            for code, name in type_names.items():
                if code in detected_type.lower() or name in detected_type:
                    type_code = code
                    break

            if not type_code and i < len(content_types):
                type_code = content_types[i]
            elif not type_code:
                type_code = f"content_{i}"

            series.append({
                "type": type_code,
                "content": content,
                "char_count": len(content),
                "title_suggestions": generate_title_suggestions(content, model=model),
            })

        # 생성 리뷰 저장 (Basic+)
        persona_text = _build_persona_text(persona)
        keywords_used = list(content_types)
        saved_ids = []
        for item in series:
            type_label = type_names.get(item["type"], item["type"])
            created = GeneratedReview.objects.create(
                clinic=None,
                persona=None,
                cafe=None,
                doctor_code="",
                doctor_name="",
                procedure=type_label,
                generated_text=item["content"],
                prompt_used=series_prompt,
                model_used=model,
                keywords_used=keywords_used,
                persona_text=persona_text,
                title_suggestions=item.get("title_suggestions") or [],
            )
            saved_ids.append(created.id)
            item["review_id"] = created.id

        # 원화 환산
        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "series": series,
            "saved_ids": saved_ids,
            "prompt": series_prompt,  # 프롬프트도 반환
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def api_generate_reply(request):
    """스타일 기반 댓글 답변 생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    source_text = data.get("source_text", "").strip()
    comment = data.get("comment", "").strip()
    model = data.get("model", "claude-sonnet-4-5-20241022")

    if not source_text:
        return JsonResponse({"error": "원본 글이 필요합니다."}, status=400)

    if not comment:
        return JsonResponse({"error": "답변할 댓글을 입력해주세요."}, status=400)

    reply_prompt = f"""당신은 아래 원본 글을 작성한 사람입니다.
원본 글의 말투, 성격, 경험을 그대로 유지하면서 댓글에 자연스럽게 답변해주세요.

## 원본 글 (이 글을 쓴 사람의 관점 유지)
{source_text}

## 받은 댓글
{comment}

## 답변 작성 원칙
1. 원본 글의 말투와 스타일 유지 (존댓말/반말, 이모지 사용 빈도 등)
2. 실제로 그 경험을 한 사람으로서 구체적으로 답변
3. 자연스럽고 친근한 답변 (광고 느낌 X)
4. 질문에 대해 성실하게 답변하되, 과장하지 않음
5. 적절한 길이 (100~300자 정도)

답변:"""

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        result = generate_review_with_prompt_enforced(reply_prompt, model=model, return_usage=True)
        log_llm_usage(user=request.user, model=model, usage=result)

        return JsonResponse({
            "success": True,
            "reply": result["text"],
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
            }
        })

    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def api_generate_with_style(request):
    """추출된 스타일로 새 글 생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    source_text = data.get("source_text", "").strip()
    prompt = data.get("prompt", "").strip()
    model = data.get("model", "claude-sonnet-4-5-20241022")

    if not source_text:
        return JsonResponse({"error": "스타일 원본이 필요합니다."}, status=400)

    if not prompt:
        return JsonResponse({"error": "생성할 글의 조건을 입력해주세요."}, status=400)

    style_prompt = f"""아래 원본 글의 작성자와 동일한 사람이 새로운 글을 작성합니다.
원본 글의 말투, 표현 방식, 성격, 감정 표현 스타일을 그대로 유지해주세요.

## 원본 글 (스타일 참고)
{source_text}

## 새로 작성할 글의 조건
{prompt}

## 작성 원칙
1. 원본 글과 동일한 사람이 쓴 것처럼 말투/스타일 완벽 유지
2. 원본에서 언급된 병원, 시술 등의 맥락 유지
3. 자연스러운 경험담 형식
4. 적절한 길이 (600~1000자)

새 글:"""

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        result = generate_review_with_prompt_enforced(style_prompt, model=model, return_usage=True)
        log_llm_usage(user=request.user, model=model, usage=result)

        # 원화 환산
        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "content": result["text"],
            "title_suggestions": title_suggestions,
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)


# =====================================================
# 프롬프트 템플릿 관리
# =====================================================

from apps.data.models import PromptTemplate, PromptTemplateVersion


def prompt_template_list(request):
    """프롬프트 템플릿 목록 페이지"""
    templates = PromptTemplate.objects.all()

    # 모드별로 그룹화
    templates_by_mode = {
        'basic': templates.filter(mode='basic'),
        'basic_plus': templates.filter(mode='basic_plus'),
        'pro_header': templates.filter(mode='pro_header'),
        'pro_guidelines': templates.filter(mode='pro_guidelines'),
        'app_gangnam': templates.filter(mode='app_gangnam'),
    }

    context = {
        'templates_by_mode': templates_by_mode,
        'mode_labels': {
            'basic': 'Basic',
            'basic_plus': 'Basic Plus',
            'pro_header': 'Pro - 헤더',
            'pro_guidelines': 'Pro - 가이드라인',
            'app_gangnam': '앱 - 강남언니',
        },
    }
    return render(request, "dashboard/prompt_template_list.html", context)


def prompt_template_edit(request, pk=None):
    """프롬프트 템플릿 생성/수정 페이지"""
    if pk:
        template = get_object_or_404(PromptTemplate, pk=pk)
    else:
        template = None

    if request.method == 'POST':
        mode = request.POST.get('mode', '').strip()
        name = request.POST.get('name', '').strip()
        content = request.POST.get('content', '').strip()
        description = request.POST.get('description', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        change_note = request.POST.get('change_note', '').strip()

        if not mode or not name or not content:
            return render(request, "dashboard/prompt_template_edit.html", {
                "template": template,
                "error": "모드, 이름, 내용은 필수입니다."
            })

        if template:
            # 기존 템플릿 수정 - 버전 이력 저장
            PromptTemplateVersion.objects.create(
                template=template,
                version=template.version,
                content=template.content,
                change_note=change_note or f"v{template.version} 백업",
            )

            template.mode = mode
            template.name = name
            template.content = content
            template.description = description
            template.is_default = is_default
            template.version += 1
            template.save()
        else:
            # 새 템플릿 생성
            template = PromptTemplate.objects.create(
                mode=mode,
                name=name,
                content=content,
                description=description,
                is_default=is_default,
            )

        return render(request, "dashboard/prompt_template_edit.html", {
            "template": template,
            "success": "저장되었습니다."
        })

    # 버전 이력 가져오기
    versions = []
    if template:
        versions = template.versions.all()[:10]

    return render(request, "dashboard/prompt_template_edit.html", {
        "template": template,
        "versions": versions,
    })


@require_http_methods(["GET"])
def api_prompt_templates(request):
    """프롬프트 템플릿 목록 API"""
    mode = request.GET.get('mode')

    if mode:
        templates = PromptTemplate.objects.filter(mode=mode, is_active=True)
    else:
        templates = PromptTemplate.objects.filter(is_active=True)

    data = [
        {
            "id": t.pk,
            "mode": t.mode,
            "mode_display": t.get_mode_display(),
            "name": t.name,
            "description": t.description,
            "content": t.content,
            "is_default": t.is_default,
            "version": t.version,
            "updated_at": t.updated_at.strftime('%Y-%m-%d %H:%M'),
        }
        for t in templates
    ]

    return JsonResponse({"success": True, "templates": data})


@require_http_methods(["GET"])
def api_prompt_template_detail(request, pk):
    """프롬프트 템플릿 상세 API"""
    template = get_object_or_404(PromptTemplate, pk=pk)

    return JsonResponse({
        "success": True,
        "template": {
            "id": template.pk,
            "mode": template.mode,
            "mode_display": template.get_mode_display(),
            "name": template.name,
            "description": template.description,
            "content": template.content,
            "is_default": template.is_default,
            "version": template.version,
            "updated_at": template.updated_at.strftime('%Y-%m-%d %H:%M'),
        }
    })


@require_http_methods(["POST"])
def api_prompt_template_delete(request, pk):
    """프롬프트 템플릿 삭제 API"""
    template = get_object_or_404(PromptTemplate, pk=pk)

    if template.is_default:
        return JsonResponse({"success": False, "error": "기본 템플릿은 삭제할 수 없습니다."}, status=400)

    name = template.name
    template.delete()

    return JsonResponse({"success": True, "message": f"'{name}' 템플릿이 삭제되었습니다."})


@require_http_methods(["POST"])
def api_prompt_template_set_default(request, pk):
    """프롬프트 템플릿 기본 설정 API"""
    template = get_object_or_404(PromptTemplate, pk=pk)
    template.is_default = True
    template.save()  # save()에서 같은 모드의 다른 템플릿 기본 해제

    return JsonResponse({
        "success": True,
        "message": f"'{template.name}'이(가) 기본 템플릿으로 설정되었습니다."
    })


@require_http_methods(["POST"])
def api_prompt_template_toggle(request, pk):
    """프롬프트 템플릿 활성화 토글 API"""
    template = get_object_or_404(PromptTemplate, pk=pk)
    template.is_active = not template.is_active
    template.save()

    return JsonResponse({
        "success": True,
        "is_active": template.is_active,
        "message": f"'{template.name}' {'활성화' if template.is_active else '비활성화'}됨"
    })


@require_http_methods(["GET"])
def api_prompt_template_versions(request, pk):
    """프롬프트 템플릿 버전 이력 API"""
    template = get_object_or_404(PromptTemplate, pk=pk)
    versions = template.versions.all()

    data = [
        {
            "version": v.version,
            "content": v.content,
            "change_note": v.change_note,
            "created_at": v.created_at.strftime('%Y-%m-%d %H:%M'),
        }
        for v in versions
    ]

    return JsonResponse({
        "success": True,
        "template_name": template.name,
        "current_version": template.version,
        "versions": data
    })


@require_http_methods(["POST"])
def api_prompt_template_restore(request, pk, version):
    """프롬프트 템플릿 특정 버전으로 복원 API"""
    template = get_object_or_404(PromptTemplate, pk=pk)
    version_obj = get_object_or_404(PromptTemplateVersion, template=template, version=version)

    # 현재 버전 백업
    PromptTemplateVersion.objects.create(
        template=template,
        version=template.version,
        content=template.content,
        change_note=f"v{version}으로 복원하기 전 백업",
    )

    # 복원
    template.content = version_obj.content
    template.version += 1
    template.save()

    return JsonResponse({
        "success": True,
        "message": f"v{version}으로 복원되었습니다. (현재 버전: v{template.version})"
    })


# =====================================================
# 앱 리뷰 생성 - 강남언니
# =====================================================

def app_review_gangnam(request):
    """강남언니 후기 생성 페이지"""
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    return render(request, "dashboard/app_review_gangnam.html", {
        "models": models_list,
    })


@require_http_methods(["POST"])
def api_generate_gangnam_review(request):
    """강남언니 형식 후기 생성 API (앱 플로우 기반)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    # 필수 필드 검증
    hospital_name = data.get("hospital_name", "").strip()
    procedure_type = data.get("procedure_type", "").strip()

    if not hospital_name or not procedure_type:
        return JsonResponse({"error": "병원명과 시술 종류는 필수입니다."}, status=400)

    # 입력 데이터 정리
    procedure_detail = data.get("procedure_detail", "")
    doctor_name = data.get("doctor_name", "")
    anesthesia = data.get("anesthesia", "")
    price_range = data.get("price_range", "")

    # 날짜 처리
    from datetime import datetime, timedelta
    import random

    procedure_date_input = data.get("procedure_date", "")
    write_date_input = data.get("write_date", "")

    # 작성일자: 비어있으면 오늘
    if write_date_input:
        write_date = datetime.strptime(write_date_input, "%Y-%m-%d")
    else:
        write_date = datetime.now()

    # 시술일자: 비어있으면 작성일 기준 7~30일 전 랜덤
    if procedure_date_input:
        procedure_date = datetime.strptime(procedure_date_input, "%Y-%m-%d")
    else:
        days_ago = random.randint(7, 30)
        procedure_date = write_date - timedelta(days=days_ago)

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
    model = data.get("model", "claude-sonnet-4-5-20250929")
    temperature = data.get("temperature", 0.85)

    # 만족도에 따른 별점 설정
    rating_map = {
        "매우 만족": 5.0,
        "만족": 4.5,
        "보통": 3.5,
        "약간 아쉬움": 3.0,
    }
    rating = rating_map.get(satisfaction_level, 4.5)

    # 태그 목록 (프롬프트에 포함)
    reason_tags = "합리적 가격, 높은 평점, 후기 내용, 의사 전문성, 병원 인지도, 병원 위치, 재방문, 지인 추천, 병원 시설, 최신 기기, 앱결제, 포인트 사용, 기타"
    good_tags = "빠른 효과, 결과 만족, 부작용 없음, 적은 통증, 흉터 없음, 빠른 회복, 일상 생활 가능, 꼼꼼한 시술, 애프터케어, 기타, 없어요"
    bad_tags = "효과 없음, 결과 불만족, 부작용 있음, 시술 중 통증, 시술 후 통증, 흉터 남음, 더딘 회복, 일상 복귀 시간 필요, 성의 없는 시술, 애프터케어 부족, 기타, 없어요"

    # DB에서 프롬프트 템플릿 가져오기
    from apps.data.models import PromptTemplate
    try:
        template = PromptTemplate.objects.filter(mode='app_gangnam', is_active=True, is_default=True).first()
        if not template:
            template = PromptTemplate.objects.filter(mode='app_gangnam', is_active=True).first()
    except Exception:
        template = None

    # 프롬프트 변수 준비
    prompt_vars = {
        'persona_age': persona_age,
        'persona_gender': persona_gender,
        'persona_tone': persona_tone,
        'emoji_usage': emoji_usage,
        'hospital_name': hospital_name,
        'procedure_type': procedure_type,
        'procedure_detail_line': f'- 시술 상세: {procedure_detail}' if procedure_detail else '',
        'doctor_line': f'- 담당 의사: {doctor_name}' if doctor_name else '',
        'anesthesia_line': f'- 마취 방법: {anesthesia}' if anesthesia else '',
        'price_line': f'- 가격대: {price_range}' if price_range else '',
        'procedure_date': procedure_date_str,
        'write_date': write_date_str,
        'days_since': days_since,
        'satisfaction_level': satisfaction_level,
        'before_concern_line': f'- 시술 전 고민/계기: {before_concern}' if before_concern else '',
        'good_points_line': f'- 강조할 좋은 점: {good_points_hint}' if good_points_hint else '',
        'bad_points_line': f'- 아쉬운 점: {bad_points_hint}' if bad_points_hint else '',
        'reason_tags': reason_tags,
        'good_tags': good_tags,
        'bad_tags': bad_tags,
        'rating': rating,
        'forbidden_line': f'8. 다음 표현은 절대 사용 금지: {forbidden_expressions}' if forbidden_expressions else '',
    }

    # 프롬프트 생성
    if template:
        prompt = template.content.format(**prompt_vars)
    else:
        # 템플릿이 없으면 기본 프롬프트 사용
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

    result = None
    try:
        from apps.ml.services.llm_service import generate_review_with_prompt_enforced
        prompt = apply_review_type_guard(prompt)
        result = generate_review_with_prompt_enforced(prompt, model=model, return_usage=True, temperature=temperature)

        # JSON 파싱
        response_text = result["text"].strip()
        # JSON 블록 추출 (```json ... ``` 형식 대응)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(response_text)

        # 원화 환산
        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "procedure_date": procedure_date_str,
            "write_date": write_date_str,
            "before_worry": parsed.get("before_worry", ""),
            "reason_tags": parsed.get("reason_tags", []),
            "result_review": parsed.get("result_review", ""),
            "good_tags": parsed.get("good_tags", []),
            "bad_tags": parsed.get("bad_tags", ["없어요"]),
            "bad_reason": parsed.get("bad_reason", ""),
            "rating": parsed.get("rating", rating),
            "additional": parsed.get("additional", ""),
            "title_suggestions": title_suggestions,
            "model_used": model,
            "model_label": _get_model_display(model),
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except json.JSONDecodeError as e:
        return JsonResponse({
            "error": f"응답 파싱 실패: {str(e)}",
            "raw_response": result.get("text", "") if result else ""
        }, status=500)
    except Exception as e:
        return JsonResponse({"error": f"생성 실패: {str(e)}"}, status=500)
