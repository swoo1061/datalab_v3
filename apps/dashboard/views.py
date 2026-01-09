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

import csv
from openpyxl import Workbook
from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from apps.data.models import (
    Review, Campaign, ImageAsset,
    Persona, CafeProfile, ClinicGuide, GeneratedReview, ContentTypeProfile, LLMUsageLog, ClinicDoctor, ClinicPrice
)
from apps.ml.services.clinic_normalizer import normalize_clinic_payload
from apps.ml.services.clinic_md_llm import parse_clinic_md_with_llm
from apps.ml.services.llm_service import generate_review, generate_review_advanced
from apps.ml.services.prompt_generator import build_review_prompt, build_prompt_from_models
from apps.ml.services.clinic_parser import parse_clinic_content


# =====================================================
# 기존 뷰 (호환성 유지)
# =====================================================

@dashboard_required
def is_staff(user):
    return user.groups.filter(name='staff').exists() or user.is_superuser

@dashboard_required
def index(request):
    """대시보드 홈"""
    total_reviews = Review.objects.count()
    generated_count = GeneratedReview.objects.count()
    clinics_count = ClinicGuide.objects.filter(is_active=True).count()
    
    recent_generated = GeneratedReview.objects.all()[:5]
    campaigns = Campaign.objects.all()[:6]
    
    context = {
        "total_reviews": total_reviews,
        "generated_reviews": generated_count,
        "clinics_count": clinics_count,
        "model_version": "v2.0",
        "campaigns": campaigns,
        "recent_generated": recent_generated,
    }
    return render(request, "dashboard/index.html", context)

@dashboard_required
def upload_view(request):
    return render(request, "dashboard/upload.html")

@dashboard_required
def review_list(request):
    reviews = Review.objects.all().order_by("-created_at")[:200]
    return render(request, "dashboard/review_list.html", {"reviews": reviews})

