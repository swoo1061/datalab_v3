import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# ✅ 기존 LLM 서비스 import
from apps.ml.services.llm_service import generate_review_with_prompt

MODEL_ALIAS_MAP = {
    # OpenAI
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5.2": "gpt-5.2",

    # Claude
    "claude-4.5": "claude-sonnet-4-5-20250929",
    "claude-opus": "claude-opus-4-5-20251101",
}

@csrf_exempt
def review_generate_api(request):
    print("🔥 LLM API HIT", request.method)

    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception as e:
        print("❌ JSON parse error:", e)
        return JsonResponse({"error": "invalid json"}, status=400)

    clinic_id = data.get("clinic_id")
    raw_model = data.get("model", "gpt-5-mini")
    model = MODEL_ALIAS_MAP.get(raw_model)

    if not model:
        return JsonResponse(
            {"error": f"unknown model: {raw_model}"},
            status=400
        )
    context = data.get("context", {})

    personas = context.get("personas", [])
    review_type = context.get("reviewType")
    review_timing = context.get("reviewTiming")
    keywords = context.get("keywords", [])

    if not clinic_id:
        return JsonResponse({"error": "missing clinic_id"}, status=400)

    # 🔥 여기서는 prompt만 만든다
    prompt_parts = []

    if personas:
        prompt_parts.append(f"페르소나: {', '.join(personas)}")

    if review_type:
        prompt_parts.append(f"리뷰 유형: {review_type}")

    if review_timing:
        prompt_parts.append(f"후기 시점: {review_timing}")

    if keywords:
        prompt_parts.append(f"강조 키워드: {', '.join(keywords)}")

    prompt_parts.append(
        "위 조건을 반영해 실제 사용자가 작성한 것처럼 "
        "과한 광고 느낌 없이 자연스럽고 솔직한 후기를 작성해주세요."
        "문장은 중간에서 끓기지 않도록 완결된 문장으로 마우리할 것"
        "마지막 문장은 후기의 결론이나ㅓ 현재 심정으로 자연스럽게 정리할 것"
    )

    prompt = "\n".join(prompt_parts)

    try:
        review_text = generate_review_with_prompt(
            prompt=prompt,
            model=model,
            max_tokens=1500,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse(
            {"error": "llm generation failed", "detail": str(e)},
            status=500
        )

    return JsonResponse({
        "review_text": review_text,
        "prompt": prompt,
        "model": model,
    })