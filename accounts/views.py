from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.models import AuditLog
from audit.serializers import AuditLogSerializer
from common.permissions import (
    AdminOnlyPermission,
    AdminWritePermission,
    RolePermission,
)

from . import services
from .access_matrix import build_matrix
from .filters import LoginEventFilter
from .models import LoginEvent, User
from .serializers import (
    LoginEventSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .services import PasswordResetError, confirm_password_reset, issue_password_reset

_ACTIVITY_VIEWERS = ("admin", "manager")
DEFAULT_ACTIVITY_LIMIT = 20


class UserViewSet(viewsets.ModelViewSet):
    """User directory. Anyone signed in can read it; only admins can change it."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ["role", "is_active"]
    search_fields = ["name", "email", "department"]
    ordering_fields = ["name", "email", "role", "created_at"]
    permission_classes = [RolePermission, AdminWritePermission]

    @action(detail=False, methods=["get"])
    def roles(self, request):
        """The role vocabulary, for populating a picker."""
        return Response(
            [{"value": key, "label": label} for key, label in User.ROLE_CHOICES]
        )

    @action(detail=True, methods=["post"])
    def set_role(self, request, pk=None):
        """Change a user's role (admin only, audited)."""
        user = services.change_user_role(
            target=self.get_object(),
            actor=request.user,
            new_role=request.data.get("role", ""),
        )
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        """Recent audit-trail entries for one user.

        Everyone can see their own; admins and managers can see anyone's.
        """
        target = self.get_object()
        role = getattr(request.user, "role", "viewer")
        if target.pk != request.user.pk and role not in _ACTIVITY_VIEWERS:
            return Response(
                {"detail": "You can only view your own activity."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            limit = int(request.query_params.get("limit", DEFAULT_ACTIVITY_LIMIT))
        except (TypeError, ValueError):
            limit = DEFAULT_ACTIVITY_LIMIT
        limit = max(1, min(limit, 200))

        logs = AuditLog.objects.filter(user=target).select_related("user")
        return Response(
            {
                "user_id": target.pk,
                "user_name": target.name,
                "total": logs.count(),
                "results": AuditLogSerializer(
                    logs.order_by("-timestamp", "-log_id")[:limit], many=True
                ).data,
            }
        )


class PermissionMatrixView(APIView):
    """Read-only view of what each role can do, computed from the live code."""

    permission_classes = [AdminOnlyPermission]

    def get(self, request):
        return Response(build_matrix())


class AuditedTokenObtainPairView(TokenObtainPairView):
    """Standard JWT login, plus a record of who signed in from where."""

    def post(self, request, *args, **kwargs):
        email = str(request.data.get("email") or "").strip()
        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed as exc:
            services.record_login_event(
                request,
                email=email,
                event="failed",
                successful=False,
                user=User.objects.filter(email__iexact=email).first(),
                reason=str(getattr(exc, "detail", exc)),
            )
            raise

        services.record_login_event(
            request,
            email=email,
            event="login",
            successful=True,
            user=User.objects.filter(email__iexact=email).first(),
        )
        return response


class LogoutView(APIView):
    """JWT is stateless, so this only records the sign-out for the activity log."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        services.record_login_event(
            request, email=request.user.email, event="logout", user=request.user
        )
        return Response({"detail": "Signed out."}, status=status.HTTP_200_OK)


class LoginEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Sign-in activity. Admins only - it exposes other people's addresses."""

    queryset = LoginEvent.objects.select_related("user").all()
    serializer_class = LoginEventSerializer
    permission_classes = [AdminOnlyPermission]
    filterset_class = LoginEventFilter
    search_fields = ["email", "ip_address", "client", "user__name"]
    ordering_fields = ["timestamp", "event_id"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Headline numbers plus each user's most recent sign-in."""
        window_days = 7
        since = timezone.now() - timedelta(days=window_days)
        events = self.filter_queryset(self.get_queryset())
        recent = events.filter(timestamp__gte=since)

        per_user = (
            events.filter(event="login", successful=True, user__isnull=False)
            .values("user__user_id", "user__name", "user__email", "user__role")
            .annotate(logins=Count("event_id"))
            .order_by("-logins")
        )
        last_seen = []
        for row in per_user:
            latest = (
                events.filter(user__user_id=row["user__user_id"], event="login", successful=True)
                .order_by("-timestamp", "-event_id")
                .first()
            )
            last_seen.append(
                {
                    "user_id": row["user__user_id"],
                    "name": row["user__name"],
                    "email": row["user__email"],
                    "role": row["user__role"],
                    "logins": row["logins"],
                    "last_login": latest.timestamp if latest else None,
                    "last_ip": latest.ip_address if latest else None,
                    "last_client": latest.client if latest else None,
                }
            )

        return Response(
            {
                "window_days": window_days,
                "total_events": events.count(),
                "successful_logins": events.filter(event="login", successful=True).count(),
                "failed_logins": events.filter(successful=False).count(),
                "failed_recent": recent.filter(successful=False).count(),
                "logins_recent": recent.filter(event="login", successful=True).count(),
                "distinct_ips": events.exclude(ip_address__isnull=True)
                .values("ip_address").distinct().count(),
                "users": last_seen,
            }
        )


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "user_id": user.user_id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "message": "Registration successful",
            },
            status=status.HTTP_201_CREATED,
        )


class PasswordResetRequestView(generics.GenericAPIView):
    """Request a password reset - emails a tokenised link."""

    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def build_url(token):
            return f"{request.scheme}://{request.get_host()}/reset-password/?token={token}"

        issue_password_reset(
            email=serializer.validated_data["email"], reset_url_builder=build_url
        )
        return Response(
            {"message": "Password reset link has been sent to your email. Please check your inbox."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    """Confirm a password reset with a token."""

    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            confirm_password_reset(
                token=serializer.validated_data["token"],
                new_password=serializer.validated_data["new_password"],
            )
        except PasswordResetError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": "Password has been reset successfully. You can now login with your new password."},
            status=status.HTTP_200_OK,
        )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def current_user(request):
    if request.method == "GET":
        return Response(UserSerializer(request.user).data)

    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
