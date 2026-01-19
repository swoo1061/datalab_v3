from django.urls import path
from . import views_api
from .views_api import FavoriteClinicView, ClinicPostListCreateView, ClinicPostDetailView, ClinicAssigneeListView
from apps.data.views_worklog_api import ClinicDailyWorkLogViewSet 

worklog_list = ClinicDailyWorkLogViewSet.as_view({
    "get": "list",
    "post": "create",
})
worklog_detail = ClinicDailyWorkLogViewSet.as_view({
    "get": "retrieve",
    "patch": "partial_update",
    "delete": "destroy",
})
worklog_summary = ClinicDailyWorkLogViewSet.as_view({
    "get": "summary",
})

urlpatterns = [
    path("clinics/", views_api.clinic_list_api),
    path("clinics/<int:clinic_id>/", views_api.clinic_detail_api),
    path("clinics/<int:clinic_id>/doctors/", views_api.clinic_detail_api),
    path("llm/models/", views_api.llm_model_list_api),
    path("favorites/", FavoriteClinicView.as_view()),
    path("favorites/<int:clinic_id>/", FavoriteClinicView.as_view()),
    path("clinics/<int:clinic_id>/worklogs/", worklog_list),
    path("clinics/<int:clinic_id>/worklogs/summary/", worklog_summary),
    path("clinics/<int:clinic_id>/worklogs/<int:pk>/", worklog_detail),
    path("clinics/<int:clinic_id>/posts/", ClinicPostListCreateView.as_view()),
    path("clinics/<int:clinic_id>/posts/<int:post_id>/", ClinicPostDetailView.as_view()),
    path("clinics/<int:clinic_id>/assignees/", ClinicAssigneeListView.as_view()),
]
