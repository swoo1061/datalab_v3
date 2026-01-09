from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.data.models import ClinicGuide
from apps.ml.services.llm.registry import LLM_MODELS
from apps.data.models import ClinicGuide, ClinicDoctor, ClinicPrice


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

@require_GET
def llm_model_list_api(request):
    return JsonResponse(
        {
            "count": len(LLM_MODELS),
            "results": LLM_MODELS,
        },
        json_dumps_params={"ensure_ascii": False},
    )