"""
Django Admin 설정 - presetss.txt 기반 144개 항목 반영
"""
from django.contrib import admin
import re
from urllib.parse import urlsplit, urlunsplit
from .models import (
    AccessLog,
    AuditEvent,
    AttendanceCorrectionRequest,
    AttendanceRecord,
    VacationRequest,
    Campaign,
    CalendarMemo,
    ReviewSchedule,
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

REVIEW_SCHEDULE_PLATFORM = "__review_schedule__"
_REVIEW_NEW_RE = re.compile(r"^\[리뷰설계\/([^\/\]]+)\/([^\]]+)\]\s*([\s\S]*?)(?:\n(?:리뷰|초안):\s*([\s\S]*))?$")
_REVIEW_OLD_RE = re.compile(r"^\[리뷰설계\/([^\]]+)\]\s*([\s\S]*?)(?:\n(?:리뷰|초안):\s*([\s\S]*))?$")


class ReviewScheduleMemo(CalendarMemo):
    class Meta:
        proxy = True
        verbose_name = "리뷰 설계안"
        verbose_name_plural = "리뷰 설계안"


def _split_plan_title(raw_detail):
    detail = str(raw_detail or "").strip()
    plan_title = ""
    kept = []
    for ln in detail.splitlines():
        s = str(ln or "").strip()
        if s.startswith("설계안 제목:"):
            plan_title = s.split(":", 1)[1].strip()
            continue
        kept.append(ln)
    return plan_title, "\n".join(kept).strip()


def _parse_review_content(raw):
    text = (raw or "").strip()
    m_new = _REVIEW_NEW_RE.match(text)
    if m_new:
        plan_title, cleaned_detail = _split_plan_title(m_new.group(3))
        return (
            (m_new.group(1) or "").strip(),
            (m_new.group(2) or "").strip(),
            cleaned_detail,
            (m_new.group(4) or "").strip(),
            plan_title,
        )
    m_old = _REVIEW_OLD_RE.match(text)
    if m_old:
        plan_title, cleaned_detail = _split_plan_title(m_old.group(2))
        return "", (m_old.group(1) or "").strip(), cleaned_detail, (m_old.group(3) or "").strip(), plan_title
    plan_title, cleaned_detail = _split_plan_title(text)
    return "", "", cleaned_detail, "", plan_title


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
    list_display = ["id", "clinic", "type", "platform", "opinion_subtype", "review_subtype", "title", "views", "comments", "message_count", "post_written_at"]
    list_filter = ["type", "platform", "clinic", "status", "opinion_subtype", "review_subtype"]
    search_fields = ["title", "url"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ClinicPostPhotoInline]
    actions = ["fill_crawled_body_from_crawled_content"]

    @admin.display(description="게시글 작성일")
    def post_written_at(self, obj):
        return obj.published_at or obj.created_at

    @admin.action(description="선택 게시글 URL 기준으로 크롤링 본문 채우기")
    def fill_crawled_body_from_crawled_content(self, request, queryset):
        def _normalize_url(raw):
            s = str(raw or "").strip()
            if not s:
                return ""
            try:
                p = urlsplit(s)
                path = (p.path or "").rstrip("/") or "/"
                return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))
            except Exception:
                return s.rstrip("/")

        posts = list(queryset)
        if not posts:
            self.message_user(request, "선택된 게시글이 없습니다.")
            return

        url_map = {}
        for post in posts:
            nurl = _normalize_url(post.url)
            if nurl:
                url_map.setdefault(nurl, []).append(post)

        if not url_map:
            self.message_user(request, "선택 게시글에 유효한 URL이 없습니다.")
            return

        crawled_qs = (
            CrawledPostContent.objects
            .filter(status="success")
            .exclude(content="")
            .order_by("-fetched_at")
        )

        latest_by_url = {}
        for row in crawled_qs:
            nurl = _normalize_url(row.url)
            if not nurl or nurl in latest_by_url:
                continue
            if nurl in url_map:
                latest_by_url[nurl] = row
            if len(latest_by_url) >= len(url_map):
                break

        updated = 0
        missing = 0
        for nurl, post_list in url_map.items():
            row = latest_by_url.get(nurl)
            if not row:
                missing += len(post_list)
                continue
            for post in post_list:
                post.crawled_body = row.content or ""
                post.save(update_fields=["crawled_body"])
                updated += 1

        self.message_user(
            request,
            f"본문 채움 완료: {updated}건, 미매칭: {missing}건",
        )

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


