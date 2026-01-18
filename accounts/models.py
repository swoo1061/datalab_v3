from django.conf import settings
from django.db import models

class UserProfile(models.Model):
    POSITION_CHOICES = (
        ("manager", "매니저"),
        ("leader", "팀장"),
        ("ceo", "대표이사"),
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
    phone = models.CharField(max_length=20, blank=True)
    

    is_approved = models.BooleanField(default=False)  # 관리자 승인용
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_position_display()})"
    
