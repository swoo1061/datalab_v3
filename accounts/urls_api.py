from django.urls import path
from .views_api import login_api, me_api, logout_api, api_signup, users_api

urlpatterns = [
    path("login/", login_api),
    path("me/", me_api),
    path("users/", users_api),
    path("logout/", logout_api),
    path("signup/", api_signup),
    
]
