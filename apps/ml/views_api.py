import json
import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from django.views.decorators.http import require_http_methods
from apps.ml.services.llm_service import generate_review_with_prompt
from apps.data.models import PromptTemplate

MODEL_ALIAS_MAP = {
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5.2": "gpt-5.2",
    "claude-4.5": "claude-sonnet-4-5-20250929",
    "claude-opus": "claude-opus-4-5-20251101",
}

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
            {"error": "use /api/ml/gangnam/review/"},
            status=400
        )

    raw_model = data.get("model")
    model = MODEL_ALIAS_MAP.get(raw_model)
    if not model:
        return JsonResponse({"error": f"unknown model: {raw_model}"}, status=400)

    prompt = context.get("prompt")
    if not prompt:
        return JsonResponse({"error": "missing prompt"}, status=400)

    try:
        review_text = generate_review_with_prompt(
            prompt=prompt,
            model=model,
            max_tokens=1200,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({
        "review_text": review_text,
        "model": model,
    })

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
    model = data.get("model", "claude-sonnet-4-5-20250929")
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

    template = PromptTemplate.objects.filter(
        mode="app_gangnam", is_active=True
    ).order_by("-is_default").first()

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

    if template:
        prompt = template.content.format(**prompt_vars)
    else:
        prompt = f"""당신은 강남언니 앱에 시술 후기를 작성하는 실제 고객입니다.
## 작성자 페르소나
- 연령/성별: {persona_age} {persona_gender}
- 말투: {persona_tone}
- 이모티콘 사용: {emoji_usage}

## 시술 정보
- 병원명: {hospital_name}
- 시술 종류: {procedure_type}
{prompt_vars['procedure_detail_line']}
{prompt_vars['doctor_line']}
{prompt_vars['anesthesia_line']}
{prompt_vars['price_line']}
- 시술일: {procedure_date_str}
- 작성일: {write_date_str}

## 경험
- 만족도: {satisfaction_level}
{prompt_vars['before_concern_line']}
{prompt_vars['good_points_line']}
{prompt_vars['bad_points_line']}

## 태그
- 이유: {reason_tags}
- 좋았던 점: {good_tags}
- 아쉬운 점: {bad_tags}

JSON만 출력:"""

    try:
        result = generate_review_with_prompt(
            prompt, model=model, return_usage=True, temperature=temperature
        )

        text = result["text"].strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(text)
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
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)