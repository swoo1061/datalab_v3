from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime

from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.models import AttendanceRecord, AttendanceCorrectionRequest, CalendarMemo
from apps.data.models_vacation import VacationRequest
from apps.data.serializers_attendance import (
    AttendanceRecordSerializer,
    AttendanceCorrectionRequestSerializer,
)
from apps.data.views_api import (
    CsrfExemptSessionAuthentication,
    HeaderSessionAuthentication,
    ATTENDANCE_MEMO_PLATFORM,
)
from apps.data.permissions import get_user_permission
from apps.data.models import SystemPermission
from apps.data.permissions import normalize_user_role


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
    candidates = (
        User.objects
        .filter(is_active=True)
        .select_related("profile")
        .prefetch_related("groups")
        .distinct()
    )
    notify_users = [
        user for user in candidates
        if get_user_permission(user, SystemPermission.KEY_ATTENDANCE_REQUESTS)
    ]
    if not notify_users:
        notify_users = list(User.objects.filter(is_active=True, is_superuser=True).distinct())

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
            platform=ATTENDANCE_MEMO_PLATFORM,
            remind_at=now,
            is_read=False,
        )


def _is_attendance_admin(user) -> bool:
    return normalize_user_role(user) in {"admin", "ceo", "leader"}


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


class AttendanceAdminListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_attendance_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        month_start = _parse_month(request.GET.get("month"))
        if not month_start:
            return Response({"message": "invalid month"}, status=status.HTTP_400_BAD_REQUEST)
        month_end = _next_month(month_start)

        q = (request.GET.get("q") or "").strip().lower()
        status_filter = (request.GET.get("status") or "all").strip().lower()
        if status_filter not in {"all", "working", "completed"}:
            status_filter = "all"

        users = get_user_model().objects.filter(is_active=True).select_related("profile")
        total_user_count = 0
        user_by_id = {}
        for user in users:
            profile = getattr(user, "profile", None)
            name = getattr(profile, "name", None) or user.get_full_name() or user.username
            user_role = normalize_user_role(user)
            if user_role == "admin":
                continue
            total_user_count += 1
            if q:
                hay = f"{name} {user.username} {user_role}".lower()
                if q not in hay:
                    continue
            user_by_id[user.id] = {
                "user_id": user.id,
                "user_name": name,
                "username": user.username,
                "role": user_role,
            }

        qs = AttendanceRecord.objects.filter(
            work_date__gte=month_start,
            work_date__lt=month_end,
            user_id__in=list(user_by_id.keys()),
        ).select_related("user")
        if status_filter != "all":
            qs = qs.filter(status=status_filter)

        rows = []
        total_minutes = 0
        worked_days = 0
        existing_keys = set()
        row_by_key = {}
        for rec in qs.order_by("-work_date", "user__username"):
            user_meta = user_by_id.get(rec.user_id)
            if not user_meta:
                continue
            work_date_key = rec.work_date.isoformat()
            existing_keys.add(f"{rec.user_id}::{work_date_key}")
            payload = {
                "id": rec.id,
                "user_id": rec.user_id,
                "user_name": user_meta["user_name"],
                "username": user_meta["username"],
                "role": user_meta["role"],
                "work_date": rec.work_date.isoformat(),
                "check_in_at": rec.check_in_at,
                "check_out_at": rec.check_out_at,
                "worked_minutes": rec.worked_minutes,
                "status": rec.status,
                "note": rec.note or "",
            }
            rows.append(payload)
            row_by_key[f"{rec.user_id}::{work_date_key}"] = payload
            if rec.check_in_at:
                worked_days += 1
            total_minutes += int(rec.worked_minutes or 0)

        vac_qs = VacationRequest.objects.filter(
            status="approved",
            user_id__in=list(user_by_id.keys()),
            start_date__lt=month_end,
            end_date__gte=month_start,
        ).select_related("user", "user__profile")
        for req in vac_qs:
            user_meta = user_by_id.get(req.user_id)
            if not user_meta:
                continue
            start_date = max(req.start_date, month_start)
            end_date = min(req.end_date, month_end - timedelta(days=1))
            cur = start_date
            while cur <= end_date:
                work_date_key = cur.isoformat()
                key = f"{req.user_id}::{work_date_key}"
                if key in existing_keys:
                    existing_row = row_by_key.get(key)
                    if existing_row and not existing_row.get("vacation_type"):
                        existing_row["vacation_type"] = req.type
                    cur += timedelta(days=1)
                    continue
                rows.append(
                    {
                        "id": None,
                        "user_id": req.user_id,
                        "user_name": user_meta["user_name"],
                        "username": user_meta["username"],
                        "role": user_meta["role"],
                        "work_date": work_date_key,
                        "check_in_at": None,
                        "check_out_at": None,
                        "worked_minutes": 0,
                        "status": f"vacation_{req.type}",
                        "vacation_type": req.type,
                        "note": req.reason or "",
                    }
                )
                existing_keys.add(key)
                cur += timedelta(days=1)

        rows.sort(key=lambda r: (r.get("work_date") or "", r.get("username") or ""), reverse=True)

        return Response(
            {
                "month": month_start.strftime("%Y-%m"),
                "count": len(rows),
                "users_count": total_user_count,
                "users": list(user_by_id.values()),
                "summary": {
                    "worked_days": worked_days,
                    "total_minutes": total_minutes,
                },
                "results": rows,
            },
            status=status.HTTP_200_OK,
        )


