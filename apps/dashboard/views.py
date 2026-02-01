"""
대시보드 뷰 - 리뷰 생성 시스템 v2
"""
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import re

from apps.data.models import (
    Review, Campaign, ImageAsset,
    Persona, CafeProfile, ClinicGuide, GeneratedReview, ContentTypeProfile, AccessLog,
    ProcedureInfo, MultiSeriesBatch, MultiSeriesItem
)
from apps.ml.services.llm_service import generate_review, generate_review_advanced
from apps.ml.services.prompt_generator import build_review_prompt, build_prompt_from_models
from apps.ml.services.clinic_parser import parse_clinic_content


# =====================================================
# 기존 뷰 (호환성 유지)
# =====================================================

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


def upload_view(request):
    return render(request, "dashboard/upload.html")


def review_list(request):
    reviews = Review.objects.all().order_by("-created_at")[:200]
    return render(request, "dashboard/review_list.html", {"reviews": reviews})


def review_detail(request, pk):
    review = get_object_or_404(Review, pk=pk)
    return render(request, "dashboard/review_detail.html", {"r": review})


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


def image_browser(request):
    images = ImageAsset.objects.all().order_by("-created_at")[:200]
    return render(request, "dashboard/image_browser.html", {"images": images})


# =====================================================
# 새로운 리뷰 생성 시스템 v2
# =====================================================

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

## 주의사항
- 위 정보에 없는 내용은 자연스럽게 생략
- 병원명, 원장님, 시술명이 있으면 자연스럽게 포함
- 지정된 페르소나가 있으면 해당 말투와 관점 반영
- 추가 가이드가 있으면 반드시 준수

자연스러운 후기를 작성해주세요:"""

    base_prompt = template.content if template else DEFAULT_BASIC_PROMPT
    prompt = base_prompt.format(user_input=user_input)

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
            "prompt_used": prompt,
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


@require_http_methods(["GET"])
def api_clinic_doctors(request, clinic_id):
    """특정 병원의 의료진 목록 API"""
    clinic = get_object_or_404(ClinicGuide, pk=clinic_id)
    return JsonResponse({
        "doctors": clinic.doctors,
        "consultants": clinic.consultants,
    })


@require_http_methods(["GET"])
def api_clinic_procedures(request, clinic_id, doctor_code):
    """특정 의료진의 시술 목록 API"""
    clinic = get_object_or_404(ClinicGuide, pk=clinic_id)
    procedures = clinic.get_procedures_by_doctor(doctor_code)
    return JsonResponse({"procedures": procedures})


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

def generated_review_list(request):
    """생성된 리뷰 목록"""
    reviews = GeneratedReview.objects.select_related('clinic', 'persona', 'cafe').all()[:100]
    return render(request, "dashboard/generated_review_list.html", {"reviews": reviews})


def generated_review_detail(request, pk):
    """생성된 리뷰 상세"""
    review = get_object_or_404(GeneratedReview, pk=pk)
    return render(request, "dashboard/generated_review_detail.html", {"review": review})


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

def clinic_list(request):
    """병원 가이드 목록"""
    clinics = ClinicGuide.objects.all().order_by('-created_at')
    return render(request, "dashboard/clinic_list.html", {"clinics": clinics})


def clinic_detail(request, pk):
    """병원 가이드 상세"""
    clinic = get_object_or_404(ClinicGuide, pk=pk)
    return render(request, "dashboard/clinic_detail.html", {"clinic": clinic})


@require_http_methods(["POST"])
def api_import_clinic_md(request):
    """MD 파일로 병원 가이드 임포트"""
    md_content = request.POST.get("md_content")
    clinic_name = request.POST.get("clinic_name")
    
    if not md_content:
        return JsonResponse({"error": "md_content는 필수입니다."}, status=400)
    
    try:
        # 파싱
        data = parse_clinic_content(md_content)
        
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


def clinic_import(request):
    """병원 가이드 MD 임포트 페이지"""
    if request.method == 'GET':
        return render(request, "dashboard/clinic_import.html")

    # POST 처리는 api_import_clinic_md에서
    return api_import_clinic_md(request)


@require_http_methods(["POST"])
def api_clinic_delete(request, pk):
    """병원 가이드 삭제"""
    clinic = get_object_or_404(ClinicGuide, pk=pk)
    clinic.delete()
    return JsonResponse({"success": True})


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

def style_analyzer(request):
    """스타일 분석 페이지"""
    personas = Persona.objects.filter(is_active=True)
    cafes = CafeProfile.objects.filter(is_active=True)
    
    return render(request, "dashboard/style_analyzer.html", {
        "personas": personas,
        "cafes": cafes,
    })


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

def persona_list(request):
    """페르소나 목록"""
    personas = Persona.objects.all().order_by('-is_active', '-created_at')
    return render(request, "dashboard/persona_list.html", {"personas": personas})


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


@require_http_methods(["POST"])
def api_persona_delete(request, pk):
    """페르소나 삭제 API"""
    persona = get_object_or_404(Persona, pk=pk)
    name = persona.name
    persona.delete()
    return JsonResponse({"success": True, "message": f"'{name}' 페르소나가 삭제되었습니다."})


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

def cafe_list(request):
    """카페 프로필 목록"""
    cafes = CafeProfile.objects.all().order_by('-is_active', '-created_at')
    return render(request, "dashboard/cafe_list.html", {"cafes": cafes})


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


@require_http_methods(["POST"])
def api_cafe_delete(request, pk):
    """카페 프로필 삭제 API"""
    cafe = get_object_or_404(CafeProfile, pk=pk)
    name = cafe.name
    cafe.delete()
    return JsonResponse({"success": True, "message": f"'{name}' 카페 프로필이 삭제되었습니다."})


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


@require_http_methods(["GET"])
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

def content_type_list(request):
    """컨텐츠 타입 목록"""
    content_types = ContentTypeProfile.objects.all()
    return render(request, "dashboard/content_type_list.html", {"content_types": content_types})


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


@require_http_methods(["POST"])
def api_content_type_delete(request, pk):
    """컨텐츠 타입 삭제"""
    content_type = get_object_or_404(ContentTypeProfile, pk=pk)
    content_type.delete()
    return JsonResponse({"success": True})


@require_http_methods(["POST"])
def api_content_type_toggle(request, pk):
    """컨텐츠 타입 활성화/비활성화"""
    content_type = get_object_or_404(ContentTypeProfile, pk=pk)
    content_type.is_active = not content_type.is_active
    content_type.save()
    return JsonResponse({"success": True, "is_active": content_type.is_active})


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
        'week1': '시술 후 1주일 후기',
        'week2': '시술 후 2주일 후기',
        'week3': '시술 후 3주일 후기',
        'month1': '시술 후 1개월 후기',
        'month2': '시술 후 2개월 후기',
        'month3': '시술 후 3개월 후기',
        'title': '제목',
    }

    type_descriptions = {
        'question': '시술 전 커뮤니티에 올리는 고민/질문글. 아직 시술을 받기 전이라 결과를 모름.',
        'research': '병원 비교, 검색 과정 공유. 여러 병원을 알아보고 비교하는 과정.',
        'consultation': '상담 받고 온 후기. 병원 방문 후 느낌, 상담 내용 공유.',
        'day0': '시술 직후 생생한 후기. 당일의 긴장감, 시술 과정, 직후 상태.',
        'week1': '시술 후 1주일 경과. 초기 회복 단계, 붓기/멍 변화, 일상 복귀.',
        'week2': '시술 후 2주일 경과. 회복 중반, 효과 나타나기 시작.',
        'week3': '시술 후 3주일 경과. 거의 회복, 효과 안정화 진행중.',
        'month1': '시술 후 1개월 경과. 회복 완료, 본격적인 효과 체감.',
        'month2': '시술 후 2개월 경과. 안정화 단계, 주변 반응.',
        'month3': '시술 후 3개월 경과. 최종 결과, 만족도, 재방문 의향.',
        'title': '카페/블로그에 올릴 제목. 클릭을 유도하면서 자연스러운 제목.',
    }

    # 생성할 컨텐츠 목록 (길이 포함)
    content_list = []
    for ct in content_types:
        length = content_lengths.get(ct, 500)
        # 제목은 개수로 처리
        if ct == 'title':
            content_list.append(f"- [{type_names.get(ct, ct)}] ({length}개): {type_descriptions.get(ct, '')}")
        else:
            content_list.append(f"- [{type_names.get(ct, ct)}] ({length}자 내외): {type_descriptions.get(ct, '')}")

    # 페르소나 정보 구성 ("미지정"인 항목은 제외)
    persona_desc = ""
    if persona:
        persona_parts = []
        if persona.get("age") and persona["age"] != "미지정":
            persona_parts.append(persona["age"])
        if persona.get("gender") and persona["gender"] != "미지정":
            persona_parts.append(persona["gender"])
        if persona.get("job") and persona["job"] != "미지정":
            persona_parts.append(persona["job"])
        if persona.get("personality") and persona["personality"] != "미지정":
            persona_parts.append(f"성격: {persona['personality']}")
        if persona.get("tone") and persona["tone"] != "미지정":
            persona_parts.append(f"말투: {persona['tone']}")
        if persona.get("experience") and persona["experience"] != "미지정":
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
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(prompt, model=model, return_usage=True, temperature=temperature)

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


# =====================================================
# Basic Multi
# =====================================================

def review_generate_basic_multi(request):
    """Basic Multi 리뷰 생성 페이지"""
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

    batches = MultiSeriesBatch.objects.all()[:20]

    return render(request, "dashboard/review_generate_basic_multi.html", {
        "models": models_list,
        "batches": batches,
    })


@require_http_methods(["POST"])
def api_generate_multi_series(request):
    """단일 시리즈 + 제목 생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    user_input = data.get("user_input", "").strip()
    procedure_id = data.get("procedure_id")
    content_types = data.get("content_types", [])
    content_lengths = data.get("content_lengths", {})
    model = data.get("model", "claude-sonnet-4-5-20250929")
    template_id = data.get("template_id")
    temperature = data.get("temperature", 0.85)
    persona = data.get("persona", {})
    situation = data.get("situation", {})

    if not user_input:
        return JsonResponse({"error": "기본 정보를 입력해주세요."}, status=400)
    if not content_types:
        return JsonResponse({"error": "최소 하나의 컨텐츠를 선택해주세요."}, status=400)

    # 시술 정보 자동 주입
    procedure_desc = ""
    if procedure_id:
        proc = ProcedureInfo.objects.filter(pk=procedure_id, is_active=True).first()
        if proc:
            proc_parts = [f"시술명: {proc.name}"]
            if proc.description:
                proc_parts.append(f"시술 설명: {proc.description}")
            if proc.pain_level:
                proc_parts.append(f"통증 레벨: {proc.get_pain_level_display()}")
            if proc.recovery_time:
                proc_parts.append(f"회복 기간: {proc.recovery_time}")
            if proc.typical_results:
                proc_parts.append(f"일반적 결과: {proc.typical_results}")
            if proc.common_side_effects:
                proc_parts.append(f"일반적 부작용: {', '.join(proc.common_side_effects)}")
            if proc.precautions:
                proc_parts.append(f"주의사항: {', '.join(proc.precautions)}")
            if proc.price_range:
                proc_parts.append(f"가격 범위: {proc.price_range}")
            if proc.duration:
                proc_parts.append(f"시술 시간: {proc.duration}")
            if proc.anesthesia_type:
                proc_parts.append(f"마취 방법: {proc.anesthesia_type}")
            if proc.sessions_recommended:
                proc_parts.append(f"권장 회차: {proc.sessions_recommended}")
            procedure_desc = "\n## 시술 정보 (자연스럽게 반영)\n" + "\n".join(proc_parts)

            # 체험 지식 DB 주입
            if proc.knowledge_base:
                kb = proc.knowledge_base
                kb_parts = []
                if kb.get("sensory"):
                    sensory = kb["sensory"]
                    if isinstance(sensory, dict):
                        for phase, items in sensory.items():
                            if isinstance(items, list):
                                kb_parts.append(f"  [{phase}] " + ", ".join(items))
                    elif isinstance(sensory, list):
                        kb_parts.append("  " + ", ".join(sensory))
                if kb.get("emotional_journey"):
                    ej = kb["emotional_journey"]
                    if isinstance(ej, dict):
                        for phase, items in ej.items():
                            if isinstance(items, list):
                                kb_parts.append(f"  감정({phase}): " + ", ".join(items))
                            elif isinstance(items, str):
                                kb_parts.append(f"  감정({phase}): {items}")
                if kb.get("real_expressions") and isinstance(kb["real_expressions"], list):
                    kb_parts.append("  커뮤니티 표현: " + ", ".join(kb["real_expressions"][:10]))
                if kb.get("unexpected") and isinstance(kb["unexpected"], list):
                    kb_parts.append("  예상 못한 점: " + ", ".join(kb["unexpected"][:5]))
                if kb.get("detail_points") and isinstance(kb["detail_points"], list):
                    kb_parts.append("  디테일 포인트: " + ", ".join(kb["detail_points"][:10]))
                if kb.get("community_tips") and isinstance(kb["community_tips"], list):
                    kb_parts.append("  커뮤니티 팁: " + ", ".join(kb["community_tips"][:5]))
                if kb_parts:
                    procedure_desc += "\n\n## 체험 지식 (자연스럽게 활용 - 전부 쓸 필요 없음, 해당 시점에 맞는 것만)\n" + "\n".join(kb_parts)

    type_names = {
        'question': '고민 & 질문',
        'research': '발품/손품',
        'consultation': '방문상담 후기',
        'day0': '시술 당일 후기',
        'week1': '시술 후 1주일 후기',
        'week2': '시술 후 2주일 후기',
        'week3': '시술 후 3주일 후기',
        'month1': '시술 후 1개월 후기',
        'month2': '시술 후 2개월 후기',
        'month3': '시술 후 3개월 후기',
        'title': '제목',
    }

    type_descriptions = {
        'question': '시술 전 커뮤니티에 올리는 고민/질문글. 아직 시술을 받기 전이라 결과를 모름.',
        'research': '병원 비교, 검색 과정 공유. 여러 병원을 알아보고 비교하는 과정.',
        'consultation': '상담 받고 온 후기. 병원 방문 후 느낌, 상담 내용 공유.',
        'day0': '시술 직후 생생한 후기. 당일의 긴장감, 시술 과정, 직후 상태.',
        'week1': '시술 후 1주일 경과. 초기 회복 단계, 붓기/멍 변화, 일상 복귀.',
        'week2': '시술 후 2주일 경과. 회복 중반, 효과 나타나기 시작.',
        'week3': '시술 후 3주일 경과. 거의 회복, 효과 안정화 진행중.',
        'month1': '시술 후 1개월 경과. 회복 완료, 본격적인 효과 체감.',
        'month2': '시술 후 2개월 경과. 안정화 단계, 주변 반응.',
        'month3': '시술 후 3개월 경과. 최종 결과, 만족도, 재방문 의향.',
        'title': '카페/블로그에 올릴 제목. 클릭을 유도하면서 자연스러운 제목.',
    }

    content_list = []
    for ct in content_types:
        length = content_lengths.get(ct, 500)
        # 제목은 개수로 처리
        if ct == 'title':
            content_list.append(f"- [{type_names.get(ct, ct)}] ({length}개): {type_descriptions.get(ct, '')}")
        else:
            content_list.append(f"- [{type_names.get(ct, ct)}] ({length}자 내외): {type_descriptions.get(ct, '')}")

    # 페르소나 정보 ("미지정"인 항목은 제외)
    persona_desc = ""
    if persona:
        persona_parts = []
        if persona.get("age") and persona["age"] != "미지정":
            persona_parts.append(persona["age"])
        if persona.get("gender") and persona["gender"] != "미지정":
            persona_parts.append(persona["gender"])
        if persona.get("job") and persona["job"] != "미지정":
            persona_parts.append(persona["job"])
        if persona.get("personality") and persona["personality"] != "미지정":
            persona_parts.append(f"성격: {persona['personality']}")
        if persona.get("tone") and persona["tone"] != "미지정":
            persona_parts.append(f"말투: {persona['tone']}")
        if persona.get("experience") and persona["experience"] != "미지정":
            persona_parts.append(f"시술 경험: {persona['experience']}")
        if persona_parts:
            persona_desc = f"\n## 글쓴이 페르소나 (반드시 반영)\n" + ", ".join(persona_parts)

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

    # DB 프롬프트 템플릿
    from apps.data.models import PromptTemplate
    if template_id:
        template = PromptTemplate.objects.filter(pk=template_id, mode='basic_multi').first()
    else:
        template = PromptTemplate.objects.filter(mode='basic_multi', is_default=True).first()

    DEFAULT_MULTI_PROMPT = """당신은 실제로 미용 시술을 받는 사람의 관점에서 시간 순서대로 일련의 글을 작성합니다.
한 사람이 시술을 결심하고, 알아보고, 상담받고, 시술받고, 회복하는 전 과정을 자연스럽게 기록합니다.

## 핵심 원칙
1. **일관된 페르소나**: 모든 글에서 동일한 사람의 말투, 성격, 걱정, 기대가 느껴져야 합니다.
2. **시간적 연속성**: 앞선 글에서 언급한 내용이 이후 글에 자연스럽게 연결됩니다.
3. **감정의 흐름**: 처음 걱정/기대 → 상담 후 안심 → 시술 당일 긴장 → 회복 과정의 변화
4. **시점 준수**: 각 글은 해당 시점에서만 알 수 있는 정보만 포함. 미래 결과 언급 금지.
5. **자연스러운 문체**: 광고가 아닌 실제 경험담, 카페/커뮤니티 글처럼.

## AI 탐지 방지 원칙
- 같은 문장 구조 반복 금지 (주어+서술어 패턴 다양화)
- "~것 같아요", "~한 것 같습니다" 같은 AI 전형적 표현 최소화
- 단문 위주, 때로는 비문/줄임말 허용 ("걍", "좀", "넘")
- 과한 논리적 연결 (따라서, 그러므로, 결과적으로) 금지
- 자연스러운 오타/탈자 가능 (단, 과하지 않게)
- 감정 표현이 갑자기 바뀌는 것도 자연스러움

## 표현 다양화 가이드
- 문장 시작 다양하게: "솔직히", "진짜", "근데", "아", "흠", "일단", "뭔가", "사실" 등
- 감탄/추임새: "헐", "오", "와", "대박", "ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "..." 활용
- 불필요한 수식어 빼기: 간결하고 직관적인 표현
- 구어체 표현: "~거든요", "~잖아요", "~같아요", "~더라고요" 자연스럽게
- 개인적 감정: "솔직히 좀 무서웠는데", "은근 기대됨", "약간 후회될뻔" 등
{procedure_desc}{persona_desc}{situation_desc}

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

    prompt_template = template.content if template else DEFAULT_MULTI_PROMPT
    series_prompt = prompt_template.format(
        procedure_desc=procedure_desc,
        persona_desc=persona_desc,
        situation_desc=situation_desc,
        user_input=user_input,
        content_list=chr(10).join(content_list)
    )

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(
            series_prompt,
            model=model,
            max_tokens=8000,
            return_usage=True,
            temperature=temperature
        )
        generated_text = result["text"]

        # 파싱
        parts = re.split(r'\n=+\n', generated_text)
        series = []
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            type_match = re.match(r'\[([^\]]+)\]', part)
            if type_match:
                detected_type = type_match.group(1)
                content = part[type_match.end():].strip()
            else:
                detected_type = content_types[i] if i < len(content_types) else f"part_{i}"
                content = part

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

        # 제목 생성
        titles = _generate_multi_titles(series, model, type_names)

        # 시리즈에 제목 정보 추가
        for i, s in enumerate(series):
            s["titles"] = titles.get(i, [])

        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "series": series,
            "prompt": series_prompt,
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except Exception as e:
        return JsonResponse({"error": f"시리즈 생성 실패: {str(e)}"}, status=500)


def _generate_multi_titles(series, model, type_names):
    """시리즈 각 피스별 제목 3개 생성"""
    from apps.data.models import PromptTemplate

    template = PromptTemplate.objects.filter(mode='basic_multi_title', is_default=True).first()

    pieces_desc = []
    for i, s in enumerate(series):
        type_label = type_names.get(s["type"], s["type"])
        preview = s["content"][:100]
        pieces_desc.append(f"피스 {i}: [{type_label}] {preview}...")

    DEFAULT_TITLE_PROMPT = """아래 각 피스에 대해 카페/커뮤니티에 올리기 좋은 자연스러운 제목을 3개씩 추천해주세요.

