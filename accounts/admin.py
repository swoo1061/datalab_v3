from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.shortcuts import render
from django.urls import path
from django.utils.crypto import get_random_string

from apps.data.models import ClinicAssignee, ClinicGuide, SystemPermission
from .models import OwnerAccountTool, UserProfile


class OwnerAccountCreateForm(forms.Form):
    clinic = forms.ModelChoiceField(
        queryset=ClinicGuide.objects.filter(is_active=True).order_by("name"),
        label="병원",
    )
    username = forms.CharField(label="아이디", max_length=150)
    temp_password = forms.CharField(
        label="임시 비밀번호",
        max_length=128,
        widget=forms.PasswordInput(render_value=True),
        help_text="첫 로그인 시 변경이 강제됩니다.",
    )
    display_name = forms.CharField(label="표시 이름", max_length=50, required=False)
    force_password_change = forms.BooleanField(
        label="첫 로그인 비밀번호 변경 강제",
        required=False,
        initial=True,
    )

    def clean_username(self):
        username = str(self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("아이디를 입력하세요.")
        if get_user_model().objects.filter(username=username).exists():
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")
        return username

    def clean_temp_password(self):
        value = str(self.cleaned_data.get("temp_password") or "")
        if not value:
            raise forms.ValidationError("임시 비밀번호를 입력해 주세요.")
        return value

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "position", "is_approved", "force_password_change", "created_at")
    list_filter = ("position", "is_approved", "force_password_change")
    search_fields = ("user__username", "name")

    actions = ["approve_users"]

    def approve_users(self, request, queryset):
        for profile in queryset:
            profile.is_approved = True
            profile.save()

            profile.user.is_active = True
            profile.user.save()

        self.message_user(request, "선택한 사용자를 승인했습니다.")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_hospital_account=False)


@admin.register(OwnerAccountTool)
class OwnerAccountToolAdmin(admin.ModelAdmin):
    change_list_template = "admin/accounts/owneraccounttool/change_list.html"
    list_display = ("user", "name", "clinic_name", "is_approved", "force_password_change", "created_at")
    list_filter = ("is_approved", "force_password_change")
    search_fields = ("user__username", "name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return OwnerAccountTool.objects.select_related("user").prefetch_related("user__clinic_assignments__clinic").filter(is_hospital_account=True)

    @admin.display(description="병원")
    def clinic_name(self, obj):
        assignment = obj.user.clinic_assignments.filter(is_active=True).select_related("clinic").first()
        if assignment and assignment.clinic:
            return assignment.clinic.name
        return "-"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "create/",
                self.admin_site.admin_view(self.create_owner_account_view),
                name="accounts_owneraccounttool_create",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        context = {"create_url": "/admin/accounts/owneraccounttool/create/"}
        if extra_context:
            context.update(extra_context)
        return super().changelist_view(request, extra_context=context)

    def create_owner_account_view(self, request):
        initial = {"temp_password": get_random_string(12)}
        form = OwnerAccountCreateForm(initial=initial)
        created_message = ""

        if request.method == "POST":
            form = OwnerAccountCreateForm(request.POST)
            if form.is_valid():
                clinic = form.cleaned_data["clinic"]
                username = form.cleaned_data["username"]
                temp_password = form.cleaned_data["temp_password"]
                display_name = str(form.cleaned_data.get("display_name") or "").strip() or clinic.name
                force_password_change = bool(form.cleaned_data.get("force_password_change"))

                UserModel = get_user_model()
                user = UserModel.objects.create_user(
                    username=username,
                    password=temp_password,
                    is_active=True,
                )
                UserProfile.objects.create(
                    user=user,
                    name=display_name,
                    position="manager",
                    is_approved=True,
                    force_password_change=force_password_change,
                    is_hospital_account=True,
                )
                ClinicAssignee.objects.update_or_create(
                    clinic=clinic,
                    user=user,
                    defaults={"is_active": True},
                )
                SystemPermission.objects.update_or_create(
                    user=user,
                    key=SystemPermission.KEY_WEB_DASHBOARD,
                    defaults={"is_enabled": False, "updated_by": request.user},
                )

                self.message_user(
                    request,
                    f"원장 계정 생성 완료: {clinic.name} / {username} (강제변경: {'ON' if force_password_change else 'OFF'})",
                )
                created_message = f"생성 완료: {clinic.name} / {username}"
                form = OwnerAccountCreateForm(initial={"temp_password": get_random_string(12), "force_password_change": True})

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "병원 원장 계정 생성",
            "form": form,
            "created_message": created_message,
        }
        return render(request, "admin/accounts/owneraccounttool/create.html", context)

admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_active", "is_staff")
    readonly_fields = ("last_login", "date_joined")

    def has_add_permission(self, request):
        return False  # ❌ admin에서 User 직접 생성 금지