class AttendanceCorrectionAdminListView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_attendance_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        month_start = _parse_month(request.GET.get("month"))
        if not month_start:
            return Response({"message": "invalid month"}, status=status.HTTP_400_BAD_REQUEST)
        month_end = _next_month(month_start)

        status_filter = (request.GET.get("status") or "pending").strip().lower()
        if status_filter not in {"all", "pending", "approved", "rejected"}:
            status_filter = "pending"

        q = (request.GET.get("q") or "").strip().lower()

        qs = AttendanceCorrectionRequest.objects.filter(
            work_date__gte=month_start,
            work_date__lt=month_end,
        ).select_related("user", "user__profile", "reviewed_by", "reviewed_by__profile")
        if status_filter != "all":
            qs = qs.filter(status=status_filter)

        rows = []
        for item in qs.order_by("-created_at"):
            profile = getattr(item.user, "profile", None)
            user_name = getattr(profile, "name", None) or item.user.get_full_name() or item.user.username
            user_role = normalize_user_role(item.user)
            if user_role == "admin":
                continue
            if q:
                hay = f"{user_name} {item.user.username} {item.reason or ''}".lower()
                if q not in hay:
                    continue
            rows.append(
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "user_name": user_name,
                    "username": item.user.username,
                    "work_date": item.work_date.isoformat(),
                    "status": item.status,
                    "reason": item.reason,
                    "current_check_in_at": item.current_check_in_at,
                    "current_check_out_at": item.current_check_out_at,
                    "requested_check_in_at": item.requested_check_in_at,
                    "requested_check_out_at": item.requested_check_out_at,
                    "review_note": item.review_note or "",
                    "reviewed_at": item.reviewed_at,
                    "created_at": item.created_at,
                }
            )

        return Response(
            {
                "month": month_start.strftime("%Y-%m"),
                "count": len(rows),
                "results": rows,
            },
            status=status.HTTP_200_OK,
        )


class AttendanceCorrectionAdminDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, correction_id):
        if not _is_attendance_admin(request.user):
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        row = AttendanceCorrectionRequest.objects.filter(id=correction_id).select_related("user").first()
        if not row:
            return Response({"message": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        action = (request.data or {}).get("action")
        review_note = ((request.data or {}).get("review_note") or "").strip()
        if action not in {"approve", "reject"}:
            return Response({"message": "invalid_action"}, status=status.HTTP_400_BAD_REQUEST)

        if action == "reject":
            row.status = "rejected"
            row.review_note = review_note
            row.reviewed_by = request.user
            row.reviewed_at = timezone.now()
            row.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
            return Response({"ok": True, "status": row.status}, status=status.HTTP_200_OK)

        # approve
        record, _ = AttendanceRecord.objects.get_or_create(
            user=row.user,
            work_date=row.work_date,
            defaults={"status": "working"},
        )

        if row.requested_check_in_at:
            record.check_in_at = row.requested_check_in_at
        if row.requested_check_out_at:
            record.check_out_at = row.requested_check_out_at

        if record.check_out_at:
            record.status = "completed"
        elif record.check_in_at:
            record.status = "working"

        record.recalculate_minutes()
        record.save(update_fields=["check_in_at", "check_out_at", "status", "worked_minutes", "updated_at"])

        row.record = record
        row.status = "approved"
        row.review_note = review_note
        row.reviewed_by = request.user
        row.reviewed_at = timezone.now()
        row.save(update_fields=["record", "status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])

        return Response({"ok": True, "status": row.status}, status=status.HTTP_200_OK)
