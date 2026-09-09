from rest_framework import serializers

from .models import LoginEvent, User


class LoginEventSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True, default=None)
    user_role = serializers.CharField(source="user.role", read_only=True, default=None)
    event_display = serializers.CharField(source="get_event_display", read_only=True)

    class Meta:
        model = LoginEvent
        fields = [
            "event_id", "user", "user_name", "user_role", "email",
            "event", "event_display", "successful", "ip_address", "client",
            "user_agent", "reason", "timestamp",
        ]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id", "name", "email", "phone_number", "department",
            "role", "role_display", "is_active", "created_at",
        ]
        # ``role`` stays read-only here on purpose: it only changes through the
        # audited, admin-only ``/users/{id}/set_role/`` action.
        read_only_fields = ["user_id", "created_at", "role", "role_display", "is_active"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["name", "email", "password", "password_confirm", "role"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(
            email=validated_data["email"],
            name=validated_data["name"],
            password=validated_data["password"],
            role=validated_data.get("role", "viewer"),
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs
