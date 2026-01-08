"""
대시보드 URL 라우팅
"""
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # 홈
    path("", views.index, name="index"),
    
    # 기존 리뷰 관리
    path("upload/", views.upload_view, name="upload"),
    path("reviews/", views.review_list, name="reviews_list"),
    path("reviews/<int:pk>/", views.review_detail, name="review_detail"),
    path("images/", views.image_browser, name="image_browser"),
    
    # 리뷰 생성 (기존 - 호환용)
    path("generate/", views.review_generate_basic, name="generate_review"),  # Basic으로 기본
    path("generate/legacy/", views.review_generate_legacy, name="generate_review_legacy"),

    # 리뷰 생성 Basic & PRO
    path("generate/basic/", views.review_generate_basic, name="generate_review_basic"),
    path("generate/basic-plus/", views.review_generate_basic_plus, name="generate_review_basic_plus"),
    path("generate/pro/", views.review_generate_v2, name="generate_review_pro"),
    path("generate/v2/", views.review_generate_v2, name="generate_review_v2"),  # 호환용
    
    # 생성된 리뷰 관리
    path("generated/", views.generated_review_list, name="generated_list"),
    path("generated/<int:pk>/", views.generated_review_detail, name="generated_detail"),
    path("api/generated/bulk-delete/", views.api_generated_bulk_delete, name="api_generated_bulk_delete"),
    
    # 병원 가이드 관리
    path("clinics/", views.clinic_list, name="clinic_list"),
    path("clinics/<int:pk>/", views.clinic_detail, name="clinic_detail"),
    path("clinics/import/", views.clinic_import, name="clinic_import"),
    path("api/clinics/<int:pk>/delete/", views.api_clinic_delete, name="api_clinic_delete"),
    path("api/clinics/<int:pk>/toggle/", views.api_clinic_toggle, name="api_clinic_toggle"),
    
    # API 엔드포인트
    path("api/clinic/<int:clinic_id>/doctors/", views.api_clinic_doctors, name="api_clinic_doctors"),
    path("api/clinic/<int:clinic_id>/procedures/<str:doctor_code>/", views.api_clinic_procedures, name="api_clinic_procedures"),
    path("api/generate/", views.api_generate_review, name="api_generate_review"),
    path("api/generate-basic/", views.api_generate_review_basic, name="api_generate_review_basic"),
    path("api/generate-series/", views.api_generate_series, name="api_generate_series"),
    path("api/generate-reply/", views.api_generate_reply, name="api_generate_reply"),
    path("api/generate-with-style/", views.api_generate_with_style, name="api_generate_with_style"),
    path("api/regenerate/", views.api_regenerate_review, name="api_regenerate_review"),
    path("api/generate-prompt/", views.api_generate_prompt, name="api_generate_prompt"),
    path("api/generate-from-prompt/", views.api_generate_review_from_prompt, name="api_generate_review_from_prompt"),
    path("api/import-clinic/", views.api_import_clinic_md, name="api_import_clinic"),
    
    # 프리셋 추출 (스타일 분석)
    path("preset-extractor/", views.style_analyzer, name="preset_extractor"),
    path("style-analyzer/", views.style_analyzer, name="style_analyzer"),  # 호환용
    path("api/analyze-style/", views.api_analyze_style, name="api_analyze_style"),
    path("api/create-persona-from-style/", views.api_create_persona_from_style, name="api_create_persona_from_style"),
    path("api/create-cafe-from-style/", views.api_create_cafe_from_style, name="api_create_cafe_from_style"),
    path("api/create-content-type-from-style/", views.api_create_content_type_from_style, name="api_create_content_type_from_style"),

    # 이미지 OCR
    path("api/extract-text-from-images/", views.api_extract_text_from_images, name="api_extract_text_from_images"),
    path("api/analyze-style-from-images/", views.api_analyze_style_from_images, name="api_analyze_style_from_images"),

    # 페르소나 관리
    path("personas/", views.persona_list, name="persona_list"),
    path("personas/new/", views.persona_edit, name="persona_new"),
    path("personas/<int:pk>/", views.persona_edit, name="persona_edit"),
    path("api/personas/<int:pk>/delete/", views.api_persona_delete, name="api_persona_delete"),
    path("api/personas/<int:pk>/toggle/", views.api_persona_toggle, name="api_persona_toggle"),

    # 카페 프로필 관리
    path("cafes/", views.cafe_list, name="cafe_list"),
    path("cafes/new/", views.cafe_edit, name="cafe_new"),
    path("cafes/<int:pk>/", views.cafe_edit, name="cafe_edit"),
    path("api/cafes/<int:pk>/delete/", views.api_cafe_delete, name="api_cafe_delete"),
    path("api/cafes/<int:pk>/toggle/", views.api_cafe_toggle, name="api_cafe_toggle"),

    # 프리셋 불러오기
    path("api/load-persona-presets/", views.api_load_persona_presets, name="api_load_persona_presets"),
    path("api/load-cafe-presets/", views.api_load_cafe_presets, name="api_load_cafe_presets"),

    # 프리셋 미리보기 및 개별 추가
    path("api/persona-presets/", views.api_get_persona_presets, name="api_get_persona_presets"),
    path("api/cafe-presets/", views.api_get_cafe_presets, name="api_get_cafe_presets"),
    path("api/persona-presets/add/", views.api_add_persona_preset, name="api_add_persona_preset"),
    path("api/cafe-presets/add/", views.api_add_cafe_preset, name="api_add_cafe_preset"),

    # 컨텐츠 타입 관리
    path("content-types/", views.content_type_list, name="content_type_list"),
    path("content-types/new/", views.content_type_edit, name="content_type_new"),
    path("content-types/<int:pk>/", views.content_type_edit, name="content_type_edit"),
    path("api/content-types/<int:pk>/delete/", views.api_content_type_delete, name="api_content_type_delete"),
    path("api/content-types/<int:pk>/toggle/", views.api_content_type_toggle, name="api_content_type_toggle"),
    path("api/content-type-presets/", views.api_get_content_type_presets, name="api_get_content_type_presets"),
    path("api/content-type-presets/add/", views.api_add_content_type_preset, name="api_add_content_type_preset"),
    path("api/load-content-type-presets/", views.api_load_content_type_presets, name="api_load_content_type_presets"),

    # 서버 설정
    path("server-settings/", views.server_settings, name="server_settings"),
    path("api/firewall-status/", views.api_firewall_status, name="api_firewall_status"),
    path("api/access-logs/", views.api_access_logs, name="api_access_logs"),
    path("api/access-logs/clear/", views.api_clear_access_logs, name="api_clear_access_logs"),

    # 프롬프트 템플릿 관리
    path("prompts/", views.prompt_template_list, name="prompt_template_list"),
    path("prompts/new/", views.prompt_template_edit, name="prompt_template_new"),
    path("prompts/<int:pk>/", views.prompt_template_edit, name="prompt_template_edit"),
    path("api/prompt-templates/", views.api_prompt_templates, name="api_prompt_templates"),
    path("api/prompt-templates/<int:pk>/", views.api_prompt_template_detail, name="api_prompt_template_detail"),
    path("api/prompt-templates/<int:pk>/delete/", views.api_prompt_template_delete, name="api_prompt_template_delete"),
    path("api/prompt-templates/<int:pk>/set-default/", views.api_prompt_template_set_default, name="api_prompt_template_set_default"),
    path("api/prompt-templates/<int:pk>/toggle/", views.api_prompt_template_toggle, name="api_prompt_template_toggle"),
    path("api/prompt-templates/<int:pk>/versions/", views.api_prompt_template_versions, name="api_prompt_template_versions"),
    path("api/prompt-templates/<int:pk>/restore/<int:version>/", views.api_prompt_template_restore, name="api_prompt_template_restore"),
]
