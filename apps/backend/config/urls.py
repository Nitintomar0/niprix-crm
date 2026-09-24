from django.contrib import admin
from django.urls import path
from organizations.views import EmployeeListView, EmployeeDetailView, EmployeeCreateView
from attendance.views import AttendanceListView, AttendanceCorrectionView, CheckInView, CheckOutView, CurrentAttendanceView

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from accounts.views import (
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
        TokenRefreshView.as_view(),
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
    path("api/attendance/check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("api/attendance/check-out/", CheckOutView.as_view(), name="attendance-check-out"),
    path("api/attendance/current/", CurrentAttendanceView.as_view(), name="attendance-current"),
    path("api/attendance/", AttendanceListView.as_view(), name="attendance-list"),
    path("api/attendance/<int:pk>/correct/", AttendanceCorrectionView.as_view(), name="attendance-correct"),
]
