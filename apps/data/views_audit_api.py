from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.models import AuditEvent
from apps.data.permissions import normalize_user_role
from apps.data.views_api import CsrfExemptSessionAuthentication, HeaderSessionAuthentication


def _is_audit_admin(user) -> bool:
    role = normalize_user_role(user)
    return role in {"admin", "ceo"}


def _actor_name(user) -> str:
    if not user:
        return "system"
    profile = getattr(user, "profile", None)
    return getattr(profile, "name", None) or user.get_full_name() or user.username


def _display_user_name(user) -> str:
    if not user:
        return "-"
    profile = getattr(user, "profile", None)
    return getattr(profile, "name", None) or user.get_full_name() or user.username


def _event_type_label(key: str) -> str:
    return dict(AuditEvent.EVENT_TYPE_CHOICES).get(key, key or "-")


def _target_type_label(key: str) -> str:
    labels = {
        "user": "사용자",
        "clinic": "병원",
        "post": "게시글",
        "system": "시스템",
    }
    raw = str(key or "").strip().lower()
    return labels.get(raw, raw or "-")


class AuditEventListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_audit_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        limit = max(1, min(int(request.GET.get("limit", 50)), 200))
        offset = max(0, int(request.GET.get("offset", 0)))
        q = (request.GET.get("q") or "").strip()
        event_type = (request.GET.get("event_type") or "").strip()
        user_id = (request.GET.get("user_id") or "").strip()
        from_date = parse_date((request.GET.get("from") or "").strip())
        to_date = parse_date((request.GET.get("to") or "").strip())

        qs = AuditEvent.objects.select_related("actor").all()
        if event_type:
            qs = qs.filter(event_type=event_type)
        if user_id.isdigit():
            qs = qs.filter(actor_id=int(user_id))
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        if q:
            qs = qs.filter(
                Q(event_type__icontains=q)
                | Q(target_type__icontains=q)
                | Q(target_id__icontains=q)
                | Q(metadata_json__icontains=q)
                | Q(actor__username__icontains=q)
                | Q(actor__profile__name__icontains=q)
            )

        total = qs.count()
        rows = qs[offset:offset + limit]
        target_user_ids = [
            int(r.target_id)
            for r in rows
            if str(r.target_type or "").lower() == "user" and str(r.target_id or "").isdigit()
        ]
        target_user_map = {}
        if target_user_ids:
            User = get_user_model()
            target_user_map = User.objects.filter(id__in=target_user_ids).select_related("profile").in_bulk()
        results = []
        for row in rows:
            target_name = ""
            if str(row.target_type or "").lower() == "user" and str(row.target_id or "").isdigit():
                target_user = target_user_map.get(int(row.target_id))
                target_name = _display_user_name(target_user)
            if not target_name:
                target_name = str((row.metadata_json or {}).get("target_username") or "").strip()
            results.append(
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "event_type_label": _event_type_label(row.event_type),
                    "target_type": row.target_type,
                    "target_type_label": _target_type_label(row.target_type),
                    "target_id": row.target_id,
                    "target_name": target_name,
                    "actor_id": row.actor_id,
                    "actor_name": _actor_name(row.actor),
                    "actor_username": row.actor.username if row.actor else "",
                    "before": row.before_json or {},
                    "after": row.after_json or {},
                    "metadata": row.metadata_json or {},
                    "created_at": timezone.localtime(row.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        User = get_user_model()
        users = User.objects.filter(is_active=True).order_by("username")[:200]
        user_options = [{"id": u.id, "name": _actor_name(u), "username": u.username} for u in users]

        return Response(
            {
                "count": len(results),
                "total": total,
                "limit": limit,
                "offset": offset,
                "event_types": [{"key": k, "label": v} for k, v in AuditEvent.EVENT_TYPE_CHOICES],
                "users": user_options,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )
