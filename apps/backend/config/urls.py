from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from organizations.views import EmployeeCreateView, EmployeeDeactivateView, EmployeeDeleteView, EmployeeDetailView, EmployeeListView
from attendance.views import AttendanceListView, AttendanceCorrectionView, AttendanceSummaryView, CheckInView, CheckOutView, CurrentAttendanceView, EmployeeLiveLocationView, LiveLocationSubmitView
from workspace.views import (
    FollowUpActivityListView, FollowUpCompleteView, FollowUpDetailView, FollowUpListCreateView,
    FollowUpPostponeView, FollowUpReassignView, ReminderPreferenceView, TaskCompleteView,
    TaskDetailView, TaskListCreateView, TaskReassignView, WorkspaceOverdueView, WorkspaceSummaryView,
    WorkspaceUpcomingView,
)
from leads.views import (
    LeadActivityListCreateView, LeadAssignmentListView, LeadAssignView, LeadDetailView,
    LeadListCreateView, LeadMoveToFollowUpView, LeadSourceListView, LeadStatusView, LeadSummaryView, LeadTemperatureView,
)
from integrations.views import (
    FacebookWebhookView, InstagramWebhookView, IntegrationConfigurationDetailView,
    IntegrationConfigurationListCreateView, IntegrationEventListView, WebsiteIntakeView,
    WhatsAppWebhookView,
)
from organizations.views import EmployeeOverviewView, EmployeePerformanceView, EmployeeAttendanceView, EmployeeActivityView, EmployeeLeadsView, EmployeeWorkView
from hrms.views import (
    EmployeeDocumentDetailView, EmployeeDocumentDownloadView, EmployeeDocumentListCreateView, HolidayDetailView, HolidayListCreateView,
    EmployeeDocumentOverviewListView, HRDashboardView, LeaveBalanceDetailView, LeaveBalanceListView, LeaveRequestActionView, LeaveRequestListCreateView, LeaveTypeDetailView, LeaveTypeListView,
)
from inventory.views import InventoryBulkCreateView, InventoryDetailView, InventoryListCreateView, InventorySummaryView
from raw_data.views import (
    RawDataDistributionPreviewView, RawDataDistributionView, RawDataEligibleEmployeesView,
    RawDataPreviewView, RawDataSavePreviewView, RawDataSummaryView, RawLeadDetailView, RawLeadListCreateView,
)

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.views import (
    ActiveEmployeeTokenRefreshView,
    CEODashboardView,
    LogoutView,
    MeView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "api/auth/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/auth/token/refresh/",
        ActiveEmployeeTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path(
        "api/auth/ceo-dashboard/",
        CEODashboardView.as_view(),
        name="ceo_dashboard",
    ),

    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/employees/",
        EmployeeListView.as_view(),
        name="employee-list",
    ),
    path("api/employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("api/employees/<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("api/employees/<int:pk>/deactivate/", EmployeeDeactivateView.as_view(), name="employee-deactivate"),
    path("api/employees/<int:pk>/delete/", EmployeeDeleteView.as_view(), name="employee-delete"),
    path("api/employees/<int:pk>/overview/", EmployeeOverviewView.as_view(), name="employee-overview"),
    path("api/employees/<int:pk>/performance/", EmployeePerformanceView.as_view(), name="employee-performance"),
    path("api/employees/<int:pk>/attendance/", EmployeeAttendanceView.as_view(), name="employee-attendance"),
    path("api/employees/<int:pk>/leads/", EmployeeLeadsView.as_view(), name="employee-leads"),
    path("api/employees/<int:pk>/work/", EmployeeWorkView.as_view(), name="employee-work"),
    path("api/employees/<int:pk>/activity/", EmployeeActivityView.as_view(), name="employee-activity"),
    path("api/attendance/check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("api/attendance/check-out/", CheckOutView.as_view(), name="attendance-check-out"),
    path("api/attendance/live-location/", LiveLocationSubmitView.as_view(), name="live-location-submit"),
    path("api/employees/<int:employee_id>/live-location/", EmployeeLiveLocationView.as_view(), name="employee-live-location"),
    path("api/attendance/current/", CurrentAttendanceView.as_view(), name="attendance-current"),
    path("api/attendance/summary/", AttendanceSummaryView.as_view(), name="attendance-summary"),
    path("api/attendance/", AttendanceListView.as_view(), name="attendance-list"),
    path("api/attendance/<int:pk>/correct/", AttendanceCorrectionView.as_view(), name="attendance-correct"),
    path("api/follow-ups/", FollowUpListCreateView.as_view(), name="follow-up-list"),
    path("api/follow-ups/<int:pk>/", FollowUpDetailView.as_view(), name="follow-up-detail"),
    path("api/follow-ups/<int:pk>/complete/", FollowUpCompleteView.as_view(), name="follow-up-complete"),
    path("api/follow-ups/<int:pk>/postpone/", FollowUpPostponeView.as_view(), name="follow-up-postpone"),
    path("api/follow-ups/<int:pk>/reassign/", FollowUpReassignView.as_view(), name="follow-up-reassign"),
    path("api/follow-ups/<int:pk>/activities/", FollowUpActivityListView.as_view(), name="follow-up-activities"),
    path("api/leads/<int:pk>/move-to-follow-up/", LeadMoveToFollowUpView.as_view(), name="lead-move-to-follow-up"),
    path("api/tasks/", TaskListCreateView.as_view(), name="task-list"),
    path("api/tasks/<int:pk>/", TaskDetailView.as_view(), name="task-detail"),
    path("api/tasks/<int:pk>/complete/", TaskCompleteView.as_view(), name="task-complete"),
    path("api/tasks/<int:pk>/reassign/", TaskReassignView.as_view(), name="task-reassign"),
    path("api/workspace/summary/", WorkspaceSummaryView.as_view(), name="workspace-summary"),
    path("api/workspace/upcoming/", WorkspaceUpcomingView.as_view(), name="workspace-upcoming"),
    path("api/workspace/overdue/", WorkspaceOverdueView.as_view(), name="workspace-overdue"),
    path("api/reminder-preferences/", ReminderPreferenceView.as_view(), name="reminder-preferences"),
    path("api/leads/", LeadListCreateView.as_view(), name="lead-list"),
    path("api/raw-data/", RawLeadListCreateView.as_view(), name="raw-lead-list"),
    path("api/raw-data/summary/", RawDataSummaryView.as_view(), name="raw-data-summary"),
    path("api/raw-data/preview/", RawDataPreviewView.as_view(), name="raw-data-preview"),
    path("api/raw-data/save-preview/", RawDataSavePreviewView.as_view(), name="raw-data-save-preview"),
    path("api/raw-data/eligible-employees/", RawDataEligibleEmployeesView.as_view(), name="raw-data-eligible-employees"),
    path("api/raw-data/distribution-preview/", RawDataDistributionPreviewView.as_view(), name="raw-data-distribution-preview"),
    path("api/raw-data/distribute/", RawDataDistributionView.as_view(), name="raw-data-distribute"),
    path("api/raw-data/<int:pk>/", RawLeadDetailView.as_view(), name="raw-lead-detail"),
    path("api/inventory/", InventoryListCreateView.as_view(), name="inventory-list"),
    path("api/inventory/summary/", InventorySummaryView.as_view(), name="inventory-summary"),
    path("api/inventory/bulk/", InventoryBulkCreateView.as_view(), name="inventory-bulk-create"),
    path("api/inventory/<int:pk>/", InventoryDetailView.as_view(), name="inventory-detail"),
    path("api/leads/summary/", LeadSummaryView.as_view(), name="lead-summary"),
    path("api/leads/<int:pk>/", LeadDetailView.as_view(), name="lead-detail"),
    path("api/leads/<int:pk>/assign/", LeadAssignView.as_view(), name="lead-assign"),
    path("api/leads/<int:pk>/status/", LeadStatusView.as_view(), name="lead-status"),
    path("api/leads/<int:pk>/temperature/", LeadTemperatureView.as_view(), name="lead-temperature"),
    path("api/leads/<int:pk>/activities/", LeadActivityListCreateView.as_view(), name="lead-activities"),
    path("api/leads/<int:pk>/sources/", LeadSourceListView.as_view(), name="lead-sources"),
    path("api/leads/<int:pk>/assignments/", LeadAssignmentListView.as_view(), name="lead-assignments"),
    path("api/integrations/", IntegrationConfigurationListCreateView.as_view(), name="integration-list"),
    path("api/integrations/<int:pk>/", IntegrationConfigurationDetailView.as_view(), name="integration-detail"),
    path("api/integrations/events/", IntegrationEventListView.as_view(), name="integration-events"),
    path("api/integrations/webhooks/whatsapp/", WhatsAppWebhookView.as_view(), name="webhook-whatsapp"),
    path("api/integrations/webhooks/facebook/", FacebookWebhookView.as_view(), name="webhook-facebook"),
    path("api/integrations/webhooks/instagram/", InstagramWebhookView.as_view(), name="webhook-instagram"),
    path("api/integrations/website/", WebsiteIntakeView.as_view(), name="website-intake"),
    path("api/hrms/leave-types/", LeaveTypeListView.as_view(), name="leave-type-list"),
    path("api/hrms/leave-types/<int:pk>/", LeaveTypeDetailView.as_view(), name="leave-type-detail"),
    path("api/hrms/leave-balances/", LeaveBalanceListView.as_view(), name="leave-balance-list"),
    path("api/hrms/leave-balances/<int:pk>/", LeaveBalanceDetailView.as_view(), name="leave-balance-detail"),
    path("api/hrms/dashboard/", HRDashboardView.as_view(), name="hr-dashboard"),
    path("api/hrms/leave-requests/", LeaveRequestListCreateView.as_view(), name="leave-request-list"),
    path("api/hrms/leave-requests/<int:pk>/<str:action>/", LeaveRequestActionView.as_view(), name="leave-request-action"),
    path("api/hrms/holidays/", HolidayListCreateView.as_view(), name="holiday-list"),
    path("api/hrms/holidays/<int:pk>/", HolidayDetailView.as_view(), name="holiday-detail"),
    path("api/hrms/employees/<int:employee_id>/documents/", EmployeeDocumentListCreateView.as_view(), name="employee-document-list"),
    path("api/hrms/documents/", EmployeeDocumentOverviewListView.as_view(), name="employee-document-overview"),
    path("api/hrms/documents/<int:pk>/download/", EmployeeDocumentDownloadView.as_view(), name="employee-document-download"),
    path("api/hrms/documents/<int:pk>/", EmployeeDocumentDetailView.as_view(), name="employee-document-detail"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
