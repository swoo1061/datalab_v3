from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime

from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.models import AttendanceRecord, AttendanceCorrectionRequest, CalendarMemo
from apps.data.serializers_attendance import (
    AttendanceRecordSerializer,
    AttendanceCorrectionRequestSerializer,
)
from apps.data.views_api import CsrfExemptSessionAuthentication, HeaderSessionAuthentication


def _parse_month(value: str):
    raw = (value or "").strip()
    if not raw:
        today = timezone.localdate()
        return date(today.year, today.month, 1)
    try:
        year, month = map(int, raw.split("-"))
        return date(year, month, 1)
    except Exception:
        return None


def _next_month(d: date):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _get_or_create_today(user):
    today = timezone.localdate()
    record, _ = AttendanceRecord.objects.get_or_create(
        user=user,
        work_date=today,
        defaults={"status": "working"},
    )
    return record


def _parse_datetime_value(raw):
    if not raw:
        return None
    if isinstance(raw, datetime):
        parsed = raw
    elif isinstance(raw, str):
        parsed = parse_datetime(raw)
        if parsed is None:
            return None
    else:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _make_requester_label(user):
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "name", None):
        return profile.name
    return user.get_full_name() or user.username


def _notify_ceo_for_correction(req: AttendanceCorrectionRequest):
    User = get_user_model()
    notify_users = User.objects.filter(
        is_active=True,
    ).filter(
        Q(profile__position__in=["ceo", "manager", "leader"])
        | Q(is_superuser=True)
        | Q(groups__name="staff")
    ).distinct()
    if not notify_users.exists():
        notify_users = User.objects.filter(is_active=True, is_superuser=True).distinct()

    requester = _make_requester_label(req.user)
    check_in_text = req.requested_check_in_at.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M") if req.requested_check_in_at else "-"
    check_out_text = req.requested_check_out_at.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M") if req.requested_check_out_at else "-"
    content = (
        f"[근태 정정요청] {requester}\n"
        f"대상일: {req.work_date}\n"
        f"요청 출근: {check_in_text} / 요청 퇴근: {check_out_text}\n"
        f"사유: {req.reason}"
    )

    now = timezone.now()
    today = timezone.localdate()
    for ceo in notify_users:
        CalendarMemo.objects.create(
            user=ceo,
            clinic=None,
            date=today,
            content=content,
            platform="",
            remind_at=now,
            is_read=False,
        )


class MyAttendanceMonthView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month_start = _parse_month(request.GET.get("month"))
        if not month_start:
            return Response({"message": "invalid month"}, status=status.HTTP_400_BAD_REQUEST)
        month_end = _next_month(month_start)

        qs = AttendanceRecord.objects.filter(
            user=request.user,
            work_date__gte=month_start,
            work_date__lt=month_end,
        ).order_by("-work_date")
        rows = list(qs)

        total_minutes = sum(r.worked_minutes or 0 for r in rows)
        completed_days = sum(1 for r in rows if r.check_in_at and r.check_out_at)
        worked_days = sum(1 for r in rows if r.check_in_at)
        avg_minutes = int(total_minutes / completed_days) if completed_days else 0

        today = timezone.localdate()
        today_record = AttendanceRecord.objects.filter(user=request.user, work_date=today).first()
        live_minutes = None
        if today_record and today_record.check_in_at and not today_record.check_out_at:
            delta = timezone.now() - today_record.check_in_at
            live_minutes = max(0, int(delta.total_seconds() // 60))

        return Response(
            {
                "month": month_start.strftime("%Y-%m"),
                "summary": {
                    "worked_days": worked_days,
                    "completed_days": completed_days,
                    "total_minutes": total_minutes,
                    "average_minutes": avg_minutes,
                },
                "today": {
                    "date": today.isoformat(),
                    "record": AttendanceRecordSerializer(today_record).data if today_record else None,
                    "live_minutes": live_minutes,
                },
                "results": AttendanceRecordSerializer(rows, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class MyAttendanceCheckInView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        record = _get_or_create_today(request.user)
        if record.check_in_at:
            return Response(
                {"message": "already_checked_in", "record": AttendanceRecordSerializer(record).data},
                status=status.HTTP_200_OK,
            )

        record.check_in_at = timezone.now()
        record.status = "working"
        record.save(update_fields=["check_in_at", "status", "updated_at"])
        return Response({"ok": True, "record": AttendanceRecordSerializer(record).data}, status=status.HTTP_200_OK)


class MyAttendanceCheckOutView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        today = timezone.localdate()
        record = AttendanceRecord.objects.filter(user=request.user, work_date=today).first()
        if not record or not record.check_in_at:
            return Response({"message": "check_in_required"}, status=status.HTTP_400_BAD_REQUEST)
        if record.check_out_at:
            return Response(
                {"message": "already_checked_out", "record": AttendanceRecordSerializer(record).data},
                status=status.HTTP_200_OK,
            )

        record.check_out_at = timezone.now()
        record.status = "completed"
        record.recalculate_minutes()
        record.save(update_fields=["check_out_at", "status", "worked_minutes", "updated_at"])
        return Response({"ok": True, "record": AttendanceRecordSerializer(record).data}, status=status.HTTP_200_OK)


class MyAttendanceCorrectionListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit_raw = request.GET.get("limit") or "20"
        try:
            limit = max(1, min(100, int(limit_raw)))
        except ValueError:
            limit = 20
        qs = AttendanceCorrectionRequest.objects.filter(user=request.user).order_by("-created_at")
        return Response(
            {
                "count": qs.count(),
                "results": AttendanceCorrectionRequestSerializer(qs[:limit], many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        payload = request.data or {}
        work_date_raw = payload.get("work_date")
        work_date = parse_date(work_date_raw or "")
        if not work_date:
            return Response({"message": "work_date_required"}, status=status.HTTP_400_BAD_REQUEST)

        reason = (payload.get("reason") or "").strip()
        if not reason:
            return Response({"message": "reason_required"}, status=status.HTTP_400_BAD_REQUEST)

        req_in = _parse_datetime_value(payload.get("requested_check_in_at"))
        req_out = _parse_datetime_value(payload.get("requested_check_out_at"))
        if req_in and req_out and req_out < req_in:
            return Response({"message": "invalid_time_range"}, status=status.HTTP_400_BAD_REQUEST)

        target = AttendanceRecord.objects.filter(user=request.user, work_date=work_date).first()
        correction = AttendanceCorrectionRequest.objects.create(
            user=request.user,
            record=target,
            work_date=work_date,
            current_check_in_at=target.check_in_at if target else None,
            current_check_out_at=target.check_out_at if target else None,
            requested_check_in_at=req_in,
            requested_check_out_at=req_out,
            reason=reason,
            status="pending",
        )
        _notify_ceo_for_correction(correction)
        return Response(
            {"ok": True, "request": AttendanceCorrectionRequestSerializer(correction).data},
            status=status.HTTP_201_CREATED,
        )
