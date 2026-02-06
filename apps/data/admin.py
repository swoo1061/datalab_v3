"""
Django Admin 설정 - presetss.txt 기반 144개 항목 반영
"""
from django.contrib import admin
from .models import (
    AccessLog,
    AttendanceCorrectionRequest,
    AttendanceRecord,
    VacationRequest,
    Campaign,
    CalendarMemo,
    CafeProfile,
    ClinicAssignee,
    ClinicDoctor,
    ClinicGuide,
    ClinicPost,
    ClinicPostPhoto,
    ClinicPrice,
    ContentTypeProfile,
    CrawledPostContent,
    FavoriteClinic,
    GeneratedReview,
    ImageAsset,
    InternalMessage,
    LLMUsageLog,
    Persona,
    PromptTemplate,
    PromptTemplateVersion,
    Review,
    SystemPermission,
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date']
    search_fields = ['name']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'language', 'sentiment', 'created_at']
    list_filter = ['source', 'language', 'sentiment']
    search_fields = ['original_text', 'summary']
    date_hierarchy = 'created_at'


@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ['id', 'review', 'width', 'height', 'created_at']
    list_filter = ['created_at']


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ['name', 'age_group', 'gender', 'occupation', 'experience_level', 'emoji_usage', 'is_active']
    list_filter = ['age_group', 'gender', 'occupation', 'experience_level', 'is_active']
    search_fields = ['name', 'description', 'intro_expression']
    fieldsets = (
        ('기본 신원', {
            'fields': ('name', 'age_group', 'gender', 'occupation', 'region')
        }),
        ('말투 스타일', {
            'fields': ('honorific_level', 'exclamation_freq', 'emoji_usage', 'sentence_ending', 'sentence_length')
        }),
        ('시술 경험', {
            'fields': ('experience_level', 'fear_level', 'price_sensitivity', 'skin_concerns', 'skin_type')
        }),
        ('표현 라이브러리', {
            'fields': ('intro_expression', 'transition_expression', 'conclusion_expression', 'recommend_expression', 'frequent_expressions'),
            'classes': ('collapse',)
        }),
        ('신뢰 요소', {
            'fields': ('own_money_emphasis', 'cons_mention_style', 'cons_examples', 'comparison_mention', 'choice_reason'),
            'classes': ('collapse',)
        }),
        ('메타', {
            'fields': ('description', 'is_active')
        }),
    )


@admin.register(CafeProfile)
class CafeProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform_type', 'cafe_character', 'length_range', 'photo_required', 'is_active']
    list_filter = ['platform_type', 'cafe_character', 'ad_restriction', 'photo_required', 'is_active']
    search_fields = ['name', 'tips']
    fieldsets = (
        ('플랫폼 정보', {
            'fields': ('platform_type', 'name', 'cafe_character', 'board_type', 'url')
        }),
        ('글 형식', {
            'fields': ('length_range', 'required_elements', 'subtitle_style', 'paragraph_style', 'photo_mention')
        }),
        ('상호작용', {
            'fields': ('question_inducement', 'info_request', 'reply_style'),
            'classes': ('collapse',)
        }),
        ('카페 규칙', {
            'fields': ('ad_restriction', 'hospital_name_disclosure', 'price_disclosure', 'photo_required'),
        }),
        ('SEO/노출', {
            'fields': ('title_prefix', 'hashtag_count', 'required_keywords', 'forbidden_keywords'),
            'classes': ('collapse',)
        }),
        ('대상 설정', {
            'fields': ('target_reader',)
        }),
        ('기타', {
            'fields': ('tips', 'is_active')
        }),
    )


class ClinicDoctorInline(admin.TabularInline):
    model = ClinicDoctor
    extra = 0
    fields = (
        "order",
        "name",
        "code",
        "style",
        "specialties",
        "is_active",
    )
    ordering = ("order",)


