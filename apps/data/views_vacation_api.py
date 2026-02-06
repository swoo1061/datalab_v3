from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.models import VacationRequest, CalendarMemo, SystemPermission
from apps.data.serializers_vacation import VacationRequestSerializer
from apps.data.views_api import CsrfExemptSessionAuthentication, HeaderSessionAuthentication, VACATION_MEMO_PLATFORM
from apps.data.permissions import normalize_user_role, get_user_permission


ANNUAL_TOTAL_DAYS = Decimal("15.0")


def _is_vacation_admin(user) -> bool:
    return normalize_user_role(user) in {"admin", "ceo", "leader"}


def _parse_year(value: str):
    raw = (value or "").strip()
    if not raw:
        return timezone.localdate().year
    try:
        return int(raw)
    except Exception:
        return None


def _get_user_stats(user_ids, year: int):
    qs = VacationRequest.objects.filter(start_date__year=year, user_id__in=user_ids)
    stats = {uid: {"used": Decimal("0.0"), "pending": Decimal("0.0")} for uid in user_ids}
    for row in qs:
        bucket = stats.setdefault(row.user_id, {"used": Decimal("0.0"), "pending": Decimal("0.0")})
        if row.status == "approved":
            bucket["used"] += row.days
        elif row.status == "pending":
            bucket["pending"] += row.days
    for uid in stats:
        used = stats[uid]["used"]
        pending = stats[uid]["pending"]
        stats[uid]["remaining"] = max(Decimal("0.0"), ANNUAL_TOTAL_DAYS - used - pending)
    return stats


def _requester_label(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "name", None) or user.get_full_name() or user.username


def _notify_admins_on_request(req: VacationRequest):
    User = get_user_model()
    candidates = (
        User.objects
        .filter(is_active=True)
        .select_related("profile")
        .prefetch_related("groups")
        .distinct()
    )
    notify_users = [
        user for user in candidates
        if normalize_user_role(user) in {"admin", "ceo", "leader"}
    ]
    if not notify_users:
        notify_users = list(User.objects.filter(is_active=True, is_superuser=True).distinct())

    requester = _requester_label(req.user)
    period = req.start_date if req.start_date == req.end_date else f"{req.start_date} ~ {req.end_date}"
    content = (
        f"[휴가 신청] {requester}\n"
        f"기간: {period}\n"
        f"유형: {req.get_type_display()} / {req.days}일\n"
        f"사유: {req.reason or '-'}"
    )
    now = timezone.now()
    today = timezone.localdate()
    for admin in notify_users:
        CalendarMemo.objects.create(
            user=admin,
            clinic=None,
            date=today,
            content=content,
            platform=VACATION_MEMO_PLATFORM,
            remind_at=now,
            is_read=False,
        )


def _notify_requester_on_review(req: VacationRequest):
    result = "승인" if req.status == "approved" else "반려"
    period = req.start_date if req.start_date == req.end_date else f"{req.start_date} ~ {req.end_date}"
    content = (
        f"[휴가 {result}] {req.get_type_display()}\n"
        f"기간: {period}\n"
        f"사용일수: {req.days}일\n"
        f"비고: {req.review_note or '-'}"
    )
    now = timezone.now()
    today = timezone.localdate()
    CalendarMemo.objects.create(
        user=req.user,
        clinic=None,
        date=today,
        content=content,
        platform=VACATION_MEMO_PLATFORM,
        remind_at=now,
        is_read=False,
    )


class MyVacationListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = _parse_year(request.GET.get("year"))
        if not year:
            return Response({"message": "invalid_year"}, status=status.HTTP_400_BAD_REQUEST)
        qs = VacationRequest.objects.filter(user=request.user, start_date__year=year).order_by("-created_at")
        stats = _get_user_stats([request.user.id], year).get(request.user.id, {})
        return Response(
            {
                "year": year,
                "summary": {
                    "total_days": float(ANNUAL_TOTAL_DAYS),
                    "used_days": float(stats.get("used", Decimal("0.0"))),
                    "pending_days": float(stats.get("pending", Decimal("0.0"))),
                    "remaining_days": float(stats.get("remaining", Decimal("0.0"))),
                },
                "results": VacationRequestSerializer(qs, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        payload = request.data or {}
        type_value = (payload.get("type") or "").strip()
        start_raw = payload.get("start_date")
        end_raw = payload.get("end_date") or start_raw
        start_date = parse_date(start_raw or "")
        end_date = parse_date(end_raw or "")
        reason = (payload.get("reason") or "").strip()

        if type_value not in {"annual", "half_am", "half_pm"}:
            return Response({"message": "type_required"}, status=status.HTTP_400_BAD_REQUEST)
        if not start_date or not end_date:
            return Response({"message": "date_required"}, status=status.HTTP_400_BAD_REQUEST)
        if end_date < start_date:
            return Response({"message": "invalid_date_range"}, status=status.HTTP_400_BAD_REQUEST)
        if type_value in {"half_am", "half_pm"} and end_date != start_date:
            return Response({"message": "half_day_single_date"}, status=status.HTTP_400_BAD_REQUEST)

        req = VacationRequest.objects.create(
            user=request.user,
            type=type_value,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status="pending",
        )
        _notify_admins_on_request(req)
        return Response(VacationRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class VacationAdminListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_vacation_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        year = _parse_year(request.GET.get("year"))
        if not year:
            return Response({"message": "invalid_year"}, status=status.HTTP_400_BAD_REQUEST)
        status_filter = (request.GET.get("status") or "").strip()
        q = (request.GET.get("q") or "").strip().lower()

        qs = VacationRequest.objects.filter(start_date__year=year).select_related("user", "user__profile").order_by("-created_at")
        if status_filter in {"pending", "approved", "rejected"}:
            qs = qs.filter(status=status_filter)
        if q:
            qs = qs.filter(
                Q(user__username__icontains=q)
                | Q(user__profile__name__icontains=q)
            )

        rows = list(qs)
        stats = _get_user_stats({r.user_id for r in rows}, year)
        data = []
        for row in rows:
            payload = VacationRequestSerializer(row).data
            s = stats.get(row.user_id, {})
            payload["remaining_days"] = float(s.get("remaining", Decimal("0.0")))
            payload["used_days"] = float(s.get("used", Decimal("0.0")))
            payload["pending_days"] = float(s.get("pending", Decimal("0.0")))
            data.append(payload)

        return Response({"year": year, "results": data}, status=status.HTTP_200_OK)


class VacationAdminDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, request_id: int):
        if not _is_vacation_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        action = (request.data or {}).get("action")
        review_note = (request.data or {}).get("review_note") or ""

        req = VacationRequest.objects.filter(id=request_id).first()
        if not req:
            return Response({"message": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        if action not in {"approve", "reject"}:
            return Response({"message": "invalid_action"}, status=status.HTTP_400_BAD_REQUEST)

        req.status = "approved" if action == "approve" else "rejected"
        req.review_note = review_note
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
        _notify_requester_on_review(req)
        return Response(VacationRequestSerializer(req).data, status=status.HTTP_200_OK)


class VacationAdminSummaryView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_vacation_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        year = _parse_year(request.GET.get("year"))
        if not year:
            return Response({"message": "invalid_year"}, status=status.HTTP_400_BAD_REQUEST)
        q = (request.GET.get("q") or "").strip().lower()
        role = (request.GET.get("role") or "").strip().lower()

        User = get_user_model()
        qs = (
            User.objects
            .filter(is_active=True)
            .select_related("profile")
            .order_by("username")
        )
        rows = []
        for u in qs:
            profile = getattr(u, "profile", None)
            name = getattr(profile, "name", None) or u.get_full_name() or u.username
            position = getattr(profile, "position", None) or ("admin" if u.is_superuser else "")
            if role and role != str(position).lower():
                continue
            if q:
                hay = f"{name} {u.username} {position}".lower()
                if q not in hay:
                    continue
            rows.append({
                "id": u.id,
                "username": u.username,
                "name": name,
                "position": position,
                "email": u.email,
                "phone": getattr(profile, "phone", ""),
                "birth_date": getattr(profile, "birth_date", None),
                "hire_date": getattr(profile, "hire_date", None),
                "work_start_hour": getattr(profile, "work_start_hour", 9),
            })

        stats = _get_user_stats([r["id"] for r in rows], year)
        for r in rows:
            s = stats.get(r["id"], {})
            r["total_days"] = float(ANNUAL_TOTAL_DAYS)
            r["used_days"] = float(s.get("used", Decimal("0.0")))
            r["pending_days"] = float(s.get("pending", Decimal("0.0")))
            r["remaining_days"] = float(s.get("remaining", Decimal("0.0")))

        return Response({"year": year, "results": rows}, status=status.HTTP_200_OK)
