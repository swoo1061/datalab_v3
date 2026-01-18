from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.data.models import ClinicGuide  # ✅ 병원 모델(너가 쓰는 ClinicGuide)


class DailyWorkLog(models.Model):
    """
    병원 페이지에서 보는 '데일리 업무 일지'
    - 병원(clinic) 단위
    - 날짜(date) 단위
    - 작성자(user) 단위
    """
    clinic = models.ForeignKey(
        ClinicGuide,
        on_delete=models.CASCADE,
        related_name="worklogs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="worklogs",
    )

    date = models.DateField(default=timezone.localdate)

    # 지표 (노션에 있던 실적 느낌)
    posts_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    reviews_count = models.PositiveIntegerField(default=0)

    # 선택: 메모/업무내용
    memo = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["clinic", "date"]),
            models.Index(fields=["user", "date"]),
        ]
        unique_together = ("clinic", "user", "date")  # ✅ 하루에 병원+유저 1개
        ordering = ["-date", "-updated_at"]

    def __str__(self):
        return f"{self.date} {self.clinic.name} {self.user}"