class ClinicPriceInline(admin.TabularInline):
    model = ClinicPrice
    extra = 0
    fields = (
        "order",
        "doctor",
        "procedure",
        "price_display",
        "note",
        "is_active",
    )
    ordering = ("order",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        수가 입력 시:
        현재 편집 중인 ClinicGuide에 속한 원장만 보이게
        """
        if db_field.name == "doctor":
            try:
                # URL: /admin/data/clinicguide/{id}/change/
                clinic_id = request.resolver_match.kwargs.get("object_id")
                if clinic_id:
                    kwargs["queryset"] = ClinicDoctor.objects.filter(
                        clinic_id=clinic_id,
                        is_active=True
                    )
            except Exception:
                pass

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ClinicPostPhotoInline(admin.TabularInline):
    model = ClinicPostPhoto
    extra = 0
    fields = ("image", "created_at")
    readonly_fields = ("created_at",)


@admin.register(ClinicPost)
class ClinicPostAdmin(admin.ModelAdmin):
    list_display = ["id", "clinic", "type", "platform", "opinion_subtype", "review_subtype", "title", "views", "comments", "message_count", "updated_at"]
    list_filter = ["type", "platform", "clinic", "status", "opinion_subtype", "review_subtype"]
    search_fields = ["title", "url"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ClinicPostPhotoInline]

@admin.register(ClinicPostPhoto)
class ClinicPostPhotoAdmin(admin.ModelAdmin):
    list_display = ["id", "post", "image", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["post__title"]
    readonly_fields = ["created_at"]


@admin.register(CrawledPostContent)
class CrawledPostContentAdmin(admin.ModelAdmin):
    list_display = ["id", "post", "platform", "status", "views", "comments", "content_length", "fetched_at"]
    list_filter = ["platform", "status", "fetched_at"]
    search_fields = ["title", "content", "url", "post__title"]
    readonly_fields = ["fetched_at", "content_length"]

@admin.register(ClinicGuide)
class ClinicGuideAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'location_short',
        'doctors_count',
        'procedures_count',
        'is_active',
        'updated_at'
    ]

    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'location']
    readonly_fields = ['created_at', 'updated_at']

    inlines = [
        ClinicDoctorInline,
        ClinicPriceInline,
    ]

    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'file_path', 'location', 'hours', 'parking')
        }),
        ('프로세스', {
            'fields': ('process',)
        }),
        ('데이터 (JSON)', {
            'fields': (
                'doctors',
                'consultants',
                'price_list',
                'aftercare',
                'post_care',
                'features',
            ),
            'classes': ('collapse',)
        }),
        ('언급 제한', {
            'fields': ('allowed_hospitals', 'blocked_hospitals'),
            'classes': ('collapse',)
        }),
        ('상태', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )

    # ===== Custom Columns =====
    def location_short(self, obj):
        if not obj.location:
            return "-"
        return obj.location[:30] + "..." if len(obj.location) > 30 else obj.location
    location_short.short_description = "위치"

    def doctors_count(self, obj):
        return obj.doctor_objects.count()
    doctors_count.short_description = "의료진"

    def procedures_count(self, obj):
        return obj.price_objects.count()
    procedures_count.short_description = "시술"

@admin.register(ClinicDoctor)
class ClinicDoctorAdmin(admin.ModelAdmin):
    list_display = ["id", "clinic", "name", "code", "is_active", "order"]
    list_filter = ["clinic", "is_active"]
    search_fields = ["name", "code", "clinic__name"]
    ordering = ["clinic", "order", "id"]

@admin.register(ClinicPrice)
class ClinicPriceAdmin(admin.ModelAdmin):
    list_display = ["id", "clinic", "doctor", "procedure", "price_display", "is_active", "order"]
    list_filter = ["clinic", "is_active"]
    search_fields = ["procedure", "clinic__name", "doctor__name"]
    ordering = ["clinic", "order", "id"]

@admin.register(ContentTypeProfile)
class ContentTypeProfileAdmin(admin.ModelAdmin):
    list_display = ['order', 'label', 'value', 'content_purpose', 'emotion_tone', 'min_length', 'max_length', 'is_active']
    list_display_links = ['label']
    list_filter = ['content_purpose', 'emotion_tone', 'is_active']
    list_editable = ['order']
    search_fields = ['label', 'value', 'description']
    fieldsets = (
        ('기본 정보', {
            'fields': ('order', 'value', 'label', 'description')
        }),
        ('공통 셋팅', {
            'fields': ('content_purpose', 'core_message', 'emotion_tone', 'cta_type')
        }),
        ('글 설정', {
            'fields': ('min_length', 'max_length', 'image_required', 'tone')
        }),
        ('타입별 세부 설정', {
            'fields': ('recommend_settings', 'research_settings', 'consultation_settings',
                      'procedure_day_settings', 'recovery_1month_settings', 'recovery_2month_plus_settings'),
            'classes': ('collapse',)
        }),
        ('구조', {
            'fields': ('structure', 'required_sections'),
            'classes': ('collapse',)
        }),
        ('표현', {
            'fields': ('common_expressions', 'opening_patterns', 'closing_patterns'),
            'classes': ('collapse',)
        }),
        ('가이드', {
            'fields': ('forbidden_elements', 'recommended_elements', 'emotion_flow', 'tips'),
            'classes': ('collapse',)
        }),
        ('상태', {
            'fields': ('is_active',)
        }),
    )


@admin.register(GeneratedReview)
class GeneratedReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'review_kind', 'clinic', 'doctor_code', 'procedure', 'status', 'char_count', 'created_at']
    list_filter = ['status', 'clinic', 'created_at']
    search_fields = ['procedure', 'generated_text', 'doctor_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    fieldsets = (
        ('생성 설정', {
            'fields': ('clinic', 'doctor_code', 'doctor_name', 'procedure', 'persona', 'cafe')
        }),
        ('결과', {
            'fields': ('generated_text', 'status', 'upload_url')
        }),
        ('프롬프트', {
            'fields': ('prompt_used',),
            'classes': ('collapse',)
        }),
        ('메타', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def char_count(self, obj):
        return len(obj.generated_text) if obj.generated_text else 0
    char_count.short_description = '글자수'

    def review_kind(self, obj):
        return '수정본' if obj.status == 'edited' else '생성본'
    review_kind.short_description = '구분'

@admin.register(FavoriteClinic)
class FavoriteClinicAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "clinic", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "user__email", "clinic__name"]

@admin.register(CalendarMemo)
class CalendarMemoAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "clinic", "date", "platform", "is_read", "created_at"]
    list_filter = ["platform", "is_read", "created_at"]
    search_fields = ["content", "user__username", "clinic__name", "account"]
    readonly_fields = ["created_at", "updated_at"]

@admin.register(ClinicAssignee)
class ClinicAssigneeAdmin(admin.ModelAdmin):
    list_display = ["id", "clinic", "user", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["clinic__name", "user__username", "user__email"]

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ["id", "ip_address", "path", "method", "created_at"]
    list_filter = ["method", "created_at"]
    search_fields = ["ip_address", "path", "user_agent", "referer"]
    readonly_fields = ["created_at"]

@admin.register(LLMUsageLog)
class LLMUsageLogAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "model", "total_tokens", "cost_usd", "cost_krw", "created_at"]
    list_filter = ["model", "created_at"]
    search_fields = ["user__username", "user__email", "model"]
    readonly_fields = ["created_at"]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "user_name", "work_date", "status", "check_in_at", "check_out_at", "worked_minutes"]
    list_filter = ["status", "work_date", "created_at"]
    search_fields = ["user__username", "user__email", "user__profile__name", "note"]
    readonly_fields = ["created_at", "updated_at", "worked_minutes"]

    def user_name(self, obj):
        profile = getattr(obj.user, "profile", None)
        return getattr(profile, "name", None) or obj.user.username
    user_name.short_description = "이름"


@admin.register(AttendanceCorrectionRequest)
class AttendanceCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "requester_name",
        "work_date",
        "status",
        "requested_check_in_at",
        "requested_check_out_at",
        "created_at",
    ]
    list_filter = ["status", "work_date", "created_at"]
    search_fields = ["user__username", "user__profile__name", "reason", "review_note"]
    readonly_fields = [
        "user",
        "record",
        "work_date",
        "current_check_in_at",
        "current_check_out_at",
        "requested_check_in_at",
        "requested_check_out_at",
        "reason",
        "created_at",
        "updated_at",
    ]

    def requester_name(self, obj):
        profile = getattr(obj.user, "profile", None)
        return getattr(profile, "name", None) or obj.user.username
    requester_name.short_description = "요청자"


@admin.register(VacationRequest)
class VacationRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "requester_name",
        "start_date",
        "end_date",
        "type",
        "days",
        "status",
        "created_at",
    ]
    list_filter = ["status", "type", "start_date", "created_at"]
    search_fields = ["user__username", "user__profile__name", "reason", "review_note"]
    readonly_fields = ["created_at", "updated_at", "days"]

    def requester_name(self, obj):
        profile = getattr(obj.user, "profile", None)
        return getattr(profile, "name", None) or obj.user.username
    requester_name.short_description = "요청자"


@admin.register(InternalMessage)
class InternalMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "sender_name", "recipient_name", "subject", "is_read", "created_at"]
    list_filter = ["is_read", "created_at"]
    search_fields = ["subject", "content", "sender__username", "sender__profile__name", "recipient__username", "recipient__profile__name"]

    def sender_name(self, obj):
        p = getattr(obj.sender, "profile", None)
        return getattr(p, "name", None) or obj.sender.username
    sender_name.short_description = "보낸사람"

    def recipient_name(self, obj):
        p = getattr(obj.recipient, "profile", None)
        return getattr(p, "name", None) or obj.recipient.username
    recipient_name.short_description = "받는사람"

@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "mode", "name", "is_default", "is_active", "version", "updated_at"]
    list_filter = ["mode", "is_default", "is_active"]
    search_fields = ["name", "content"]
    readonly_fields = ["created_at", "updated_at"]

@admin.register(PromptTemplateVersion)
class PromptTemplateVersionAdmin(admin.ModelAdmin):
    list_display = ["id", "template", "version", "changed_by", "created_at"]
    list_filter = ["template", "created_at"]
    search_fields = ["template__name", "changed_by", "change_note"]
    readonly_fields = ["created_at"]


@admin.register(SystemPermission)
class SystemPermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "key", "is_enabled", "updated_by", "updated_at"]
    list_filter = ["key", "is_enabled", "updated_at"]
    search_fields = ["user__username", "user__profile__name", "updated_by__username"]
    readonly_fields = ["created_at", "updated_at"]


# Admin 사이트 설정
admin.site.site_header = 'MedViral 관리자'
admin.site.site_title = 'MedViral Admin'
admin.site.index_title = '리뷰 생성 시스템 관리'