## 제목 스타일
- 카페/커뮤니티 글 제목처럼 자연스러운 스타일
- 너무 꾸미지 않은, 실제 작성자가 쓸법한 제목
- 괄호, 이모지 선택적 사용 가능

## 피스 목록
{pieces}

## 출력 형식 (반드시 JSON)
```json
{{
  "0": ["제목1", "제목2", "제목3"],
  "1": ["제목1", "제목2", "제목3"]
}}
```

JSON만 출력하세요:"""

    prompt = (template.content if template else DEFAULT_TITLE_PROMPT).format(
        pieces=chr(10).join(pieces_desc)
    )

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(prompt, model=model, max_tokens=2000, return_usage=True, temperature=0.8)
        text = result["text"]
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            titles_data = json.loads(json_match.group())
            return {int(k): v for k, v in titles_data.items()}
    except Exception:
        pass
    return {}


@require_http_methods(["POST"])
def api_generate_multi_batch(request):
    """배치 생성 시작 (DB 레코드 생성)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    user_input = data.get("user_input", "").strip()
    procedure_id = data.get("procedure_id")
    content_types = data.get("content_types", [])
    content_lengths = data.get("content_lengths", {})
    model = data.get("model", "claude-sonnet-4-5-20250929")
    target_count = data.get("target_count", 30)
    persona = data.get("persona", {})
    situation = data.get("situation", {})
    temperature = data.get("temperature", 0.85)

    if not user_input:
        return JsonResponse({"error": "기본 정보를 입력해주세요."}, status=400)
    if not content_types:
        return JsonResponse({"error": "최소 하나의 컨텐츠를 선택해주세요."}, status=400)

    target_count = max(1, min(50, target_count))

    procedure = None
    if procedure_id:
        procedure = ProcedureInfo.objects.filter(pk=procedure_id, is_active=True).first()

    batch = MultiSeriesBatch.objects.create(
        name=f"{procedure.name if procedure else '시술'} 시리즈 x{target_count}",
        procedure=procedure,
        user_input=user_input,
        content_types=content_types,
        model_used=model,
        target_count=target_count,
        status='in_progress',
        persona_settings=persona,
        situation_settings=situation,
        temperature=temperature,
    )

    return JsonResponse({
        "success": True,
        "batch_id": batch.id,
        "target_count": target_count,
        "content_types": content_types,
        "content_lengths": content_lengths,
    })


