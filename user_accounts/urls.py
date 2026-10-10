from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from user_accounts.views import LoginView, MeView, RegisterView

app_name = "user_accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
