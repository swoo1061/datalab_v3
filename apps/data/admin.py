"""
Django Admin 설정 - presetss.txt 기반 144개 항목 반영
"""
from django.contrib import admin
from .models import (
    Campaign, Review, ImageAsset,
    Persona, CafeProfile, ClinicGuide, GeneratedReview, ContentTypeProfile,
    ProcedureInfo, MultiSeriesBatch, MultiSeriesItem,
    PromptOptimizationSession, OptimizationRound, OptimizationSample, OptimizationLog
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


@admin.register(ClinicGuide)
class ClinicGuideAdmin(admin.ModelAdmin):
    list_display = ['name', 'location_short', 'doctors_count', 'procedures_count', 'is_active', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'location']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'file_path', 'location', 'hours', 'parking')
        }),
        ('프로세스', {
            'fields': ('process',)
        }),
        ('데이터 (JSON)', {
            'fields': ('doctors', 'consultants', 'price_list', 'aftercare', 'post_care', 'features'),
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

    def location_short(self, obj):
        return obj.location[:30] + '...' if len(obj.location) > 30 else obj.location
    location_short.short_description = '위치'

    def doctors_count(self, obj):
        return len(obj.doctors) if obj.doctors else 0
    doctors_count.short_description = '의료진'

    def procedures_count(self, obj):
        return len(obj.price_list) if obj.price_list else 0
    procedures_count.short_description = '시술'


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
    list_display = ['id', 'clinic', 'doctor_code', 'procedure', 'status', 'char_count', 'created_at']
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


@admin.register(ProcedureInfo)
class ProcedureInfoAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'pain_level', 'price_range', 'is_active', 'updated_at']
    list_filter = ['category', 'pain_level', 'is_active']
    search_fields = ['name', 'description']
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'category', 'description')
        }),
        ('시술 상세', {
            'fields': ('pain_level', 'recovery_time', 'typical_results', 'duration', 'anesthesia_type', 'sessions_recommended')
        }),
        ('가격 & 부작용', {
            'fields': ('price_range', 'common_side_effects', 'precautions'),
            'classes': ('collapse',)
        }),
        ('체험 지식 DB', {
            'fields': ('knowledge_base',),
            'classes': ('collapse',)
        }),
        ('상태', {
            'fields': ('is_active',)
        }),
    )


@admin.register(MultiSeriesBatch)
class MultiSeriesBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'procedure', 'target_count', 'completed_count', 'status', 'total_cost_usd', 'created_at']
    list_filter = ['status', 'model_used', 'created_at']
    search_fields = ['name', 'user_input']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MultiSeriesItem)
class MultiSeriesItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'batch', 'series_index', 'naturalness_score', 'status', 'cost_usd', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at']


# =====================================================
# 프롬프트 최적화 관리
# =====================================================

@admin.register(PromptOptimizationSession)
class PromptOptimizationSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'procedure', 'status', 'current_round', 'target_rounds', 'mode', 'total_cost_usd', 'created_at']
    list_filter = ['status', 'mode', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'current_round', 'total_input_tokens', 'total_output_tokens', 'total_cost_usd']
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'description', 'base_prompt_template', 'procedure', 'user_input')
        }),
        ('설정', {
            'fields': ('samples_per_round', 'target_rounds', 'mode', 'auto_approve_threshold', 'model_used', 'analysis_model')
        }),
        ('분석 옵션', {
            'fields': ('analyze_ai_detection', 'analyze_naturalness', 'analyze_diversity', 'analyze_accuracy')
        }),
        ('상태 & 통계', {
            'fields': ('status', 'current_round', 'total_input_tokens', 'total_output_tokens', 'total_cost_usd')
        }),
        ('메타', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(OptimizationRound)
class OptimizationRoundAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'round_number', 'status', 'score_overall', 'generated_count', 'cost_usd', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['session__name', 'prompt_changes']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OptimizationSample)
class OptimizationSampleAdmin(admin.ModelAdmin):
    list_display = ['id', 'round', 'sample_index', 'content_preview', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['created_at']

    def content_preview(self, obj):
        return obj.generated_content[:100] + '...' if len(obj.generated_content) > 100 else obj.generated_content
    content_preview.short_description = '내용 미리보기'


@admin.register(OptimizationLog)
class OptimizationLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'round', 'log_type', 'message_preview', 'created_at']
    list_filter = ['log_type', 'created_at']
    search_fields = ['message']
    readonly_fields = ['created_at']

    def message_preview(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    message_preview.short_description = '메시지'


# Admin 사이트 설정
admin.site.site_header = 'MedViral 관리자'
admin.site.site_title = 'MedViral Admin'
admin.site.index_title = '리뷰 생성 시스템 관리'
