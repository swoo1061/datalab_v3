from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),  # 추가된 회원가입 경로 
    path('report/', views.doctor_report_view, name='doctor_report'),
]
