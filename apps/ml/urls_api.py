from django.urls import path
from .views_api import review_generate_api

urlpatterns = [
    path("review/", review_generate_api),
]