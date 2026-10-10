from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from user_accounts.models import User
from user_accounts.serializers import (
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Registers a new Customer or Provider user and returns JWT authentication tokens.
    """

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Register a new user",
        description="Creates a new customer or provider account. Admin accounts cannot be created here.",
        responses={
            201: OpenApiResponse(
                description="User registered successfully with JWT tokens"
            ),
            400: OpenApiResponse(
                description="Validation error (e.g. duplicate email, invalid role)"
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role

        user_data = UserSerializer(user).data
        return Response(
            {
                "message": "User registered successfully.",
                "user": user_data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    """
    POST /api/auth/login/
    Authenticates user credentials and issues JWT access and refresh tokens.
    """

    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Log in user",
        description="Authenticate with email and password to receive JWT tokens.",
        responses={
            200: OpenApiResponse(description="Login successful"),
            400: OpenApiResponse(
                description="Invalid credentials or deactivated account"
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user_data = UserSerializer(data["user"]).data

        return Response(
            {
                "message": "Login successful.",
                "user": user_data,
                "tokens": {
                    "access": data["access"],
                    "refresh": data["refresh"],
                },
            },
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET /api/auth/me/
    Retrieves the current authenticated user's profile.
    PATCH/PUT /api/auth/me/
    Allows updating profile fields (full_name, username) while strictly preserving role immutability.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Current user profile",
        description="Returns details for the currently authenticated user.",
    )
    def get_object(self):
        return self.request.user
