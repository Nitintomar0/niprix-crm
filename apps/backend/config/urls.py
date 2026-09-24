from django.contrib import admin
from django.urls import path
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
]