@dashboard_required
def review_detail(request, pk):
    review = get_object_or_404(Review, pk=pk)
    return render(request, "dashboard/review_detail.html", {"r": review})

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
    return JsonResponse({"review": generated, "review_id": rev.id})

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

    base_prompt = template.content if template else DEFAULT_BASIC_PROMPT
    prompt = base_prompt.format(user_input=user_input)

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt
        from apps.ml.services.usage_logger import log_llm_usage

        # 🔥 LLM 호출
        result = generate_review_with_prompt(
            prompt,
            model=model,
            return_usage=True
        )
        review_text = result["text"]

        # ✅ STEP 3 핵심: 사용량 로그 기록
        log_llm_usage(
            user=request.user,
            model=model,
            usage=result
        )

        # DB 저장
        generated_review = GeneratedReview.objects.create(
            generated_text=review_text,
            prompt_used=prompt,
        )

        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "review_id": generated_review.id,
            "review": review_text,
            "char_count": len(review_text),
            "model_used": model,
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

        # 리뷰 생성 (선택된 모델 사용)
        from apps.ml.services.llm_service import generate_review_with_prompt
        review_text = generate_review_with_prompt(prompt, model=model)

        # DB 저장
        doctor_name = ""
        if clinic and doctor_code:
            doctor = clinic.get_doctor_by_code(doctor_code)
            doctor_name = doctor.get('name', '') if doctor else ''

        generated_review = GeneratedReview.objects.create(
            clinic=clinic,
            persona=persona,
            cafe=cafe,
            doctor_code=doctor_code or "",
            doctor_name=doctor_name,
            procedure=procedure or "",
            generated_text=review_text,
            prompt_used=prompt,
        )

        return JsonResponse({
            "success": True,
            "review_id": generated_review.id,
            "review": review_text,
            "prompt_preview": prompt,  # 전체 프롬프트 전송
            "char_count": len(review_text),
            "model_used": model,
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
        )

        return JsonResponse({
            "success": True,
            "review_id": new_review.id,
            "review": new_text,
            "char_count": len(new_text),
            "model_used": model,
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
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(prompt, model=model, return_usage=True)
        review_text = result["text"]

        # DB 저장
        generated_review = GeneratedReview.objects.create(
            generated_text=review_text,
            prompt_used=prompt,
        )

        # 원화 환산 (1 USD = 약 1,450 KRW)
        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "review_id": generated_review.id,
            "review": review_text,
            "char_count": len(review_text),
            "model_used": model,
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
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
    reviews = GeneratedReview.objects.select_related('clinic', 'persona', 'cafe').all()[:100]
    return render(request, "dashboard/generated_review_list.html", {"reviews": reviews})

@dashboard_required
def generated_review_detail(request, pk):
    """생성된 리뷰 상세"""
    review = get_object_or_404(GeneratedReview, pk=pk)
    return render(request, "dashboard/generated_review_detail.html", {"review": review})

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
    today = timezone.now().date()
    month_start = today.replace(day=1)
    start_date = today - timedelta(days=14)

    qs = LLMUsageLog.objects.select_related("user")

    # =========================
    # 오늘 통계
    # =========================
    today_stats = qs.filter(created_at__date=today).aggregate(
        total_cost=Sum("cost_krw"),
        total_tokens=Sum("total_tokens"),
        count=Count("id"),
    )

    # =========================
    # 이번 달 통계
    # =========================
    month_stats = qs.filter(created_at__date__gte=month_start).aggregate(
        total_cost=Sum("cost_krw"),
        total_tokens=Sum("total_tokens"),
        count=Count("id"),
    )

    # =========================
    # 📈 날짜별 비용 (그래프)
    # =========================
    daily_stats = (
        qs.filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total_cost=Sum("cost_krw"))
        .order_by("day")
    )

    daily_labels = [d["day"].strftime("%m/%d") for d in daily_stats]
    daily_costs = [float(d["total_cost"] or 0) for d in daily_stats]

    # =========================
    # 📊 모델별 비용
    # =========================
    by_model = (
        qs.values("model")
        .annotate(
            total_cost=Sum("cost_krw"),
            total_tokens=Sum("total_tokens"),
            count=Count("id"),
        )
        .order_by("-total_cost")
    )

    model_labels = [m["model"] for m in by_model]
    model_costs = [float(m["total_cost"] or 0) for m in by_model]

    # =========================
    # 유저별 비용 (표용)
    # =========================
    by_user = (
        qs.values("user__username")
        .annotate(
            total_cost=Sum("cost_krw"),
            total_tokens=Sum("total_tokens"),
            count=Count("id"),
        )
        .order_by("-total_cost")
    )

    context = {
        # 요약
        "today": today_stats,
        "month": month_stats,

        # 표
        "by_model": by_model,
        "by_user": by_user,

        # 그래프
        "daily_labels": daily_labels,
        "daily_costs": daily_costs,
        "model_labels": model_labels,
        "model_costs": model_costs,
    }
    return render(request, "dashboard/llm_usage_dashboard.html", context)

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
        from apps.ml.services.llm_service import generate_review_with_prompt
        # max_tokens를 8000으로 늘려서 긴 시리즈도 생성 가능
        # temperature 파라미터 추가로 창의성 조절
        result = generate_review_with_prompt(
            series_prompt,
            model=model,
            max_tokens=8000,
            return_usage=True,
            temperature=temperature
        )
        generated_text = result["text"]

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
            })

        # 원화 환산
        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "series": series,
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
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(reply_prompt, model=model, return_usage=True)

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
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(style_prompt, model=model, return_usage=True)

        # 원화 환산
        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "content": result["text"],
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
    }

    context = {
        'templates_by_mode': templates_by_mode,
        'mode_labels': {
            'basic': 'Basic',
            'basic_plus': 'Basic Plus',
            'pro_header': 'Pro - 헤더',
            'pro_guidelines': 'Pro - 가이드라인',
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
