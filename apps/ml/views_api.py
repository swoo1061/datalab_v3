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
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1": "gpt-4.1",
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
            {"error": "use /api/ml/gangnam_review/"},
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

    try:
        result = generate_review_with_prompt(
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
            "usage": {
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "cost_usd": round(result["cost_usd"], 6),
                "cost_krw": round(cost_krw, 2),
            }
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
