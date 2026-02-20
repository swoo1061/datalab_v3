from django.conf import settings
from django.db import models

class UserProfile(models.Model):
    POSITION_CHOICES = (
        ("manager", "매니저"),
        ("leader", "팀장"),
        ("ceo", "대표이사"),
    )
    PRESENCE_CHOICES = (
        ("online", "접속중"),
        ("away", "자리비움"),
        ("meeting", "미팅중"),
        ("dnd", "방해금지"),
        ("offline", "오프라인"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    name = models.CharField(max_length=50)
    position = models.CharField(
        max_length=20,
        choices=POSITION_CHOICES
    )
    birth_date = models.DateField(null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_image = models.ImageField(upload_to="profile_images/%Y/%m/%d", null=True, blank=True)
    presence_status = models.CharField(max_length=20, choices=PRESENCE_CHOICES, default="offline")
    presence_updated_at = models.DateTimeField(null=True, blank=True)
    work_start_hour = models.PositiveSmallIntegerField(default=9)
    force_password_change = models.BooleanField(default=False)
    is_hospital_account = models.BooleanField(default=False)
    

    is_approved = models.BooleanField(default=False)  # 관리자 승인용
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_position_display()})"


class OwnerAccountTool(UserProfile):
    class Meta:
        proxy = True
        verbose_name = "병원 계정 관리"
        verbose_name_plural = "병원 계정 관리"
