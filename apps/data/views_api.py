from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.data.models import ClinicGuide
from apps.ml.services.llm.registry import LLM_MODELS


@csrf_exempt
def clinic_list_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"}, status=405)

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
def llm_model_list_api(request):
    return JsonResponse(
        {
            "count": len(LLM_MODELS),
            "results": LLM_MODELS,
        },
        json_dumps_params={"ensure_ascii": False},
    )