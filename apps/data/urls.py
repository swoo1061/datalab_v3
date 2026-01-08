from django.urls import path
from .views_api import clinic_list_api, llm_model_list_api

urlpatterns = [
    path("clinics/", clinic_list_api),
    path("llm/models/", llm_model_list_api),
    
]