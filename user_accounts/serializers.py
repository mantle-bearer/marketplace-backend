from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from user_accounts.models import Role, User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom SimpleJWT token serializer injecting user claims."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["full_name"] = user.full_name or ""
        return token


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={"input_type": "password"},
    )
    role = serializers.ChoiceField(
        choices=[Role.CUSTOMER, Role.PROVIDER],
        default=Role.CUSTOMER,
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "password",
            "full_name",
            "username",
            "role",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate_role(self, value):
        if value == Role.ADMIN:
            raise serializers.ValidationError(
                "Admin accounts cannot be registered via this endpoint."
            )
        if value not in [Role.CUSTOMER, Role.PROVIDER]:
            raise serializers.ValidationError(
                "Invalid role. Must be 'customer' or 'provider'."
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")

        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role

        return {
            "user": user,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details, with read-only role to prevent self-modification."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "username",
            "role",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "email",
            "role",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
        )
