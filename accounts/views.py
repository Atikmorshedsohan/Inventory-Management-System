from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from common.permissions import RolePermission

from .models import User
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .services import PasswordResetError, confirm_password_reset, issue_password_reset


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ["role"]
    search_fields = ["name", "email"]
    permission_classes = [RolePermission]


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
