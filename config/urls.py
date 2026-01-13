"""
MedViral URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # ⭐ API는 최상단에서 먼저 처리 (중요)
    path("api/accounts/", include("accounts.urls_api")),
    path("api/", include("apps.ml.urls_api")),
    path("api/", include("apps.data.urls")),

    # 인증
    path('accounts/', include('accounts.urls')),

    # 내부 대시보드
    path('dashboard/', include('apps.dashboard.urls')),

    # 외부 공개 영역 (맨 마지막!)
    path('', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
