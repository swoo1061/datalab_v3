"""
MedViral URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔒 API 영역 – prefix 분리 (중요)
    path("api/data/", include("apps.data.urls")),       
    path("api/data/", include("apps.data.urls_api")),     
    path("api/ml/", include("apps.ml.urls_api")),
    path("api/accounts/", include("accounts.urls_api")),

    # 인증
    path('accounts/', include('accounts.urls')),

    # 내부 대시보드
    path('dashboard/', include('apps.dashboard.urls')),

    # 외부 공개 영역
    path('', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
