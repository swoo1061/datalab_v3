from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.permissions import normalize_user_role
from apps.data.views_api import CsrfExemptSessionAuthentication, HeaderSessionAuthentication


def _is_monitor_admin(user) -> bool:
    role = normalize_user_role(user)
    return role in {"admin", "ceo"}


def _to_bool(value) -> bool:
    return bool(str(value or "").strip())


def _check_openai(connectivity: bool) -> dict:
    key = getattr(settings, "OPENAI_API_KEY", "") or ""
    configured = _to_bool(key)
    result = {
        "provider": "openai",
        "configured": configured,
        "connected": False,
        "detail": "missing_api_key" if not configured else "not_checked",
    }
    if not configured or not connectivity:
        return result

    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        client.models.list()
        result["connected"] = True
        result["detail"] = "ok"
        return result
    except Exception as exc:
        result["detail"] = f"{exc.__class__.__name__}"
        return result


def _check_anthropic(connectivity: bool) -> dict:
    key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    configured = _to_bool(key)
    result = {
        "provider": "anthropic",
        "configured": configured,
        "connected": False,
        "detail": "missing_api_key" if not configured else "not_checked",
    }
    if not configured or not connectivity:
        return result

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=key)
        client.models.list()
        result["connected"] = True
        result["detail"] = "ok"
        return result
    except Exception as exc:
        result["detail"] = f"{exc.__class__.__name__}"
        return result


class SystemMonitorLLMStatusView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_monitor_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        connectivity = str(request.GET.get("connectivity") or "1").strip() not in {"0", "false", "False"}
        openai_result = _check_openai(connectivity)
        anthropic_result = _check_anthropic(connectivity)

        return Response(
            {
                "ok": True,
                "connectivity_checked": connectivity,
                "checked_at": timezone.now().isoformat(),
                "providers": [openai_result, anthropic_result],
            },
            status=status.HTTP_200_OK,
        )
