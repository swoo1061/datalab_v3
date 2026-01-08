from django.contrib import admin
from .models import UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "position", "is_approved", "created_at")
    list_filter = ("position", "is_approved")
    search_fields = ("user__username", "name")

    actions = ["approve_users"]

    def approve_users(self, request, queryset):
        for profile in queryset:
            profile.is_approved = True
            profile.save()

            profile.user.is_active = True
            profile.user.save()

        self.message_user(request, "선택한 사용자를 승인했습니다.")

admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_active", "is_staff")
    readonly_fields = ("last_login", "date_joined")

    def has_add_permission(self, request):
        return False  # ❌ admin에서 User 직접 생성 금지