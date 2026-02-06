from __future__ import annotations

from apps.data.models import SystemPermission


def normalize_user_role(user) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    if user.is_superuser or user.groups.filter(name="staff").exists():
        return "admin"
    profile = getattr(user, "profile", None)
    role = getattr(profile, "position", "") if profile else ""
    return str(role or "").strip().lower()


def default_permission_for_user(user, key: str) -> bool:
    role = normalize_user_role(user)
    if key == SystemPermission.KEY_ATTENDANCE_REQUESTS:
        return role in {"admin", "ceo"}
    if key == SystemPermission.KEY_WEB_DASHBOARD:
        return role in {"admin", "ceo", "leader"}
    if key == SystemPermission.KEY_VACATION_ADMIN:
        return role in {"admin", "ceo", "leader"}
    if key == SystemPermission.KEY_EMPLOYEE_MANAGEMENT:
        return role in {"admin", "ceo", "leader"}
    if key == SystemPermission.KEY_SYSTEM_MONITOR:
        return role in {"admin", "ceo"}
    return False


def get_user_permission(user, key: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    row = (
        SystemPermission.objects
        .filter(user=user, key=key)
        .values("is_enabled")
        .first()
    )
    if row is None:
        return default_permission_for_user(user, key)
    return bool(row["is_enabled"])


def can_access_web_dashboard(user) -> bool:
    return get_user_permission(user, SystemPermission.KEY_WEB_DASHBOARD)
