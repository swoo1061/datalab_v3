from django.http import JsonResponse
from apps.data.models import ClinicGuide


def clinic_detail_api(request, clinic_id):
    clinic = ClinicGuide.objects.get(id=clinic_id, is_active=True)

    return JsonResponse(
        {
            "clinic": {
                "id": clinic.id,
                "name": clinic.name,
                "location": clinic.location,
                "hours": clinic.hours,
                "parking": clinic.parking,
                "process": clinic.process,
                "features": clinic.features,
            },

            # ✅ 어드민에 실제 들어있는 데이터
            "doctors": clinic.doctors or [],
            "price_list": clinic.price_list or [],
            "consultants": clinic.consultants or [],
            "aftercare": clinic.aftercare or {},
        },
        json_dumps_params={"ensure_ascii": False},
    )