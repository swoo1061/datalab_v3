from django.urls import path
from .views_api import review_generate_api, review_save_edit_api, api_generate_gangnam_review

urlpatterns = [
    path("review/", review_generate_api),
    path("review/edit/", review_save_edit_api),
    path("gangnam_review/", api_generate_gangnam_review),
]