@admin.register(ReviewSchedule)
class ReviewScheduleAdmin(admin.ModelAdmin):
    list_display = ["id", "plan_id", "plan_title", "label", "user", "clinic", "date", "is_read", "created_at"]
    list_filter = ["is_read", "date", "created_at", "user"]
    search_fields = ["plan_id", "plan_title", "label", "detail", "draft", "user__username", "clinic__name", "account"]
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

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["id", "event_type", "actor", "target_type", "target_id", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["event_type", "target_type", "target_id", "actor__username", "actor__profile__name"]
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


# Admin 사이트 설정 (한글 통일)
admin.site.site_header = "Datalab90 관리자"
admin.site.site_title = "Datalab90 관리자"
admin.site.index_title = "운영 관리"


# 어드민 목록 표시를 카테고리 중심으로 정렬/표기
_CATEGORY_ORDER = {
    "시스템": 0,
    "인사/권한": 1,
    "게시글/콘텐츠": 2,
    "병원/가이드": 3,
    "리뷰/AI": 4,
    "커뮤니케이션": 5,
    "기타": 99,
}

_MODEL_CATEGORY = {
    "AuditEvent": "시스템",
    "AccessLog": "시스템",
    "SystemPermission": "인사/권한",
    "AttendanceRecord": "인사/권한",
    "AttendanceCorrectionRequest": "인사/권한",
    "VacationRequest": "인사/권한",
    "ClinicPost": "게시글/콘텐츠",
    "ClinicPostPhoto": "게시글/콘텐츠",
    "CrawledPostContent": "게시글/콘텐츠",
    "CalendarMemo": "게시글/콘텐츠",
    "ReviewScheduleMemo": "게시글/콘텐츠",
    "ReviewSchedule": "게시글/콘텐츠",
    "ContentTypeProfile": "게시글/콘텐츠",
    "PromptTemplate": "게시글/콘텐츠",
    "PromptTemplateVersion": "게시글/콘텐츠",
    "ClinicGuide": "병원/가이드",
    "ClinicDoctor": "병원/가이드",
    "ClinicPrice": "병원/가이드",
    "ClinicAssignee": "병원/가이드",
    "FavoriteClinic": "병원/가이드",
    "Review": "리뷰/AI",
    "GeneratedReview": "리뷰/AI",
    "LLMUsageLog": "리뷰/AI",
    "Campaign": "리뷰/AI",
    "Persona": "리뷰/AI",
    "CafeProfile": "리뷰/AI",
    "ImageAsset": "리뷰/AI",
    "InternalMessage": "커뮤니케이션",
    "InternalMessageAttachment": "커뮤니케이션",
}

_MODEL_KO_NAME = {
    "AuditEvent": "감사 로그",
    "AccessLog": "접속 로그",
    "SystemPermission": "시스템 권한",
    "AttendanceRecord": "출퇴근 기록",
    "AttendanceCorrectionRequest": "출퇴근 정정요청",
    "VacationRequest": "휴가 요청",
    "ClinicPost": "게시글",
    "ClinicPostPhoto": "게시글 사진",
    "CrawledPostContent": "크롤링 본문",
    "CalendarMemo": "캘린더 메모",
    "ReviewScheduleMemo": "스케줄 설계",
    "ReviewSchedule": "스케줄 설계",
    "ContentTypeProfile": "컨텐츠 유형",
    "PromptTemplate": "프롬프트 템플릿",
    "PromptTemplateVersion": "프롬프트 버전",
    "ClinicGuide": "병원 가이드",
    "ClinicDoctor": "의료진",
    "ClinicPrice": "수가표",
    "ClinicAssignee": "병원 담당자",
    "FavoriteClinic": "즐겨찾기 병원",
    "Review": "원본 리뷰",
    "GeneratedReview": "생성 리뷰",
    "LLMUsageLog": "LLM 사용 로그",
    "Campaign": "캠페인",
    "Persona": "페르소나",
    "CafeProfile": "카페 프로필",
    "ImageAsset": "이미지 자산",
    "InternalMessage": "쪽지",
    "InternalMessageAttachment": "쪽지 첨부파일",
}

_original_get_app_list = admin.site.get_app_list


def _custom_get_app_list(request, app_label=None):
    raw_app_list = _original_get_app_list(request, app_label)
    result = []

    for app in raw_app_list:
        if app.get("app_label") != "data":
            result.append(app)
            continue

        grouped = {}
        for model in app.get("models", []):
            object_name = model.get("object_name") or ""
            category = _MODEL_CATEGORY.get(object_name, "기타")
            label = _MODEL_KO_NAME.get(object_name) or model.get("name") or object_name
            cloned = dict(model)
            cloned["name"] = label
            grouped.setdefault(category, []).append(cloned)

        for category, _order in sorted(_CATEGORY_ORDER.items(), key=lambda x: x[1]):
            models = grouped.get(category, [])
            if not models:
                continue
            models.sort(key=lambda m: m.get("name", ""))
            result.append(
                {
                    "name": f"데이터 운영 · {category}",
                    "app_label": app.get("app_label"),
                    "app_url": app.get("app_url"),
                    "has_module_perms": app.get("has_module_perms", True),
                    "models": models,
                }
            )

    return result


admin.site.get_app_list = _custom_get_app_list