@require_http_methods(["POST"])
def api_generate_multi_batch_next(request):
    """배치 내 다음 시리즈 생성"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    batch_id = data.get("batch_id")
    if not batch_id:
        return JsonResponse({"error": "batch_id 필요"}, status=400)

    batch = MultiSeriesBatch.objects.filter(pk=batch_id).first()
    if not batch:
        return JsonResponse({"error": "배치를 찾을 수 없습니다."}, status=404)

    if batch.completed_count >= batch.target_count:
        batch.status = 'completed'
        batch.save()
        return JsonResponse({"success": True, "completed": True, "batch_id": batch.id})

    series_index = batch.completed_count + 1

    import random

    # 저장된 페르소나 설정 가져오기
    saved_persona = batch.persona_settings or {}
    saved_situation = batch.situation_settings or {}

    def is_valid_value(val):
        """값이 유효한지 (빈값/'미지정'/'랜덤'이 아닌지) 확인"""
        return val and val not in ('', '미지정')

    def has_any_specified(settings):
        """설정 중 하나라도 지정된 값이 있는지 확인"""
        return any(is_valid_value(v) for v in settings.values())

    def get_value_or_random(saved_val, options, force_random=False):
        """저장된 값이 유효하면 사용, '랜덤'이거나 force_random이면 랜덤"""
        if saved_val == '랜덤' or force_random:
            return random.choice(options)
        if is_valid_value(saved_val):
            return saved_val
        return None  # 미지정이면 None 반환 (프롬프트에 추가 안 함)

    # 랜덤 옵션들
    ages = ['20대 초반', '20대 중반', '20대 후반', '30대 초반', '30대 중반', '30대 후반', '40대']
    genders = ['여성', '남성']
    jobs = ['직장인', '대학생', '주부', '자영업', '프리랜서']
    personalities = ['활발함', '소심함', '꼼꼼함', '털털함']
    tones = ['존댓말 위주', '반말 위주', '혼용', '살짝 격식체']
    experiences = ['첫 시술', '2~3회차', '5회 이상', '단골']

    # 페르소나: 모든 값이 미지정이면 빈 dict (사용자 입력 텍스트만 사용)
    # 하나라도 지정된 값이 있으면 해당 값 사용, '랜덤'이면 랜덤
    persona = {}
    if has_any_specified(saved_persona) or any(v == '랜덤' for v in saved_persona.values()):
        persona_fields = {
            'age': ages, 'gender': genders, 'job': jobs,
            'personality': personalities, 'tone': tones, 'experience': experiences
        }
        for key, options in persona_fields.items():
            val = get_value_or_random(saved_persona.get(key), options)
            if val:
                persona[key] = val

    # 상황 설정: 마찬가지로 지정된 값만 사용
    satisfaction_opts = ['매우 만족', '만족', '보통', '약간 아쉬움']
    pain_opts = ['거의 없음', '약간', '보통', '좀 아팠음']
    consult_opts = ['매우 친절', '친절', '보통', '사무적']
    downtime_opts = ['없음', '1~2일', '3~5일', '1주일 이상']
    price_opts = ['매우 합리적', '적당', '좀 비쌈', '비쌈']
    revisit_opts = ['꼭 다시 감', '아마 갈 듯', '모르겠음', '안 갈 듯']

    situation = {}
    if has_any_specified(saved_situation) or any(v == '랜덤' for v in saved_situation.values()):
        situation_fields = {
            'satisfaction': satisfaction_opts, 'pain': pain_opts,
            'consult': consult_opts, 'downtime': downtime_opts,
            'price': price_opts, 'revisit': revisit_opts
        }
        for key, options in situation_fields.items():
            val = get_value_or_random(saved_situation.get(key), options)
            if val:
                situation[key] = val

    # Temperature: 저장된 값 기준 ±0.05 랜덤 변동
    base_temp = batch.temperature or 0.85
    temperature = round(max(0.5, min(1.0, base_temp + random.uniform(-0.05, 0.05))), 2)
    content_lengths = data.get("content_lengths", {})

    from django.test import RequestFactory
    factory = RequestFactory()
    internal_data = {
        "user_input": batch.user_input,
        "procedure_id": batch.procedure_id,
        "content_types": batch.content_types,
        "content_lengths": content_lengths,
        "model": batch.model_used,
        "temperature": temperature,
        "persona": persona,
        "situation": situation,
    }
    fake_request = factory.post(
        '/dashboard/api/generate-multi-series/',
        data=json.dumps(internal_data),
        content_type='application/json'
    )
    response = api_generate_multi_series(fake_request)
    response_data = json.loads(response.content)

    if response_data.get("success"):
        series_data = response_data["series"]
        usage = response_data.get("usage", {})

        item = MultiSeriesItem.objects.create(
            batch=batch,
            series_index=series_index,
            persona_settings=persona,
            situation_settings=situation,
            temperature=temperature,
            pieces=series_data,
            prompt_used=response_data.get("prompt", ""),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=usage.get("cost_usd", 0),
        )

        batch.completed_count = series_index
        batch.total_input_tokens += usage.get("input_tokens", 0)
        batch.total_output_tokens += usage.get("output_tokens", 0)
        batch.total_cost_usd += usage.get("cost_usd", 0)
        if batch.completed_count >= batch.target_count:
            batch.status = 'completed'
        batch.save()

        return JsonResponse({
            "success": True,
            "completed": batch.completed_count >= batch.target_count,
            "batch_id": batch.id,
            "series_index": series_index,
            "item_id": item.id,
            "series": series_data,
            "persona": persona,
            "completed_count": batch.completed_count,
            "target_count": batch.target_count,
            "usage": usage,
        })
    else:
        return JsonResponse({
            "error": response_data.get("error", "생성 실패"),
            "batch_id": batch.id,
            "series_index": series_index,
        }, status=500)


@require_http_methods(["POST"])
def api_score_naturalness(request):
    """자연스러움 점수 평가 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    item_id = data.get("item_id")
    pieces = data.get("pieces", [])

    if not pieces:
        if item_id:
            item = MultiSeriesItem.objects.filter(pk=item_id).first()
            if item:
                pieces = item.pieces
        if not pieces:
            return JsonResponse({"error": "평가할 컨텐츠가 없습니다."}, status=400)

    from apps.data.models import PromptTemplate
    template = PromptTemplate.objects.filter(mode='basic_multi_score', is_default=True).first()

    pieces_text = []
    for i, p in enumerate(pieces):
        content = p.get("edited_content") or p.get("content", "")
        pieces_text.append(f"--- 피스 {i+1} [{p.get('type', '')}] ---\n{content}")

    DEFAULT_SCORE_PROMPT = """아래 시리즈 컨텐츠의 자연스러움을 평가해주세요.

## 평가 기준
1. AI가 아닌 실제 사람이 쓴 것처럼 보이는가
2. 반복되는 문장 구조나 패턴이 있는가
3. 과도하게 논리적이거나 정리된 느낌이 드는가
4. 자연스러운 구어체, 감정 표현이 잘 살아있는가
5. 카페/커뮤니티 글로서 적절한가

## 시리즈 컨텐츠
{pieces_text}

## 출력 형식 (반드시 JSON)
```json
{{
  "score": 7.5,
  "feedback": "전반적으로 자연스럽지만...",
  "strengths": ["구어체 표현이 자연스러움", "..."],
  "weaknesses": ["일부 문장 구조 반복", "..."],
  "suggestions": ["~부분을 ~로 수정하면 더 자연스러움", "..."]
}}
```

JSON만 출력하세요:"""

    prompt = (template.content if template else DEFAULT_SCORE_PROMPT).format(
        pieces_text=chr(10).join(pieces_text)
    )

    model = data.get("model", "claude-sonnet-4-5-20250929")

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(prompt, model=model, max_tokens=2000, return_usage=True, temperature=0.5)
        text = result["text"]

        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            score_data = json.loads(json_match.group())
        else:
            score_data = {"score": 0, "feedback": text}

        if item_id:
            item = MultiSeriesItem.objects.filter(pk=item_id).first()
            if item:
                item.naturalness_score = score_data.get("score", 0)
                item.score_feedback = json.dumps(score_data, ensure_ascii=False)
                item.status = 'scored'
                item.save()

        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "score_data": score_data,
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except Exception as e:
        return JsonResponse({"error": f"평가 실패: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def api_regenerate_piece(request):
    """특정 피스 재생성 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    item_id = data.get("item_id")
    piece_index = data.get("piece_index", 0)
    model = data.get("model", "claude-sonnet-4-5-20250929")

    item = MultiSeriesItem.objects.filter(pk=item_id).first()
    if not item:
        return JsonResponse({"error": "시리즈를 찾을 수 없습니다."}, status=404)

    if piece_index < 0 or piece_index >= len(item.pieces):
        return JsonResponse({"error": "유효하지 않은 피스 인덱스"}, status=400)

    piece = item.pieces[piece_index]
    type_names = {
        'question': '고민 & 질문', 'research': '발품/손품',
        'consultation': '방문상담 후기', 'day0': '시술 당일 후기',
        'week1': '시술 후 1주일 후기', 'week2': '시술 후 2주일 후기', 'week3': '시술 후 3주일 후기',
        'month1': '시술 후 1개월 후기', 'month2': '시술 후 2개월 후기',
        'month3': '시술 후 3개월 후기', 'title': '제목',
    }

    prompt = f"""아래 컨텐츠를 더 자연스럽게 다시 작성해주세요.
동일한 주제와 시점을 유지하되, 표현과 문체를 완전히 새롭게 바꿔주세요.

## 컨텐츠 타입: {type_names.get(piece.get('type', ''), piece.get('type', ''))}
## 글자수: {piece.get('char_count', 500)}자 내외
## 기존 내용:
{piece.get('content', '')}

## 원칙
- AI 탐지 방지를 위한 자연스러운 문체
- 단문 위주, 구어체 표현
- 반복 패턴 금지
- 카페/커뮤니티 글 스타일

새로운 버전을 작성해주세요:"""

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt
        result = generate_review_with_prompt(prompt, model=model, max_tokens=3000, return_usage=True, temperature=0.9)
        new_content = result["text"].strip()

        item.pieces[piece_index]["content"] = new_content
        item.pieces[piece_index]["char_count"] = len(new_content)
        item.save()

        cost_krw = result["cost_usd"] * 1450

        return JsonResponse({
            "success": True,
            "piece_index": piece_index,
            "content": new_content,
            "char_count": len(new_content),
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except Exception as e:
        return JsonResponse({"error": f"재생성 실패: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def api_save_multi_edits(request):
    """편집 내용 저장 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    item_id = data.get("item_id")
    pieces = data.get("pieces", [])

    item = MultiSeriesItem.objects.filter(pk=item_id).first()
    if not item:
        return JsonResponse({"error": "시리즈를 찾을 수 없습니다."}, status=404)

    for p_update in pieces:
        idx = p_update.get("index", -1)
        if 0 <= idx < len(item.pieces):
            if "edited_content" in p_update:
                item.pieces[idx]["edited_content"] = p_update["edited_content"]
            if "selected_title" in p_update:
                item.pieces[idx]["selected_title"] = p_update["selected_title"]

    item.status = 'edited'
    item.save()

    return JsonResponse({"success": True, "item_id": item.id})


@require_http_methods(["POST"])
def api_save_schedule(request):
    """스케줄 저장 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    item_id = data.get("item_id")
    schedules = data.get("schedules", [])

    item = MultiSeriesItem.objects.filter(pk=item_id).first()
    if not item:
        return JsonResponse({"error": "시리즈를 찾을 수 없습니다."}, status=404)

    for sched in schedules:
        idx = sched.get("index", -1)
        if 0 <= idx < len(item.pieces):
            item.pieces[idx]["scheduled_date"] = sched.get("date", "")

    item.status = 'scheduled'
    item.save()

    return JsonResponse({"success": True, "item_id": item.id})


@require_http_methods(["POST"])
def api_export_multi(request):
    """내보내기 API (text/CSV/JSON)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    batch_id = data.get("batch_id")
    item_ids = data.get("item_ids", [])
    export_format = data.get("format", "json")

    if batch_id:
        items = MultiSeriesItem.objects.filter(batch_id=batch_id).order_by('series_index')
    elif item_ids:
        items = MultiSeriesItem.objects.filter(pk__in=item_ids).order_by('series_index')
    else:
        return JsonResponse({"error": "batch_id 또는 item_ids 필요"}, status=400)

    type_names = {
        'question': '고민 & 질문', 'research': '발품/손품',
        'consultation': '방문상담 후기', 'day0': '시술 당일 후기',
        'week1': '시술 후 1주일 후기', 'week2': '시술 후 2주일 후기', 'week3': '시술 후 3주일 후기',
        'month1': '시술 후 1개월 후기', 'month2': '시술 후 2개월 후기',
        'month3': '시술 후 3개월 후기', 'title': '제목',
    }

    if export_format == 'text':
        lines = []
        for item in items:
            lines.append(f"===== 시리즈 #{item.series_index} =====")
            for i, p in enumerate(item.pieces):
                title = p.get("selected_title", "")
                content = p.get("edited_content") or p.get("content", "")
                type_label = type_names.get(p.get("type", ""), p.get("type", ""))
                if title:
                    lines.append(f"\n--- [{type_label}] {title} ---")
                else:
                    lines.append(f"\n--- [{type_label}] ---")
                lines.append(content)
            lines.append("")
        return JsonResponse({"success": True, "data": "\n".join(lines), "format": "text"})

    elif export_format == 'csv':
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["시리즈", "피스", "타입", "제목", "내용", "글자수", "스케줄"])
        for item in items:
            for i, p in enumerate(item.pieces):
                content = p.get("edited_content") or p.get("content", "")
                writer.writerow([
                    item.series_index,
                    i + 1,
                    type_names.get(p.get("type", ""), p.get("type", "")),
                    p.get("selected_title", ""),
                    content,
                    len(content),
                    p.get("scheduled_date", ""),
                ])
        return JsonResponse({"success": True, "data": output.getvalue(), "format": "csv"})

    else:  # json
        export_data = []
        for item in items:
            export_data.append({
                "series_index": item.series_index,
                "persona": item.persona_settings,
                "situation": item.situation_settings,
                "naturalness_score": item.naturalness_score,
                "pieces": item.pieces,
            })
        return JsonResponse({"success": True, "data": export_data, "format": "json"})


@require_http_methods(["GET"])
def api_procedures_search(request):
    """시술 정보 검색 (autocomplete)"""
    q = request.GET.get("q", "").strip()
    if not q:
        procedures = ProcedureInfo.objects.filter(is_active=True)[:20]
    else:
        procedures = ProcedureInfo.objects.filter(
            is_active=True,
            name__icontains=q
        )[:20]

    results = []
    for p in procedures:
        results.append({
            "id": p.id,
            "name": p.name,
            "category": p.get_category_display(),
            "pain_level": p.get_pain_level_display(),
            "price_range": p.price_range,
            "description": p.description[:100] if p.description else "",
        })

    return JsonResponse({"results": results})


# =====================================================
# 시술 정보 CRUD
# =====================================================

def procedure_list(request):
    """시술 정보 목록"""
    procedures = ProcedureInfo.objects.all()
    return render(request, "dashboard/procedure_list.html", {"procedures": procedures})


def procedure_edit(request, pk=None):
    """시술 정보 편집/생성"""
    if pk:
        procedure = get_object_or_404(ProcedureInfo, pk=pk)
    else:
        procedure = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, "dashboard/procedure_edit.html", {
                "procedure": procedure, "error": "시술명은 필수입니다."
            })

        if not procedure:
            procedure = ProcedureInfo()

        procedure.name = name
        procedure.category = request.POST.get('category', 'skin')
        procedure.description = request.POST.get('description', '')
        procedure.pain_level = request.POST.get('pain_level', 'moderate')
        procedure.recovery_time = request.POST.get('recovery_time', '')
        procedure.typical_results = request.POST.get('typical_results', '')
        procedure.price_range = request.POST.get('price_range', '')
        procedure.duration = request.POST.get('duration', '')
        procedure.anesthesia_type = request.POST.get('anesthesia_type', '')
        procedure.sessions_recommended = request.POST.get('sessions_recommended', '')

        side_effects = request.POST.get('common_side_effects', '')
        procedure.common_side_effects = [s.strip() for s in side_effects.split(',') if s.strip()] if side_effects else []

        precautions = request.POST.get('precautions', '')
        procedure.precautions = [s.strip() for s in precautions.split(',') if s.strip()] if precautions else []

        procedure.save()

        from django.shortcuts import redirect
        return redirect('dashboard:procedure_list')

    return render(request, "dashboard/procedure_edit.html", {"procedure": procedure})


