import json
import random
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.ml.services.llm_service import (
    generate_review_with_prompt_enforced,
    generate_title_suggestions,
    apply_review_type_guard,
)
from apps.ml.services.prompt_generator import build_ft_prompt_from_models, build_prompt_from_models
from apps.ml.services.usage_logger import log_llm_usage
from apps.data.models import PromptTemplate, GeneratedReview, ClinicGuide, Persona

MODEL_ALIAS_MAP = {
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5.2": "gpt-5.2",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1": "gpt-4.1",
    "claude-4.5": "claude-sonnet-4-5-20250929",
    "claude-opus": "claude-opus-4-5-20251101",
    # "ft:gpt-3.5-turbo-0125:personal::D2AzRPLe": "ft:gpt-3.5-turbo-0125:personal::D2AzRPLe", --- IGNORE ---
    # "ft:gpt-4.1-2025-04-14:personal::D3C9lMYD": "ft:gpt-4.1-2025-04-14:personal::D3C9lMYD", --- IGNORE ---
    # Legacy aliases -> current Gugong model
    "ft:gpt-4.1-2025-04-14:personal::D3J40yRV": "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    "ft:gpt-4.1-2025-04-14:personal:D3gDuLBk:": "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk": "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
}

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
