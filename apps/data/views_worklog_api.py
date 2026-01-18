from datetime import datetime, timedelta

from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.data.models import ClinicGuide
from apps.data.models_worklog import DailyWorkLog
from apps.data.serializers_worklog import DailyWorkLogSerializer


def _parse_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


class ClinicDailyWorkLogViewSet(viewsets.ModelViewSet):
    """
    /api/clinics/<clinic_id>/worklogs/
    /api/clinics/<clinic_id>/worklogs/<id>/
    """
    serializer_class = DailyWorkLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        clinic_id = self.kwargs.get("clinic_id")
        clinic = get_object_or_404(ClinicGuide, id=clinic_id)

        qs = DailyWorkLog.objects.filter(clinic=clinic)

        # ✅ date=YYYY-MM-DD (단일 날짜)
        date_str = self.request.query_params.get("date")
        if date_str:
            d = _parse_date(date_str)
            if d:
                return qs.filter(date=d)

        # ✅ start/end (기간 조회)
        start_str = self.request.query_params.get("start")
        end_str = self.request.query_params.get("end")
        if start_str or end_str:
            start = _parse_date(start_str) if start_str else None
            end = _parse_date(end_str) if end_str else None

            if start and end:
                qs = qs.filter(date__range=[start, end])
            elif start and not end:
                qs = qs.filter(date__gte=start)
            elif end and not start:
                qs = qs.filter(date__lte=end)

        return qs

    def perform_create(self, serializer):
        clinic_id = self.kwargs.get("clinic_id")
        clinic = get_object_or_404(ClinicGuide, id=clinic_id)

        # ✅ 작성자는 로그인 유저로 고정
        serializer.save(
            clinic=clinic,
            user=self.request.user,
        )

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request, clinic_id=None):
        """
        /api/clinics/<clinic_id>/worklogs/summary/?date=YYYY-MM-DD

        기본: date 없으면 오늘
        - 오늘 합계/작성자별
        - 최근 7일 추이(합계)
        """
        clinic = get_object_or_404(ClinicGuide, id=clinic_id)

        date_str = request.query_params.get("date")
        target = _parse_date(date_str) if date_str else timezone.localdate()

        today_qs = DailyWorkLog.objects.filter(clinic=clinic, date=target)

        # 오늘 합계
        total = {
            "posts": sum(x.posts_count for x in today_qs),
            "comments": sum(x.comments_count for x in today_qs),
            "reviews": sum(x.reviews_count for x in today_qs),
        }

        # 작성자별
        by_user = []
        for x in today_qs.order_by("-updated_at"):
            by_user.append({
                "user_id": x.user_id,
                "user_name": getattr(x.user, "username", ""),
                "posts": x.posts_count,
                "comments": x.comments_count,
                "reviews": x.reviews_count,
                "memo": x.memo,
                "updated_at": x.updated_at,
            })

        # 최근 7일 합계(병원 기준)
        start = target - timedelta(days=6)
        recent_qs = DailyWorkLog.objects.filter(
            clinic=clinic,
            date__range=[start, target]
        )

        day_map = {}
        cur = start
        while cur <= target:
            day_map[cur.isoformat()] = {"posts": 0, "comments": 0, "reviews": 0}
            cur += timedelta(days=1)

        for x in recent_qs:
            k = x.date.isoformat()
            day_map[k]["posts"] += x.posts_count
            day_map[k]["comments"] += x.comments_count
            day_map[k]["reviews"] += x.reviews_count

        recent = [{"date": k, **v} for k, v in day_map.items()]

        return Response({
            "clinic_id": clinic.id,
            "clinic_name": clinic.name,
            "date": target.isoformat(),
            "total": total,
            "by_user": by_user,
            "recent_7days": recent,
        }, status=status.HTTP_200_OK)