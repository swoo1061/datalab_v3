from django.urls import path
from .views_api import (
    login_api,
    me_api,
    me_presence_api,
    me_profile_image_api,
    me_password_change_api,
    logout_api,
    api_signup,
    users_api,
)

urlpatterns = [
    path("login/", login_api),
    path("me/", me_api),
    path("me/presence/", me_presence_api),
    path("me/profile-image/", me_profile_image_api),
    path("me/password/", me_password_change_api),
    path("users/", users_api),
    path("logout/", logout_api),
    path("signup/", api_signup),
    
]
