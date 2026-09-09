from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    # Login goes through the audited view so sign-ins land in the activity log.
    path("auth/token/", views.AuditedTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.current_user, name="current_user"),
    path("access/matrix/", views.PermissionMatrixView.as_view(), name="permission_matrix"),
    path("auth/password-reset/", views.PasswordResetRequestView.as_view(), name="password_reset_request"),
    path(
        "auth/password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
