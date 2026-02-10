from __future__ import annotations

from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.models import SystemPermission
from apps.data.permissions import (
    get_user_permission,
    normalize_user_role,
)
from apps.data.views_api import CsrfExemptSessionAuthentication, HeaderSessionAuthentication
from apps.data.services.audit_logger import log_audit_event


def _is_permission_admin(user) -> bool:
    role = normalize_user_role(user)
    return role in {"admin", "ceo"}


def _serialize_user_permissions(user):
    rows = {
        row["key"]: bool(row["is_enabled"])
        for row in SystemPermission.objects.filter(user=user).values("key", "is_enabled")
    }
    payload = {}
    for key, _label in SystemPermission.KEY_CHOICES:
        payload[key] = rows.get(key, get_user_permission(user, key))
    return payload


class SystemPermissionMeView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        key = (request.GET.get("key") or "").strip()
        if key and key not in dict(SystemPermission.KEY_CHOICES):
            return Response({"message": "invalid_key"}, status=status.HTTP_400_BAD_REQUEST)

        if key:
            return Response(
                {"key": key, "enabled": get_user_permission(request.user, key)},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "permissions": _serialize_user_permissions(request.user),
            },
            status=status.HTTP_200_OK,
        )


class SystemPermissionUserListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_permission_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        User = get_user_model()
        q = (request.GET.get("q") or "").strip().lower()
        users = User.objects.filter(is_active=True).select_related("profile").order_by("username")

        rows = []
        for u in users:
            profile = getattr(u, "profile", None)
            name = getattr(profile, "name", None) or u.get_full_name() or u.username
            role = normalize_user_role(u)
            item = {
                "id": u.id,
                "username": u.username,
                "name": name,
                "role": role,
                "permissions": _serialize_user_permissions(u),
            }
            if q:
                hay = f"{item['name']} {item['username']} {item['role']}".lower()
                if q not in hay:
                    continue
            rows.append(item)

        return Response(
            {
                "count": len(rows),
                "keys": [{"key": k, "label": v} for k, v in SystemPermission.KEY_CHOICES],
                "results": rows,
            },
            status=status.HTTP_200_OK,
        )


class SystemPermissionUserDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        if not _is_permission_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        User = get_user_model()
        target = User.objects.filter(id=user_id, is_active=True).first()
        if not target:
            return Response({"message": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data or {}
        permissions = payload.get("permissions")
        if not isinstance(permissions, dict):
            return Response({"message": "permissions_required"}, status=status.HTTP_400_BAD_REQUEST)

        valid_keys = dict(SystemPermission.KEY_CHOICES)
        updated = {}
        before_permissions = _serialize_user_permissions(target)
        for key, value in permissions.items():
            if key not in valid_keys:
                continue
            enabled = bool(value)
            row, _created = SystemPermission.objects.get_or_create(
                user=target,
                key=key,
                defaults={"is_enabled": enabled, "updated_by": request.user},
            )
            if row.is_enabled != enabled or row.updated_by_id != request.user.id:
                row.is_enabled = enabled
                row.updated_by = request.user
                row.save(update_fields=["is_enabled", "updated_by", "updated_at"])
            updated[key] = enabled

        after_permissions = _serialize_user_permissions(target)
        if updated:
            log_audit_event(
                actor=request.user,
                event_type="permission.update",
                target_type="user",
                target_id=target.id,
                before={k: before_permissions.get(k) for k in updated.keys()},
                after={k: after_permissions.get(k) for k in updated.keys()},
                metadata={
                    "target_username": target.username,
                    "changed_keys": list(updated.keys()),
                    "source": "system_permissions_api",
                },
            )

        return Response(
            {
                "ok": True,
                "user_id": target.id,
                "updated": updated,
                "permissions": _serialize_user_permissions(target),
            },
            status=status.HTTP_200_OK,
        )
