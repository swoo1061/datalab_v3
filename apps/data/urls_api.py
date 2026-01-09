from django.urls import path
from . import views_api

urlpatterns = [
    path("clinics/", views_api.clinic_list_api),
    path("clinics/<int:clinic_id>/doctors/", views_api.clinic_detail_api),
    path("llm/models/", views_api.llm_model_list_api),
]