@require_http_methods(["POST"])
def api_procedure_delete(request, pk):
    """시술 삭제"""
    procedure = get_object_or_404(ProcedureInfo, pk=pk)
    procedure.delete()
    return JsonResponse({"success": True})


@require_http_methods(["POST"])
def api_procedure_toggle(request, pk):
    """시술 활성/비활성"""
    procedure = get_object_or_404(ProcedureInfo, pk=pk)
    procedure.is_active = not procedure.is_active
    procedure.save()
    return JsonResponse({"success": True, "is_active": procedure.is_active})


def api_sisool_list_search(request):
    """SiSool_List.json에서 시술명 검색 API"""
    import os
    from django.conf import settings

    query = request.GET.get("q", "").strip().lower()

    # JSON 파일 로드
    json_path = os.path.join(settings.BASE_DIR, "SiSool_List.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            sisool_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return JsonResponse({"error": str(e), "results": []})

    # 모든 시술명 평탄화
    def flatten_procedures(data, path=""):
        results = []
        if isinstance(data, dict):
            for key, value in data.items():
                # 메타 정보 스킵
                if key in ["미용시술_전체목록", "작성일", "총_카테고리수", "카테고리"]:
                    continue
                new_path = f"{path} > {key}" if path else key
                results.extend(flatten_procedures(value, new_path))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = item.get("시술명") or item.get("성분명") or item.get("기술명", "")
                    if name:
                        results.append({
                            "name": name,
                            "category": path,
                            "english": item.get("영문명", ""),
                            "effect": item.get("효과", []) if isinstance(item.get("효과"), list) else [],
                            "cycle": item.get("시술주기", item.get("지속기간", "")),
                            "data": item,
                        })
        return results

    all_procedures = flatten_procedures(sisool_data)

    # 검색 필터링
    if query:
        filtered = []
        for p in all_procedures:
            # 시술명, 영문명, 카테고리에서 검색
            if (query in p["name"].lower() or
                query in p.get("english", "").lower() or
                query in p["category"].lower()):
                filtered.append(p)
        results = filtered[:30]  # 최대 30개
    else:
        results = all_procedures[:50]  # 기본 50개

    return JsonResponse({
        "results": results,
        "total": len(all_procedures),
        "query": query,
    })


@require_http_methods(["POST"])
def api_collect_procedure_knowledge(request):
    """AI 시술 지식 수집 API"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    procedure_name = data.get("procedure_name", "").strip()
    procedure_id = data.get("procedure_id")
    model = data.get("model", "claude-sonnet-4-5-20250929")
    custom_prompt = data.get("custom_prompt", "").strip()
    categories = data.get("categories", [])  # 특정 카테고리만 수집
    save_raw_only = data.get("save_raw_only", False)  # 원본만 저장 모드

    logger.info(f"[지식수집] 시술명={procedure_name}, ID={procedure_id}, 모델={model}, 원본저장={save_raw_only}")
    print(f"[지식수집] 시술명={procedure_name}, ID={procedure_id}, 모델={model}, 원본저장={save_raw_only}")

    if not procedure_name:
        return JsonResponse({"error": "시술명을 입력해주세요."}, status=400)

    # 기존 지식이 있으면 참조
    existing_knowledge = {}
    if procedure_id:
        proc = ProcedureInfo.objects.filter(pk=procedure_id).first()
        if proc and proc.knowledge_base:
            existing_knowledge = proc.knowledge_base

    # 수집 프롬프트 구성
    # 원본 저장 모드에서는 custom_prompt가 메타데이터용이므로 자동 수집 프롬프트 사용
    use_custom = custom_prompt and not save_raw_only
    if use_custom:
        # 커스텀 프롬프트 모드
        prompt = f"""다음 시술에 대해 사용자의 질문/요청에 답변하고, 해당 내용을 knowledge_base JSON 형식에 맞춰 반환해주세요.

시술명: {procedure_name}

사용자 요청:
{custom_prompt}

기존 수집된 지식:
{json.dumps(existing_knowledge, ensure_ascii=False, indent=2) if existing_knowledge else "없음"}

## 출력 형식 (반드시 JSON)
기존 지식에 새 내용을 병합(merge)하여 아래 구조로 반환하세요. 기존 내용은 유지하고 새 내용을 추가/보완합니다.
```json
{{
  "sensory": {{
    "during": ["시술 중 느끼는 감각들"],
    "after": ["시술 직후 감각들"],
    "healing": ["회복 중 감각 변화"]
  }},
  "emotional_journey": {{
    "before": ["시술 전 감정/걱정/기대"],
    "during": ["시술 중 감정 변화"],
    "recovery": ["회복 과정 감정 변화"],
    "after": ["최종 결과에 대한 감정"]
  }},
  "real_expressions": ["실제 커뮤니티에서 쓰이는 표현들 (시술 관련)"],
  "unexpected": ["예상 못한 부분들, 의외의 경험"],
  "community_tips": ["커뮤니티에서 공유되는 실용적 팁"],
  "common_concerns": ["흔한 걱정거리와 실제 결과"],
  "satisfaction_patterns": {{
    "satisfied": "만족하는 경우의 패턴/이유",
    "disappointed": "아쉬워하는 경우의 패턴/이유"
  }},
  "seasonal_notes": "계절별 고려사항",
  "comparison_notes": "비슷한 시술과의 비교",
  "detail_points": ["리뷰에서 디테일로 쓸 수 있는 구체적 포인트들"],
  "wrong_info_corrections": ["흔히 잘못 알려진 정보 교정"]
}}
```

JSON만 출력하세요:"""
    else:
        # 전체 자동 수집 모드
        category_filter = ""
        if categories:
            category_filter = f"\n\n## 수집 범위\n다음 카테고리만 중점적으로 수집: {', '.join(categories)}"

        prompt = f"""당신은 미용 시술 체험 정보를 수집하는 전문가입니다.
다음 시술에 대해 **실제 시술을 받은 사람들의 관점**에서 체험 기반 지식을 수집해주세요.

단순한 의료 정보(통증레벨, 회복기간 등)가 아니라,
**실제 체험자만 알 수 있는 감각, 감정, 디테일, 커뮤니티 표현**을 중심으로 수집합니다.

시술명: {procedure_name}
{category_filter}

기존 수집된 지식:
{json.dumps(existing_knowledge, ensure_ascii=False, indent=2) if existing_knowledge else "없음"}

## 수집 원칙
1. 의료 교과서적 설명 금지 → 체험자가 실제로 느끼고 말하는 방식으로
2. "통증이 있을 수 있습니다" 대신 → "고무줄로 톡톡 튕기는 느낌", "따끔+열감이 올라옴"
3. 커뮤니티(카페, 블로그)에서 실제 사용되는 표현 위주
4. 시술 전/중/후 시간 흐름에 따른 감정 변화 포착
5. 잘 알려지지 않은 디테일 (대기시간, 마취 기다리는 지루함, 회복 중 불편한 순간 등)
6. 기존 지식이 있으면 보완/확장 (중복 제거)

## 출력 형식 (반드시 JSON)
```json
{{
  "sensory": {{
    "during": ["시술 중 느끼는 구체적 감각들"],
    "after": ["시술 직후 감각들 (당일)"],
    "healing": ["회복 중 감각 변화 (일주일간)"]
  }},
  "emotional_journey": {{
    "before": ["시술 전 감정/걱정/기대"],
    "during": ["시술 중 감정 흐름"],
    "recovery": ["회복 과정 감정 변화"],
    "after": ["최종 결과에 대한 감정"]
  }},
  "real_expressions": ["커뮤니티에서 실제 쓰이는 이 시술 관련 표현들 10개 이상"],
  "unexpected": ["예상 못한 부분들, 아무도 안 알려준 것들"],
  "community_tips": ["커뮤니티에서 공유되는 실용적 팁들"],
  "common_concerns": ["흔한 걱정거리 + 실제로는 어떤지"],
  "satisfaction_patterns": {{
    "satisfied": "만족하는 경우의 패턴과 이유",
    "disappointed": "아쉬워하는 경우의 패턴과 이유"
  }},
  "seasonal_notes": "계절별 고려사항 (있다면)",
  "comparison_notes": "비슷한 시술과의 차이점 (체험자 관점)",
  "detail_points": ["리뷰에서 디테일로 활용 가능한 구체적 포인트 10개 이상"],
  "wrong_info_corrections": ["흔히 잘못 알려진 정보와 실제"]
}}
```

JSON만 출력하세요:"""

    try:
        from apps.ml.services.llm_service import generate_review_with_prompt
        from datetime import datetime

        result = generate_review_with_prompt(
            prompt,
            model=model,
            max_tokens=4000,
            return_usage=True,
            temperature=0.7
        )
        text = result["text"]
        cost_krw = result["cost_usd"] * 1450

        print(f"[지식수집] LLM 응답 길이: {len(text)}, 토큰: {result.get('input_tokens', 0)}+{result.get('output_tokens', 0)}")

        # 원본만 저장 모드
        if save_raw_only:
            # 원본을 바로 DB에 저장
            proc = None
            if procedure_id:
                proc = ProcedureInfo.objects.filter(pk=procedure_id).first()

            # procedure_id가 없거나 찾지 못한 경우 이름으로 생성/조회
            if not proc and procedure_name:
                proc, created = ProcedureInfo.objects.get_or_create(
                    name=procedure_name,
                    defaults={"category": "etc"}
                )

            if not proc:
                return JsonResponse({
                    "error": "시술 정보를 저장할 수 없습니다. 시술명을 확인해주세요.",
                    "raw_content": text,
                }, status=400)

            # 원본 저장
            raw_entries = list(proc.raw_knowledge_entries or [])
            raw_entries.append({
                "collected_at": datetime.now().isoformat(),
                "prompt": custom_prompt or "(자동 수집)",
                "model": model,
                "content": text,
                "tokens": result["input_tokens"] + result["output_tokens"],
                "cost_usd": result["cost_usd"],
            })
            proc.raw_knowledge_entries = raw_entries
            proc.save()
            print(f"[지식수집] 원본 저장 완료: 시술ID={proc.id}, 항목수={len(raw_entries)}")

            return JsonResponse({
                "success": True,
                "mode": "raw_saved",
                "procedure_id": proc.id,
                "procedure_name": proc.name,
                "raw_content": text,
                "entries_count": len(raw_entries),
                "usage": {
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "cost_usd": round(result["cost_usd"], 6),
                    "cost_krw": round(cost_krw, 2),
                }
            })

        # JSON 추출 - 여러 방법 시도 (기존 파싱 모드)
        knowledge = None
        parse_error = None
        json_str = None
        start_idx = -1
        end_idx = -1

        def clean_json_string(s):
            """JSON 문자열 정제"""
            cleaned = s
            # 싱글 쿼트를 더블 쿼트로 변환 (문자열 내부 제외)
            # 단순 변환 (문자열 내부의 싱글 쿼트는 유지)
            cleaned = re.sub(r"(?<![\\])'", '"', cleaned)
            # 후행 쉼표 제거
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
            # 제어 문자 처리 (줄바꿈, 탭 등)
            # 먼저 이미 이스케이프된 것은 건드리지 않음
            cleaned = re.sub(r'(?<!\\)\n', '\\n', cleaned)
            cleaned = re.sub(r'(?<!\\)\t', '\\t', cleaned)
            cleaned = re.sub(r'(?<!\\)\r', '\\r', cleaned)
            return cleaned

        # 방법 1: ```json 블록에서 추출
        json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_block_match:
            try:
                json_str = json_block_match.group(1).strip()
                knowledge = json.loads(json_str)
            except json.JSONDecodeError as e:
                parse_error = e
                # 클리닝 후 재시도
                try:
                    knowledge = json.loads(clean_json_string(json_str))
                except json.JSONDecodeError:
                    pass

        # 방법 2: 가장 바깥쪽 중괄호 찾기 (중첩 고려)
        if knowledge is None:
            try:
                # 첫 번째 { 위치 찾기
                start_idx = text.find('{')
                if start_idx != -1:
                    # 중첩된 중괄호 카운팅으로 마지막 } 찾기
                    brace_count = 0
                    end_idx = start_idx
                    for i, char in enumerate(text[start_idx:], start_idx):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i
                                break

                    json_str = text[start_idx:end_idx + 1]
                    knowledge = json.loads(json_str)
            except json.JSONDecodeError as e:
                parse_error = e

        # 방법 3: JSON 클리닝 후 재시도
        if knowledge is None and start_idx != -1 and json_str:
            try:
                cleaned = clean_json_string(json_str)
                knowledge = json.loads(cleaned)
            except json.JSONDecodeError as e:
                parse_error = e

        # 방법 4: ast.literal_eval로 Python dict 파싱 시도
        if knowledge is None and json_str:
            try:
                import ast
                # Python dict 형태(싱글 쿼트)로 파싱
                parsed = ast.literal_eval(json_str)
                if isinstance(parsed, dict):
                    knowledge = parsed
            except (ValueError, SyntaxError) as e:
                pass

        # 방법 5: 모든 시도 실패 시 raw 텍스트와 함께 에러 반환
        if knowledge is None:
            # 파싱 실패해도 원본은 저장 (procedure_id 또는 procedure_name으로)
            proc = None
            if procedure_id:
                proc = ProcedureInfo.objects.filter(pk=procedure_id).first()
            if not proc and procedure_name:
                proc, created = ProcedureInfo.objects.get_or_create(
                    name=procedure_name,
                    defaults={"category": "etc"}
                )

            raw_saved = False
            if proc:
                raw_entries = list(proc.raw_knowledge_entries or [])
                raw_entries.append({
                    "collected_at": datetime.now().isoformat(),
                    "prompt": custom_prompt or "(자동 수집)",
                    "model": model,
                    "content": text,
                    "tokens": result["input_tokens"] + result["output_tokens"],
                    "cost_usd": result["cost_usd"],
                    "parse_failed": True,
                })
                proc.raw_knowledge_entries = raw_entries
                proc.save()
                raw_saved = True
                print(f"[지식수집] 파싱 실패했지만 원본 저장 완료: 시술ID={proc.id}")

            error_msg = f"JSON 파싱 실패: {str(parse_error)}" if parse_error else "AI 응답에서 JSON을 추출하지 못했습니다."
            return JsonResponse({
                "error": error_msg,
                "raw": text,
                "raw_saved": raw_saved,
                "procedure_id": proc.id if proc else None,
                "hint": "AI 응답을 확인하고 필요한 부분을 수동으로 추출해 주세요. 원본은 저장되었습니다." if raw_saved else "원본 저장도 실패했습니다."
            }, status=500)

        return JsonResponse({
            "success": True,
            "knowledge": knowledge,
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })

    except Exception as e:
        import traceback
        return JsonResponse({
            "error": f"수집 실패: {str(e)}",
            "traceback": traceback.format_exc()
        }, status=500)


@require_http_methods(["POST"])
def api_save_procedure_knowledge(request):
    """수집된 지식을 시술 DB에 저장"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    procedure_id = data.get("procedure_id")
    procedure_name = data.get("procedure_name", "").strip()
    knowledge = data.get("knowledge", {})
    raw_entries = data.get("raw_entries")  # 원본 데이터 업데이트용
    basic_info = data.get("basic_info", {})  # 기본 정보도 함께 저장 가능

    # raw_entries만 업데이트하는 경우
    if raw_entries is not None and not knowledge:
        if not procedure_id:
            return JsonResponse({"error": "procedure_id 필요"}, status=400)
        proc = ProcedureInfo.objects.filter(pk=procedure_id).first()
        if not proc:
            return JsonResponse({"error": "시술을 찾을 수 없습니다."}, status=404)
        proc.raw_knowledge_entries = raw_entries
        proc.save()
        return JsonResponse({
            "success": True,
            "procedure_id": proc.id,
            "raw_entries_count": len(raw_entries),
        })

    if not knowledge:
        return JsonResponse({"error": "저장할 지식 데이터가 없습니다."}, status=400)

    if procedure_id:
        proc = ProcedureInfo.objects.filter(pk=procedure_id).first()
        if not proc:
            return JsonResponse({"error": "시술을 찾을 수 없습니다."}, status=404)
    elif procedure_name:
        # 이름으로 찾거나 새로 생성
        proc, created = ProcedureInfo.objects.get_or_create(
            name=procedure_name,
            defaults={"category": basic_info.get("category", "etc")}
        )
    else:
        return JsonResponse({"error": "procedure_id 또는 procedure_name 필요"}, status=400)

    # 기본 정보 업데이트 (제공된 경우)
    if basic_info:
        if basic_info.get("category"):
            proc.category = basic_info["category"]
        if basic_info.get("description"):
            proc.description = basic_info["description"]
        if basic_info.get("pain_level"):
            proc.pain_level = basic_info["pain_level"]
        if basic_info.get("recovery_time"):
            proc.recovery_time = basic_info["recovery_time"]
        if basic_info.get("price_range"):
            proc.price_range = basic_info["price_range"]
        if basic_info.get("duration"):
            proc.duration = basic_info["duration"]

    # 지식 병합 (기존 + 새로운)
    existing = proc.knowledge_base or {}
    merged = _merge_knowledge(existing, knowledge)
    proc.knowledge_base = merged
    proc.save()

    return JsonResponse({
        "success": True,
        "procedure_id": proc.id,
        "procedure_name": proc.name,
        "knowledge_categories": list(merged.keys()),
    })


@require_http_methods(["POST"])
def api_parse_raw_knowledge(request):
    """원본 데이터 일괄/개별 파싱 API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    procedure_id = data.get("procedure_id")
    entry_index = data.get("entry_index")  # 특정 항목만 파싱 (None이면 전체)

    if not procedure_id:
        return JsonResponse({"error": "procedure_id 필요"}, status=400)

    proc = ProcedureInfo.objects.filter(pk=procedure_id).first()
    if not proc:
        return JsonResponse({"error": "시술을 찾을 수 없습니다."}, status=404)

    raw_entries = list(proc.raw_knowledge_entries or [])
    if not raw_entries:
        return JsonResponse({"error": "파싱할 원본 데이터가 없습니다."}, status=400)

    # 파싱 대상 결정
    if entry_index is not None:
        if entry_index < 0 or entry_index >= len(raw_entries):
            return JsonResponse({"error": "잘못된 entry_index"}, status=400)
        targets = [(entry_index, raw_entries[entry_index])]
    else:
        targets = list(enumerate(raw_entries))

    parsed_count = 0
    failed_count = 0
    merged_knowledge = dict(proc.knowledge_base or {})

    def clean_json_string(s):
        """JSON 문자열 정제"""
        cleaned = s
        # 싱글 쿼트를 더블 쿼트로 변환
        cleaned = re.sub(r"(?<![\\])'", '"', cleaned)
        # 후행 쉼표 제거
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        # 제어 문자 처리
        cleaned = re.sub(r'(?<!\\)\n', '\\n', cleaned)
        cleaned = re.sub(r'(?<!\\)\t', '\\t', cleaned)
        cleaned = re.sub(r'(?<!\\)\r', '\\r', cleaned)
        return cleaned

    def extract_json_from_text(text):
        """텍스트에서 JSON 추출"""
        # 방법 1: ```json 블록
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_match:
            json_str = json_match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                try:
                    return json.loads(clean_json_string(json_str))
                except json.JSONDecodeError:
                    pass

        # 방법 2: 중괄호 매칭
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            end_idx = start_idx
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            json_str = text[start_idx:end_idx + 1]

            # 원본 시도
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # 클리닝 후 시도
            try:
                return json.loads(clean_json_string(json_str))
            except json.JSONDecodeError:
                pass

            # ast.literal_eval 시도 (Python dict 형태)
            try:
                import ast
                parsed = ast.literal_eval(json_str)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                pass

        return None

    for idx, entry in targets:
        content = entry.get("content", "")
        if not content:
            continue

        # JSON 추출 시도
        extracted = extract_json_from_text(content)

        if extracted and isinstance(extracted, dict):
            # knowledge_base에 병합
            merged_knowledge = _merge_knowledge(merged_knowledge, extracted)
            # 원본에 파싱 완료 표시
            raw_entries[idx]["parsed"] = True
            raw_entries[idx]["parsed_at"] = __import__('datetime').datetime.now().isoformat()
            parsed_count += 1
        else:
            raw_entries[idx]["parse_failed"] = True
            failed_count += 1

    # 저장
    proc.knowledge_base = merged_knowledge
    proc.raw_knowledge_entries = raw_entries
    proc.save()

    return JsonResponse({
        "success": True,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "total_entries": len(raw_entries),
        "knowledge_categories": list(merged_knowledge.keys()),
    })


def _merge_knowledge(existing, new_data):
    """기존 지식과 새 지식을 병합"""
    merged = dict(existing)
    for key, value in new_data.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged[key], dict):
            # 딕셔너리면 재귀 병합
            merged[key] = _merge_knowledge(merged[key], value)
        elif isinstance(value, list) and isinstance(merged[key], list):
            # 리스트면 중복 제거 후 합치기
            existing_set = set(merged[key])
            for item in value:
                if item not in existing_set:
                    merged[key].append(item)
        else:
            # 나머지는 새 값으로 덮어쓰기
            merged[key] = value
    return merged


# =====================================================
# 프롬프트 최적화 사이클
# =====================================================

def optimization_list(request):
    """최적화 세션 목록"""
    from apps.data.models import PromptOptimizationSession
    sessions = PromptOptimizationSession.objects.all()
    return render(request, "dashboard/optimization_list.html", {"sessions": sessions})


def optimization_new(request):
    """새 최적화 세션 생성"""
    from apps.data.models import PromptOptimizationSession, ProcedureInfo, PromptTemplate
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    if request.method == 'POST':
        data = request.POST
        session = PromptOptimizationSession.objects.create(
            name=data.get('name', '새 세션'),
            description=data.get('description', ''),
            base_prompt_template_id=data.get('template_id') or None,
            procedure_id=data.get('procedure_id') or None,
            user_input=data.get('user_input', ''),
            samples_per_round=int(data.get('samples_per_round', 50)),
            target_rounds=int(data.get('target_rounds', 5)),
            mode=data.get('mode', 'semi_auto'),
            auto_approve_threshold=float(data.get('auto_approve_threshold', 8.0)),
            model_used=data.get('model_used', 'claude-sonnet-4-5-20250929'),
            analysis_model=data.get('analysis_model', 'claude-sonnet-4-5-20250929'),
            # 상세 생성 설정
            temperature_min=float(data.get('temperature_min', 0.7)),
            temperature_max=float(data.get('temperature_max', 0.95)),
            max_tokens_generation=int(data.get('max_tokens_generation', 4000)),
            max_tokens_analysis=int(data.get('max_tokens_analysis', 8000)),
            analysis_depth=data.get('analysis_depth', 'detailed'),
            # 분석 옵션
            analyze_ai_detection=data.get('analyze_ai_detection') == 'on',
            analyze_naturalness=data.get('analyze_naturalness') == 'on',
            analyze_diversity=data.get('analyze_diversity') == 'on',
            analyze_accuracy=data.get('analyze_accuracy') == 'on',
        )
        from django.shortcuts import redirect
        return redirect('dashboard:optimization_session', pk=session.pk)

    # GET: 폼 표시
    templates = PromptTemplate.objects.filter(is_active=True)
    procedures = ProcedureInfo.objects.filter(is_active=True)
    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    return render(request, "dashboard/optimization_new.html", {
        "templates": templates,
        "procedures": procedures,
        "models": models_list,
    })


def optimization_session(request, pk):
    """최적화 세션 상세 (메인 워크플로우)"""
    from apps.data.models import PromptOptimizationSession, OptimizationRound
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    session = get_object_or_404(PromptOptimizationSession, pk=pk)
    rounds = session.rounds.all().order_by('round_number')
    current_round = rounds.last() if rounds.exists() else None

    # 가장 최근 승인된 라운드 찾기
    latest_approved_round = rounds.filter(status='approved').order_by('-round_number').first()

    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    return render(request, "dashboard/optimization_session.html", {
        "session": session,
        "rounds": rounds,
        "current_round": current_round,
        "latest_approved_round": latest_approved_round,
        "models": models_list,
    })


def optimization_session_auto(request, pk):
    """자동 최적화 세션 (완전 자동화)"""
    from apps.data.models import PromptOptimizationSession, OptimizationRound
    from apps.ml.services.llm_service import AVAILABLE_MODELS

    session = get_object_or_404(PromptOptimizationSession, pk=pk)
    rounds = session.rounds.all().order_by('round_number')
    current_round = rounds.last() if rounds.exists() else None

    models_list = []
    for provider, models in AVAILABLE_MODELS.items():
        for model_id, info in models.items():
            models_list.append({
                "id": model_id,
                "provider": provider,
                "name": info["name"],
                "desc": info["desc"],
            })

    return render(request, "dashboard/optimization_session_auto.html", {
        "session": session,
        "rounds": rounds,
        "current_round": current_round,
        "models": models_list,
    })


@require_http_methods(["POST"])
def optimization_delete(request, pk):
    """세션 삭제"""
    from apps.data.models import PromptOptimizationSession
    session = get_object_or_404(PromptOptimizationSession, pk=pk)
    session.delete()
    return JsonResponse({"success": True})


# =====================================================
# 최적화 API - 세션 관리
# =====================================================

def api_optimization_sessions(request):
    """세션 목록/생성 API"""
    from apps.data.models import PromptOptimizationSession

    if request.method == 'GET':
        sessions = PromptOptimizationSession.objects.all()
        data = [{
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "current_round": s.current_round,
            "target_rounds": s.target_rounds,
            "total_cost_usd": s.total_cost_usd,
            "created_at": s.created_at.strftime('%Y-%m-%d %H:%M'),
        } for s in sessions]
        return JsonResponse({"sessions": data})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "잘못된 요청"}, status=400)

        session = PromptOptimizationSession.objects.create(
            name=data.get('name', '새 세션'),
            description=data.get('description', ''),
            base_prompt_template_id=data.get('template_id'),
            procedure_id=data.get('procedure_id'),
            user_input=data.get('user_input', ''),
            samples_per_round=data.get('samples_per_round', 50),
            target_rounds=data.get('target_rounds', 5),
            mode=data.get('mode', 'semi_auto'),
        )
        return JsonResponse({"success": True, "id": session.id})


def api_optimization_session_detail(request, pk):
    """세션 상세/삭제 API"""
    from apps.data.models import PromptOptimizationSession

    session = get_object_or_404(PromptOptimizationSession, pk=pk)

    if request.method == 'GET':
        rounds_data = [{
            "id": r.id,
            "round_number": r.round_number,
            "status": r.status,
            "score_overall": r.score_overall,
            "generated_count": r.generated_count,
        } for r in session.rounds.all().order_by('round_number')]

        return JsonResponse({
            "id": session.id,
            "name": session.name,
            "description": session.description,
            "status": session.status,
            "current_round": session.current_round,
            "target_rounds": session.target_rounds,
            "samples_per_round": session.samples_per_round,
            "mode": session.mode,
            "analyze_ai_detection": session.analyze_ai_detection,
            "analyze_naturalness": session.analyze_naturalness,
            "analyze_diversity": session.analyze_diversity,
            "analyze_accuracy": session.analyze_accuracy,
            "total_cost_usd": session.total_cost_usd,
            "rounds": rounds_data,
        })

    elif request.method == 'DELETE':
        session.delete()
        return JsonResponse({"success": True})


# =====================================================
# 최적화 API - 라운드 실행
# =====================================================

@require_http_methods(["POST"])
def api_optimization_start_round(request, pk):
    """새 라운드 시작"""
    from apps.data.models import PromptOptimizationSession, OptimizationRound, OptimizationLog

    session = get_object_or_404(PromptOptimizationSession, pk=pk)

    # 아직 완료되지 않은 라운드가 있는지 확인 (승인/거부되지 않은 모든 라운드)
    incomplete_round = session.rounds.exclude(status__in=['approved', 'rejected']).first()
    if incomplete_round:
        status_msg = {
            'pending': '대기 중 (생성 시작 필요)',
            'generating': '생성 중',
            'generated': '생성 완료 (분석 필요)',
            'analyzing': '분석 중',
            'analyzed': '분석 완료 (승인 필요)',
        }.get(incomplete_round.status, incomplete_round.status)
        return JsonResponse({
            "error": f"라운드 {incomplete_round.round_number}이(가) 아직 완료되지 않았습니다. (상태: {status_msg})"
        }, status=400)

    # 새 라운드 번호 결정 - 단순히 전체 라운드 수 + 1
    existing_count = session.rounds.count()
    new_round_number = existing_count + 1

    # 마지막 승인된 라운드 찾기
    last_approved = session.rounds.filter(status='approved').order_by('-round_number').first()

    # 프롬프트 결정: 마지막 승인된 프롬프트 또는 기본 템플릿
    if last_approved and last_approved.approved_prompt:
        prompt_content = last_approved.approved_prompt
        prompt_changes = f"라운드 {last_approved.round_number}에서 승인된 프롬프트 사용"
    elif session.base_prompt_template:
        prompt_content = session.base_prompt_template.content
        prompt_changes = "기본 템플릿 사용"
    else:
        # 기본 프롬프트
        prompt_content = """당신은 실제로 시술을 받은 환자로서 자연스러운 후기를 작성합니다.

## 작성 원칙
1. 실제 환자가 쓴 것처럼 자연스러운 말투 사용
2. 구체적인 경험과 감정 묘사
3. 과장 없이 솔직하게 작성
4. 광고성 문구 사용 금지

{user_input}

자연스러운 후기를 작성해주세요:"""
        prompt_changes = "기본 프롬프트로 시작"

    # 라운드 생성
    new_round = OptimizationRound.objects.create(
        session=session,
        round_number=new_round_number,
        prompt_content=prompt_content,
        prompt_changes=prompt_changes,
        status='pending',
    )

    # 세션 상태 업데이트
    session.status = 'in_progress'
    session.current_round = new_round_number
    session.save()

    # 로그
    OptimizationLog.objects.create(
        session=session,
        round=new_round,
        log_type='info',
        message=f"라운드 {new_round_number} 시작",
    )

    return JsonResponse({
        "success": True,
        "round_id": new_round.id,
        "round_number": new_round_number,
        "prompt_content": prompt_content,
    })


@require_http_methods(["POST"])
def api_optimization_generate_next(request, pk):
    """다음 샘플 생성"""
    from apps.data.models import PromptOptimizationSession, OptimizationRound, OptimizationSample, OptimizationLog
    from apps.ml.services.llm_service import generate_review_with_prompt
    import random

    session = get_object_or_404(PromptOptimizationSession, pk=pk)

    # 현재 진행중인 라운드 찾기
    current_round = session.rounds.filter(
        status__in=['pending', 'generating']
    ).order_by('-round_number').first()

    if not current_round:
        return JsonResponse({"error": "진행중인 라운드가 없습니다."}, status=400)

    # 이미 목표 수만큼 생성했는지 확인
    generated_count = current_round.samples.count()
    if generated_count >= session.samples_per_round:
        current_round.status = 'generated'
        current_round.save()
        return JsonResponse({
            "success": True,
            "completed": True,
            "generated_count": generated_count,
            "message": "모든 샘플 생성 완료"
        })

    # 상태 업데이트
    if current_round.status == 'pending':
        current_round.status = 'generating'
        current_round.save()

    # 랜덤 페르소나 생성 (세션 옵션 반영)
    persona = _generate_random_persona(session)

    # 온도 범위 내에서 랜덤
    temp_min = getattr(session, 'temperature_min', 0.7) or 0.7
    temp_max = getattr(session, 'temperature_max', 0.95) or 0.95
    temperature = round(random.uniform(temp_min, temp_max), 2)

    # 최대 토큰
    max_tokens = getattr(session, 'max_tokens_generation', 4000) or 4000

    # 프롬프트 구성
    prompt = current_round.prompt_content

    # 변수 치환
    replacements = {
        "{user_input}": session.user_input or "",
        "{procedure_name}": session.procedure.name if session.procedure else "시술",
        "{age_group}": persona.get('age_group', '30대'),
        "{gender}": persona.get('gender', '여성'),
        "{job}": persona.get('job', '직장인'),
        "{tone}": persona.get('tone', '친근'),
        "{emoji}": persona.get('emoji', '적당히'),
        "{experience}": persona.get('experience', '첫시술'),
        "{writing_style}": persona.get('writing_style', '중간 길이'),
        "{motivation}": persona.get('motivation', '고민 해결'),
        "{satisfaction}": persona.get('satisfaction', '만족'),
        "{pain_level}": persona.get('pain_level', '견딜만함'),
        "{sentence_ending}": persona.get('sentence_ending', '~요'),
        "{paragraph_style}": persona.get('paragraph_style', '적당히'),
        "{detail_level}": persona.get('detail_level', '적당히'),
    }
    for key, val in replacements.items():
        prompt = prompt.replace(key, str(val))

    # 페르소나 상세 추가 (프롬프트에 명시적 지시 추가)
    persona_text = f"""

## 이번 리뷰의 작성자 설정
- **기본 정보**: {persona.get('age_group', '30대')} {persona.get('gender', '여성')}, {persona.get('job', '직장인')}
- **시술 경험**: {persona.get('experience', '첫시술')} / 시술 계기: {persona.get('motivation', '고민 해결')}
- **만족도**: {persona.get('satisfaction', '만족')} / 통증: {persona.get('pain_level', '견딜만함')}
- **글 스타일**: {persona.get('writing_style', '중간 길이')}, {persona.get('tone', '친근')}한 말투
- **문장 끝**: {persona.get('sentence_ending', '~요')} 스타일
- **이모지 사용**: {persona.get('emoji', '적당히')}
- **문단 스타일**: {persona.get('paragraph_style', '적당히')}
- **상세도**: {persona.get('detail_level', '적당히')}

위 설정에 맞는 자연스러운 후기를 작성해주세요. AI가 쓴 티가 나지 않도록 주의하세요.
"""
    full_prompt = prompt + persona_text

    try:
        # LLM 호출
        result = generate_review_with_prompt(
            prompt=full_prompt,
            model=session.model_used,
            temperature=temperature,
            max_tokens=max_tokens,
            return_usage=True,
        )

        # 샘플 저장
        sample = OptimizationSample.objects.create(
            round=current_round,
            sample_index=generated_count + 1,
            persona_settings=persona,
            generated_content=result.get('text', ''),
            input_tokens=result.get('input_tokens', 0),
            output_tokens=result.get('output_tokens', 0),
        )

        # 라운드 통계 업데이트
        current_round.generated_count = generated_count + 1
        current_round.input_tokens += result.get('input_tokens', 0)
        current_round.output_tokens += result.get('output_tokens', 0)
        current_round.cost_usd += result.get('cost_usd', 0.0)
        current_round.save()

        # 세션 통계 업데이트
        session.total_input_tokens += result.get('input_tokens', 0)
        session.total_output_tokens += result.get('output_tokens', 0)
        session.total_cost_usd += result.get('cost_usd', 0.0)
        session.save()

        # 완료 여부 확인
        is_completed = (generated_count + 1) >= session.samples_per_round
        if is_completed:
            current_round.status = 'generated'
            current_round.save()

        return JsonResponse({
            "success": True,
            "sample_id": sample.id,
            "sample_index": sample.sample_index,
            "content_preview": sample.generated_content[:200] + "..." if len(sample.generated_content) > 200 else sample.generated_content,
            "generated_count": generated_count + 1,
            "target_count": session.samples_per_round,
            "completed": is_completed,
        })

    except Exception as e:
        OptimizationLog.objects.create(
            session=session,
            round=current_round,
            log_type='error',
            message=f"샘플 생성 실패: {str(e)}",
        )
        return JsonResponse({"error": str(e)}, status=500)


def _generate_random_persona(session=None):
    """랜덤 페르소나 생성 (세션 옵션 반영)"""
    import random

    # 기본 옵션
    default_options = {
        "age_groups": ['20대 초반', '20대 중반', '20대 후반', '30대 초반', '30대 중반', '30대 후반', '40대', '40대 후반', '50대'],
        "genders": ['여성', '남성'],
        "gender_weights": [85, 15],
        "tones": ['친근', '정중', '털털', '조심스러운', '활발한', '차분한', '솔직한', '신중한'],
        "emoji_levels": ['많음', '적당히', '거의없음', '전혀없음'],
        "experiences": ['첫시술', '2~3회차', '5회 이상', '단골', '오랜만에 다시'],
        "jobs": ['직장인', '대학생', '주부', '자영업', '프리랜서', '전문직'],
        "writing_styles": ['짧고 간결', '중간 길이', '상세하게', '두서없이'],
        "motivations": ['고민 해결', '자기관리', '특별한 날', '친구 추천', '이벤트/할인'],
    }

    # 세션에서 커스텀 옵션 가져오기
    opts = default_options.copy()
    if session and session.persona_options:
        for key, val in session.persona_options.items():
            if val:
                opts[key] = val

    # 스타일 옵션
    style_opts = {
        "sentence_endings": ['~요', '~음', '~다', '혼용'],
        "paragraph_style": ['줄바꿈 많음', '붙여쓰기', '적당히'],
        "detail_level": ['핵심만', '적당히', '자세하게'],
    }
    if session and session.style_options:
        for key, val in session.style_options.items():
            if val:
                style_opts[key] = val

    return {
        "age_group": random.choice(opts["age_groups"]),
        "gender": random.choices(opts["genders"], weights=opts.get("gender_weights", [85, 15]))[0],
        "job": random.choice(opts.get("jobs", ['직장인'])),
        "tone": random.choice(opts["tones"]),
        "emoji": random.choice(opts["emoji_levels"]),
        "experience": random.choice(opts["experiences"]),
        "writing_style": random.choice(opts.get("writing_styles", ['중간 길이'])),
        "motivation": random.choice(opts.get("motivations", ['고민 해결'])),
        "sentence_ending": random.choice(style_opts["sentence_endings"]),
        "paragraph_style": random.choice(style_opts["paragraph_style"]),
        "detail_level": random.choice(style_opts["detail_level"]),
        # 추가 변수
        "satisfaction": random.choice(['매우 만족', '만족', '대체로 만족', '보통', '약간 아쉬움']),
        "pain_level": random.choice(['거의 없음', '약간 따끔', '견딜만함', '좀 아팠음']),
        "would_recommend": random.choice(['강추', '추천', '상황에 따라', '글쎄']),
    }


@require_http_methods(["POST"])
def api_optimization_analyze(request, pk):
    """라운드 분석 실행"""
    from apps.data.models import OptimizationRound, OptimizationLog
    from apps.ml.services.llm_service import generate_review_with_prompt

    round_obj = get_object_or_404(OptimizationRound, pk=pk)
    session = round_obj.session

    if round_obj.status not in ['generated', 'analyzed']:
        return JsonResponse({"error": "생성이 완료된 라운드만 분석 가능합니다."}, status=400)

    round_obj.status = 'analyzing'
    round_obj.save()

    # 샘플들 가져오기
    samples = list(round_obj.samples.all().order_by('sample_index'))
    if not samples:
        return JsonResponse({"error": "분석할 샘플이 없습니다."}, status=400)

    # 분석 깊이에 따른 샘플 수 결정
    analysis_depth = getattr(session, 'analysis_depth', 'detailed') or 'detailed'
    max_samples_map = {'basic': 20, 'detailed': 40, 'exhaustive': 50}
    max_samples = max_samples_map.get(analysis_depth, 40)

    # 샘플 텍스트 모음
    sample_texts = "\n\n---\n\n".join([
        f"[샘플 {s.sample_index}]\n{s.generated_content}"
        for s in samples[:max_samples]
    ])

    # 분석 최대 토큰
    max_tokens_analysis = getattr(session, 'max_tokens_analysis', 8000) or 8000

    # 분석 프롬프트 구성 (대폭 강화)
    analysis_prompt = f"""당신은 AI 생성 텍스트 탐지 전문가이자 콘텐츠 품질 분석가입니다.
다음 {len(samples)}개의 시술 후기 샘플을 **매우 엄격하고 정밀하게** 분석해주세요.

## 분석 맥락
- 이 텍스트들은 AI가 생성한 시술 후기입니다
- 목표: AI 탐지 도구(GPTZero, Originality.ai 등)를 통과하면서 실제 사람이 쓴 것처럼 보이는 것
- 실제 네이버 카페, 블로그, 커뮤니티에 게시될 예정

## 평가 기준 (각 10점 만점, 0.5점 단위)

### 1. AI 탐지 회피 (ai_detection_score)
**엄격하게 평가하세요. 대부분의 AI 텍스트는 6점 이하입니다.**

체크리스트:
- [ ] 문장 구조가 너무 균일하거나 정형화되어 있지 않은가?
- [ ] 접속사 사용이 자연스러운가? (그래서, 그런데, 근데 등)
- [ ] 문장 길이 변화가 자연스러운가? (짧은 문장과 긴 문장 혼용)
- [ ] AI 특유의 나열식 구조가 보이지 않는가?
- [ ] "~입니다", "~습니다" 같은 딱딱한 어미가 과도하지 않은가?
- [ ] 불필요하게 논리적이거나 체계적이지 않은가?
- [ ] 인간적인 비논리성, 두서없음이 적절히 있는가?
- [ ] Perplexity(예측 불가능성)가 충분히 높은가?
- [ ] Burstiness(문장 길이 변화)가 자연스러운가?

감점 요소:
- 모든 문장이 비슷한 길이 → -2점
- "첫째, 둘째" 또는 번호 나열 → -1점
- 과도한 접속사 패턴 → -1점
- 균일한 문단 구조 → -1점

### 2. 자연스러움 (naturalness_score)
**실제 카페 글과 비교해서 평가하세요.**

체크리스트:
- [ ] 실제 사람이 카페에 올릴 법한 글인가?
- [ ] 감정 표현이 과장되지 않고 진정성 있는가?
- [ ] 구어체와 문어체가 자연스럽게 섞여 있는가?
- [ ] 적절한 축약어, 신조어 사용이 있는가?
- [ ] 불필요한 부연설명이 없는가?
- [ ] 문맥에 맞는 감탄사 사용인가?
- [ ] "정말", "진짜", "너무" 등의 강조 표현이 과도하지 않은가?
- [ ] 글의 흐름이 자연스러운가?

감점 요소:
- 모든 문장에 "정말", "너무" 반복 → -2점
- 과도한 이모지 또는 전혀 없는 이모지 → -1점
- 광고성 표현 ("강력 추천", "꼭 가세요") → -2점
- 비현실적으로 긍정적인 톤 → -1점

### 3. 다양성 (diversity_score)
**샘플 간 차이를 엄격하게 분석하세요.**

체크리스트:
- [ ] 시작 문장이 얼마나 다양한가?
- [ ] 끝맺음 패턴이 다양한가?
- [ ] 문단 구조가 다양한가?
- [ ] 표현 방식이 다양한가?
- [ ] 감정 표현의 스펙트럼이 넓은가?
- [ ] 각 샘플이 독립적인 개성을 가지는가?

감점 요소:
- 50% 이상 비슷한 시작 문장 → -3점
- 반복되는 핵심 문구 → -2점
- 유사한 문단 구조 → -1점
- 동일한 감정 표현 패턴 → -1점

### 4. 정보 정확도 (accuracy_score)
체크리스트:
- [ ] 시술 관련 정보가 정확한가?
- [ ] 회복 기간, 통증 묘사가 현실적인가?
- [ ] 비용 관련 언급이 있다면 적절한가?
- [ ] 부작용/주의사항 언급이 균형 잡혀 있는가?
- [ ] 전문 용어 사용이 적절한가?

## 분석 대상 샘플 ({len(samples[:max_samples])}개)

{sample_texts}

## 응답 형식 (반드시 JSON)

{{
  "ai_detection_score": 6.5,
  "ai_detection_analysis": {{
    "sentence_uniformity": "높음/중간/낮음 + 구체적 예시",
    "perplexity_level": "높음/중간/낮음",
    "burstiness_level": "높음/중간/낮음",
    "problematic_patterns": ["패턴1", "패턴2"],
    "detection_risk": "높음/중간/낮음"
  }},
  "ai_detection_feedback": "상세한 피드백",

  "naturalness_score": 7.0,
  "naturalness_analysis": {{
    "tone_authenticity": "높음/중간/낮음",
    "emotional_range": "넓음/중간/좁음",
    "overused_expressions": ["표현1", "표현2"],
    "missing_elements": ["요소1", "요소2"]
  }},
  "naturalness_feedback": "상세한 피드백",

  "diversity_score": 5.5,
  "diversity_analysis": {{
    "opening_variety": "높음/중간/낮음 + 반복 패턴",
    "closing_variety": "높음/중간/낮음",
    "structure_variety": "높음/중간/낮음",
    "repeated_phrases": ["문구1", "문구2"]
  }},
  "diversity_feedback": "상세한 피드백",

  "accuracy_score": 8.5,
  "accuracy_feedback": "상세한 피드백",

  "overall_score": 6.9,
  "overall_feedback": "종합 평가 (강점과 약점 모두)",

  "critical_issues": [
    "가장 시급히 해결해야 할 문제 1",
    "가장 시급히 해결해야 할 문제 2"
  ],

  "improvement_suggestions": [
    {{
      "category": "ai_detection",
      "priority": "높음",
      "suggestion": "구체적 개선 방안",
      "example_before": "개선 전 예시",
      "example_after": "개선 후 예시"
    }}
  ],

  "best_samples": [1, 5, 12],
  "best_sample_reasons": ["좋은 이유1", "좋은 이유2"],
  "worst_samples": [3, 8],
  "worst_sample_reasons": ["나쁜 이유1", "나쁜 이유2"],

  "patterns_to_avoid": ["피해야 할 패턴1", "피해야 할 패턴2"],
  "patterns_to_encourage": ["권장 패턴1", "권장 패턴2"],

  "prompt_improvement_direction": "프롬프트 개선 방향 상세 설명"
}}

**중요**: 점수를 관대하게 주지 마세요. 실제 AI 탐지 도구 기준으로 엄격하게 평가해주세요.
대부분의 AI 생성 텍스트는 ai_detection_score가 5~7점 사이입니다.

JSON 형식으로만 응답해주세요:"""

    try:
        result = generate_review_with_prompt(
            prompt=analysis_prompt,
            model=session.analysis_model,
            temperature=0.2,  # 분석은 더 일관성 있게
            max_tokens=max_tokens_analysis,
            return_usage=True,
        )

        # JSON 파싱
        response_text = result.get('text', '{}')
        original_response = response_text

        # JSON 블록 추출
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            parts = response_text.split('```')
            if len(parts) >= 2:
                response_text = parts[1]

        try:
            analysis = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 기본 점수 설정
            analysis = {
                "ai_detection_score": 5.0,
                "naturalness_score": 5.0,
                "diversity_score": 5.0,
                "accuracy_score": 5.0,
                "overall_score": 5.0,
                "overall_feedback": "JSON 파싱 실패 - 원본 응답: " + original_response[:500],
                "parse_error": True,
            }

        # 라운드 업데이트
        round_obj.analysis_result = analysis
        round_obj.score_ai_detection = analysis.get('ai_detection_score') or 5.0
        round_obj.score_naturalness = analysis.get('naturalness_score') or 5.0
        round_obj.score_diversity = analysis.get('diversity_score') or 5.0
        round_obj.score_accuracy = analysis.get('accuracy_score') or 5.0
        round_obj.score_overall = analysis.get('overall_score') or 5.0
        round_obj.analysis_feedback = analysis.get('overall_feedback', '')
        round_obj.status = 'analyzed'
        round_obj.input_tokens += result.get('input_tokens', 0)
        round_obj.output_tokens += result.get('output_tokens', 0)
        round_obj.cost_usd += result.get('cost_usd', 0.0)
        round_obj.save()

        # 세션 통계 업데이트
        session.total_input_tokens += result.get('input_tokens', 0)
        session.total_output_tokens += result.get('output_tokens', 0)
        session.total_cost_usd += result.get('cost_usd', 0.0)
        session.save()

        # 로그
        OptimizationLog.objects.create(
            session=session,
            round=round_obj,
            log_type='analysis',
            message=f"분석 완료 - 종합점수: {analysis.get('overall_score', 'N/A')}",
            details=analysis,
        )

        return JsonResponse({
            "success": True,
            "analysis": analysis,
            "scores": {
                "ai_detection": round_obj.score_ai_detection,
                "naturalness": round_obj.score_naturalness,
                "diversity": round_obj.score_diversity,
                "accuracy": round_obj.score_accuracy,
                "overall": round_obj.score_overall,
            }
        })

    except Exception as e:
        OptimizationLog.objects.create(
            session=session,
            round=round_obj,
            log_type='error',
            message=f"분석 실패: {str(e)}",
        )
        round_obj.status = 'generated'
        round_obj.save()
        return JsonResponse({"error": str(e)}, status=500)


# =====================================================
# 최적화 API - 프롬프트 개선
# =====================================================

def api_optimization_suggestions(request, pk):
    """개선 제안 조회/생성"""
    from apps.data.models import OptimizationRound, OptimizationLog
    from apps.ml.services.llm_service import generate_review_with_prompt

    round_obj = get_object_or_404(OptimizationRound, pk=pk)
    session = round_obj.session

    if request.method == 'GET':
        return JsonResponse({
            "round_number": round_obj.round_number,
            "current_prompt": round_obj.prompt_content,
            "suggested_prompt": round_obj.suggested_prompt,
            "suggested_changes": round_obj.suggested_changes,
            "analysis_result": round_obj.analysis_result,
        })

    elif request.method == 'POST':
        # 새로운 제안 생성
        if round_obj.status != 'analyzed':
            return JsonResponse({"error": "분석이 완료된 라운드만 제안 생성 가능합니다."}, status=400)

        analysis = round_obj.analysis_result
        max_tokens_analysis = getattr(session, 'max_tokens_analysis', 8000) or 8000

        # 분석 세부 정보 추출
        ai_analysis = analysis.get('ai_detection_analysis', {})
        naturalness_analysis = analysis.get('naturalness_analysis', {})
        diversity_analysis = analysis.get('diversity_analysis', {})
        critical_issues = analysis.get('critical_issues', [])
        improvement_suggestions = analysis.get('improvement_suggestions', [])

        suggestion_prompt = f"""당신은 AI 탐지를 회피하면서 자연스러운 텍스트를 생성하는 프롬프트 엔지니어링 전문가입니다.
현재 프롬프트의 분석 결과를 바탕으로, **실질적으로 점수를 향상시킬 수 있는** 개선된 프롬프트를 작성해주세요.

## 현재 프롬프트
```
{round_obj.prompt_content}
```

## 상세 분석 결과

### AI 탐지 회피: {analysis.get('ai_detection_score', 'N/A')}/10
- 피드백: {analysis.get('ai_detection_feedback', '')}
- 문장 균일성: {ai_analysis.get('sentence_uniformity', 'N/A')}
- Perplexity: {ai_analysis.get('perplexity_level', 'N/A')}
- Burstiness: {ai_analysis.get('burstiness_level', 'N/A')}
- 문제 패턴: {json.dumps(ai_analysis.get('problematic_patterns', []), ensure_ascii=False)}

### 자연스러움: {analysis.get('naturalness_score', 'N/A')}/10
- 피드백: {analysis.get('naturalness_feedback', '')}
- 톤 진정성: {naturalness_analysis.get('tone_authenticity', 'N/A')}
- 감정 범위: {naturalness_analysis.get('emotional_range', 'N/A')}
- 과다 사용 표현: {json.dumps(naturalness_analysis.get('overused_expressions', []), ensure_ascii=False)}

### 다양성: {analysis.get('diversity_score', 'N/A')}/10
- 피드백: {analysis.get('diversity_feedback', '')}
- 시작 문장 다양성: {diversity_analysis.get('opening_variety', 'N/A')}
- 반복 문구: {json.dumps(diversity_analysis.get('repeated_phrases', []), ensure_ascii=False)}

### 정확도: {analysis.get('accuracy_score', 'N/A')}/10
- 피드백: {analysis.get('accuracy_feedback', '')}

## 가장 시급한 문제
{json.dumps(critical_issues, ensure_ascii=False, indent=2)}

## 피해야 할 패턴
{json.dumps(analysis.get('patterns_to_avoid', []), ensure_ascii=False)}

## 권장 패턴
{json.dumps(analysis.get('patterns_to_encourage', []), ensure_ascii=False)}

## 개선 방향
{analysis.get('prompt_improvement_direction', '')}

## 프롬프트 개선 원칙

1. **AI 탐지 회피 강화**
   - 문장 길이를 의도적으로 불균일하게 만드는 지시 추가
   - 논리적 흐름을 일부러 흐트러뜨리는 지시 추가
   - 불완전한 문장, 생략, 두서없음을 허용하는 지시 추가
   - "~입니다" 대신 구어체 어미 사용 지시

2. **자연스러움 향상**
   - 과도한 강조 표현 자제 지시
   - 실제 카페 글 스타일 참고 지시
   - 맥락에 맞는 감정 표현 지시
   - 광고성 표현 금지 목록 추가

3. **다양성 증가**
   - 시작 문장 변형 목록 제공
   - 금지 표현 목록 추가
   - 매번 다른 구조 사용 지시

4. **실용적 개선**
   - 너무 길거나 복잡한 지시는 피하기
   - 핵심 개선점에 집중
   - 측정 가능한 구체적 지시

## 응답 형식 (JSON)

{{
  "suggested_prompt": "개선된 전체 프롬프트 (마크다운 형식 가능, 충분히 길어도 됨)",
  "changes_summary": "주요 변경사항 요약 (불릿포인트)",
  "key_additions": ["추가된 핵심 지시 1", "추가된 핵심 지시 2"],
  "removed_or_modified": ["제거/수정된 부분 1", "제거/수정된 부분 2"],
  "expected_score_improvements": {{
    "ai_detection": "+1.5 예상",
    "naturalness": "+1.0 예상",
    "diversity": "+2.0 예상",
    "accuracy": "유지"
  }},
  "risk_factors": ["이 변경으로 인한 잠재적 위험 1"]
}}

**중요**: 프롬프트는 충분히 상세하고 구체적으로 작성해주세요. 길이 제한 없습니다.
JSON 형식으로만 응답해주세요:"""

        try:
            result = generate_review_with_prompt(
                prompt=suggestion_prompt,
                model=session.analysis_model,
                temperature=0.3,
                max_tokens=max_tokens_analysis,  # 프롬프트가 길어질 수 있으므로 충분히
                return_usage=True,
            )

            response_text = result.get('text', '{}')
            original_response = response_text  # 원본 보관

            # JSON 블록 추출 시도
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                parts = response_text.split('```')
                if len(parts) >= 2:
                    response_text = parts[1]

            try:
                suggestion = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                # JSON 파싱 실패 시 - 전체 텍스트를 프롬프트로 사용
                suggestion = {
                    "suggested_prompt": original_response,  # 원본 텍스트를 프롬프트로
                    "changes_summary": "JSON 파싱 실패로 원본 응답 사용",
                    "parse_error": str(e),
                }

            # 라운드 업데이트
            round_obj.suggested_prompt = suggestion.get('suggested_prompt', '') or original_response
            round_obj.suggested_changes = suggestion.get('changes_summary', '')
            round_obj.input_tokens += result.get('input_tokens', 0)
            round_obj.output_tokens += result.get('output_tokens', 0)
            round_obj.cost_usd += result.get('cost_usd', 0.0)
            round_obj.save()

            # 세션 통계 업데이트
            session.total_input_tokens += result.get('input_tokens', 0)
            session.total_output_tokens += result.get('output_tokens', 0)
            session.total_cost_usd += result.get('cost_usd', 0.0)
            session.save()

            return JsonResponse({
                "success": True,
                "suggestion": suggestion,
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["POST"])
def api_optimization_approve(request, pk):
    """제안 승인"""
    from apps.data.models import OptimizationRound, OptimizationLog

    round_obj = get_object_or_404(OptimizationRound, pk=pk)
    session = round_obj.session

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    # 승인할 프롬프트 결정
    if data.get('use_suggested', True):
        approved = round_obj.suggested_prompt or round_obj.prompt_content
    else:
        approved = round_obj.prompt_content

    round_obj.approved_prompt = approved
    round_obj.status = 'approved'
    round_obj.save()

    # 로그
    OptimizationLog.objects.create(
        session=session,
        round=round_obj,
        log_type='approval',
        message=f"라운드 {round_obj.round_number} 승인 완료",
    )

    # 자동 모드면 다음 라운드 체크
    auto_continue = False
    if session.mode == 'auto' and session.current_round < session.target_rounds:
        auto_continue = True

    return JsonResponse({
        "success": True,
        "approved_prompt": approved,
        "auto_continue": auto_continue,
    })


@require_http_methods(["POST"])
def api_optimization_modify(request, pk):
    """수정 후 승인"""
    from apps.data.models import OptimizationRound, OptimizationLog

    round_obj = get_object_or_404(OptimizationRound, pk=pk)
    session = round_obj.session

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 요청"}, status=400)

    modified_prompt = data.get('prompt', '').strip()
    if not modified_prompt:
        return JsonResponse({"error": "수정된 프롬프트를 입력해주세요."}, status=400)

    round_obj.approved_prompt = modified_prompt
    round_obj.status = 'approved'
    round_obj.save()

    # 로그
    OptimizationLog.objects.create(
        session=session,
        round=round_obj,
        log_type='approval',
        message=f"라운드 {round_obj.round_number} 수정 후 승인",
        details={"modified": True},
    )

    return JsonResponse({
        "success": True,
        "approved_prompt": modified_prompt,
    })


# =====================================================
# 최적화 API - 비교 & 내보내기
# =====================================================

def api_optimization_compare(request, pk):
    """라운드 비교"""
    from apps.data.models import PromptOptimizationSession

    session = get_object_or_404(PromptOptimizationSession, pk=pk)
    rounds = session.rounds.filter(status__in=['analyzed', 'approved']).order_by('round_number')

    comparison_data = []
    for r in rounds:
        comparison_data.append({
            "round_number": r.round_number,
            "status": r.status,
            "scores": {
                "ai_detection": r.score_ai_detection,
                "naturalness": r.score_naturalness,
                "diversity": r.score_diversity,
                "accuracy": r.score_accuracy,
                "overall": r.score_overall,
            },
            "generated_count": r.generated_count,
            "cost_usd": r.cost_usd,
            "prompt_changes": r.prompt_changes,
        })

    # 점수 추이 계산
    if len(comparison_data) >= 2:
        first = comparison_data[0]['scores']
        last = comparison_data[-1]['scores']
        improvement = {
            k: (last.get(k, 0) or 0) - (first.get(k, 0) or 0)
            for k in ['ai_detection', 'naturalness', 'diversity', 'accuracy', 'overall']
        }
    else:
        improvement = None

    return JsonResponse({
        "session_name": session.name,
        "total_rounds": session.current_round,
        "comparison": comparison_data,
        "improvement": improvement,
        "total_cost_usd": session.total_cost_usd,
    })


def api_optimization_export(request, pk):
    """세션 내보내기"""
    from apps.data.models import PromptOptimizationSession
    from django.http import HttpResponse
    import csv
    from io import StringIO

    session = get_object_or_404(PromptOptimizationSession, pk=pk)
    export_format = request.GET.get('format', 'json')

    if export_format == 'json':
        # JSON 내보내기
        rounds_data = []
        for r in session.rounds.all().order_by('round_number'):
            samples_data = [{
                "index": s.sample_index,
                "content": s.generated_content,
                "persona": s.persona_settings,
            } for s in r.samples.all().order_by('sample_index')]

            rounds_data.append({
                "round_number": r.round_number,
                "prompt": r.prompt_content,
                "approved_prompt": r.approved_prompt,
                "scores": {
                    "ai_detection": r.score_ai_detection,
                    "naturalness": r.score_naturalness,
                    "diversity": r.score_diversity,
                    "accuracy": r.score_accuracy,
                    "overall": r.score_overall,
                },
                "analysis": r.analysis_result,
                "samples": samples_data,
            })

        export_data = {
            "session": {
                "id": session.id,
                "name": session.name,
                "created_at": session.created_at.isoformat(),
                "total_cost_usd": session.total_cost_usd,
            },
            "rounds": rounds_data,
        }

        response = JsonResponse(export_data, json_dumps_params={'ensure_ascii': False, 'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="optimization_{session.id}.json"'
        return response

    elif export_format == 'csv':
        # CSV 내보내기 (샘플 중심)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Round', 'Sample', 'Content', 'Persona', 'Overall Score'])

        for r in session.rounds.all().order_by('round_number'):
            for s in r.samples.all().order_by('sample_index'):
                writer.writerow([
                    r.round_number,
                    s.sample_index,
                    s.generated_content,
                    json.dumps(s.persona_settings, ensure_ascii=False),
                    r.score_overall,
                ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="optimization_{session.id}.csv"'
        return response


def api_optimization_logs(request, pk):
    """세션 로그 조회"""
    from apps.data.models import PromptOptimizationSession

    session = get_object_or_404(PromptOptimizationSession, pk=pk)

    logs = session.logs.all().order_by('-created_at')[:100]
    logs_data = [{
        "id": log.id,
        "type": log.log_type,
        "message": log.message,
        "round_number": log.round.round_number if log.round else None,
        "created_at": log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    } for log in logs]

    return JsonResponse({"logs": logs_data})


def api_optimization_round_samples(request, pk):
    """라운드의 샘플 조회"""
    from apps.data.models import OptimizationRound

    round_obj = get_object_or_404(OptimizationRound, pk=pk)

    samples = round_obj.samples.all().order_by('sample_index')
    samples_data = [{
        "id": sample.id,
        "index": sample.sample_index,
        "content": sample.generated_content,
        "persona": sample.persona_settings,
        "scores": sample.individual_scores,
    } for sample in samples]

    return JsonResponse({
        "success": True,
        "round_id": round_obj.id,
        "round_number": round_obj.round_number,
        "prompt": round_obj.approved_prompt or round_obj.prompt_content,
        "samples": samples_data,
        "count": len(samples_data),
    })
