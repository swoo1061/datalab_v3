from django.conf import settings
from django.db import models
from django.utils import timezone


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("working", "근무중"),
        ("completed", "퇴근"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    work_date = models.DateField(default=timezone.localdate, db_index=True)
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    worked_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="working", db_index=True)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-work_date", "-updated_at"]
        unique_together = ("user", "work_date")
        indexes = [
            models.Index(fields=["user", "work_date"]),
            models.Index(fields=["work_date", "status"]),
        ]

    def __str__(self):
        return f"{self.user} {self.work_date} {self.get_status_display()}"

    def recalculate_minutes(self):
        if self.check_in_at and self.check_out_at and self.check_out_at >= self.check_in_at:
            delta = self.check_out_at - self.check_in_at
            self.worked_minutes = int(delta.total_seconds() // 60)
        else:
            self.worked_minutes = 0


class AttendanceCorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "대기"),
        ("approved", "승인"),
        ("rejected", "반려"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_correction_requests",
    )
    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="correction_requests",
    )
    work_date = models.DateField(db_index=True)
    current_check_in_at = models.DateTimeField(null=True, blank=True)
    current_check_out_at = models.DateTimeField(null=True, blank=True)
    requested_check_in_at = models.DateTimeField(null=True, blank=True)
    requested_check_out_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_attendance_corrections",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "work_date"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} {self.work_date} 정정요청({self.get_status_display()})"
