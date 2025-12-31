"""
MedViral URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # 외부 공개 영역
    path('', include('apps.core.urls')),        # ✅ 루트는 core

    # 인증
    path('accounts/', include('accounts.urls')),

    # 내부 대시보드 (로그인 필수)
    path('dashboard/', include('apps.dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
