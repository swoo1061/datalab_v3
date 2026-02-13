from django.urls import path
from . import views_api
from .views_api import (
    FavoriteClinicView,
    ClinicPostListCreateView,
    ClinicPostDetailView,
    ClinicAssigneeListView,
    CalendarMemoListCreateView,
    CalendarMemoDetailView,
    ReviewScheduleListView,
    ReviewScheduleGenerateView,
    ReviewScheduleDetailView,
    NotificationListView,
)
from apps.data.views_worklog_api import ClinicDailyWorkLogViewSet 
from apps.data.views_attendance_api import (
    MyAttendanceMonthView,
    MyAttendanceCheckInView,
    MyAttendanceCheckOutView,
    MyAttendanceCorrectionListCreateView,
    AttendanceAdminListView,
    AttendanceCorrectionAdminListView,
    AttendanceCorrectionAdminDetailView,
)
from apps.data.views_vacation_api import (
    MyVacationListCreateView,
    VacationAdminListView,
    VacationAdminDetailView,
    VacationAdminSummaryView,
)
from apps.data.views_message_api import (
    InternalMessageListCreateView,
    InternalMessageDetailView,
)
from apps.data.views_permissions_api import (
    SystemPermissionMeView,
    SystemPermissionUserListView,
    SystemPermissionUserDetailView,
)
from apps.data.views_monitor_api import (
    SystemMonitorLLMStatusView,
)
from apps.data.views_audit_api import (
    AuditEventListView,
)

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
    path("my-clinics/", views_api.my_clinic_ids_api),
    path("favorites/", FavoriteClinicView.as_view()),
    path("favorites/<int:clinic_id>/", FavoriteClinicView.as_view()),
    path("clinics/<int:clinic_id>/worklogs/", worklog_list),
    path("clinics/<int:clinic_id>/worklogs/summary/", worklog_summary),
    path("clinics/<int:clinic_id>/worklogs/<int:pk>/", worklog_detail),
    path("clinics/<int:clinic_id>/posts/", ClinicPostListCreateView.as_view()),
    path("clinics/<int:clinic_id>/posts/<int:post_id>/", ClinicPostDetailView.as_view()),
    path("clinics/<int:clinic_id>/assignees/", ClinicAssigneeListView.as_view()),
    path("calendar-memos/", CalendarMemoListCreateView.as_view()),
    path("calendar-memos/<int:memo_id>/", CalendarMemoDetailView.as_view()),
    path("review-schedules/", ReviewScheduleListView.as_view()),
    path("review-schedules/generate/", ReviewScheduleGenerateView.as_view()),
    path("review-schedules/<int:schedule_id>/", ReviewScheduleDetailView.as_view()),
    path("notifications/", NotificationListView.as_view()),
    path("attendance/me/", MyAttendanceMonthView.as_view()),
    path("attendance/admin/records/", AttendanceAdminListView.as_view()),
    path("attendance/admin/corrections/", AttendanceCorrectionAdminListView.as_view()),
    path("attendance/admin/corrections/<int:correction_id>/", AttendanceCorrectionAdminDetailView.as_view()),
    path("attendance/me/check-in/", MyAttendanceCheckInView.as_view()),
    path("attendance/me/check-out/", MyAttendanceCheckOutView.as_view()),
    path("attendance/me/corrections/", MyAttendanceCorrectionListCreateView.as_view()),
    path("vacations/me/", MyVacationListCreateView.as_view()),
    path("vacations/admin/", VacationAdminListView.as_view()),
    path("vacations/admin/<int:request_id>/", VacationAdminDetailView.as_view()),
    path("vacations/admin/summary/", VacationAdminSummaryView.as_view()),
    path("system-permissions/me/", SystemPermissionMeView.as_view()),
    path("system-permissions/users/", SystemPermissionUserListView.as_view()),
    path("system-permissions/users/<int:user_id>/", SystemPermissionUserDetailView.as_view()),
    path("system-monitor/llm-status/", SystemMonitorLLMStatusView.as_view()),
    path("audit-events/", AuditEventListView.as_view()),
    path("messages/", InternalMessageListCreateView.as_view()),
    path("messages/<int:message_id>/", InternalMessageDetailView.as_view()),
]
