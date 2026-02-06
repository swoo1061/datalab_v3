from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class VacationRequest(models.Model):
    TYPE_CHOICES = [
        ("annual", "연차"),
        ("half_am", "오전반차"),
        ("half_pm", "오후반차"),
    ]
    STATUS_CHOICES = [
        ("pending", "대기"),
        ("approved", "승인"),
        ("rejected", "반려"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vacation_requests",
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="annual", db_index=True)
    days = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("0.0"))
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_vacation_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "start_date"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} {self.start_date}~{self.end_date} {self.get_type_display()}"

    def recalculate_days(self):
        if self.type in {"half_am", "half_pm"}:
            self.days = Decimal("0.5")
            return
        if not self.start_date or not self.end_date or self.end_date < self.start_date:
            self.days = Decimal("0.0")
            return
        delta = (self.end_date - self.start_date).days + 1
        self.days = Decimal(str(delta))

    def save(self, *args, **kwargs):
        self.recalculate_days()
        super().save(*args, **kwargs)
