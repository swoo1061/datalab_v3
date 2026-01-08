import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# ✅ 기존 LLM 서비스 import
from apps.ml.services.llm_service import generate_review


@csrf_exempt
def review_generate_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    # Electron에서 보내는 값
    clinic_name = data.get("clinic_name")
    platform = data.get("platform")
    procedure = data.get("procedure")
    keywords = data.get("keywords", [])

    if not clinic_name or not platform or not procedure:
        return JsonResponse(
            {"error": "missing required fields"},
            status=400
        )

    # 🔥 여기서 기존 LLM 호출
    review_text = generate_review(
        clinic_name=clinic_name,
        platform=platform,
        procedure=procedure,
        keywords=keywords,
    )

    return JsonResponse({
        "review_text": review_text
    })