from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from user_accounts.models import Role, User


class UserAuthenticationTests(APITestCase):
    client: APIClient

    def setUp(self):
        self.register_url = reverse("user_accounts:register")
        self.login_url = reverse("user_accounts:login")
        self.me_url = reverse("user_accounts:me")

    def test_customer_registration_success(self):
        """Test customer registration succeeds and issues JWT tokens."""
        payload = {
            "email": "customer1@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test Customer",
            "role": Role.CUSTOMER,
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], "customer1@example.com")
        self.assertEqual(response.data["user"]["role"], Role.CUSTOMER)

    def test_provider_registration_success(self):
        """Test provider registration succeeds."""
        payload = {
            "email": "provider1@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test Provider",
            "role": Role.PROVIDER,
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], Role.PROVIDER)

    def test_admin_registration_rejected(self):
        """Test user cannot self-assign Admin role during registration."""
        payload = {
            "email": "fakeadmin@example.com",
            "password": "SecurePassword123!",
            "role": Role.ADMIN,
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="fakeadmin@example.com").exists())

    def test_duplicate_email_registration_rejected(self):
        """Test duplicate email registration fails with validation error."""
        User.objects.create_user(
            email="existing@example.com",
            password="SecurePassword123!",
            role=Role.CUSTOMER,
        )
        payload = {
            "email": "EXISTING@example.com",  # Case-insensitive check
            "password": "NewPassword123!",
            "role": Role.CUSTOMER,
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_successful(self):
        """Test login returns JWT tokens."""
        user = User.objects.create_user(
            email="loginuser@example.com",
            password="ValidPassword123!",
            role=Role.CUSTOMER,
        )
        payload = {
            "email": "loginuser@example.com",
            "password": "ValidPassword123!",
        }
        response = self.client.post(self.login_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)
        self.assertEqual(response.data["user"]["id"], str(user.id))

    def test_login_invalid_credentials(self):
        """Test login fails with incorrect password."""
        User.objects.create_user(
            email="loginfail@example.com",
            password="ValidPassword123!",
        )
        payload = {
            "email": "loginfail@example.com",
            "password": "WrongPassword!",
        }
        response = self.client.post(self.login_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_me_profile_authenticated(self):
        """Test GET /api/auth/me/ returns current user profile."""
        user = User.objects.create_user(
            email="me@example.com",
            password="Password123!",
            full_name="Me User",
            role=Role.CUSTOMER,
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")
        self.assertEqual(response.data["role"], Role.CUSTOMER)

    def test_role_immutability_through_api(self):
        """Test users cannot modify their own role via PATCH /api/auth/me/."""
        user = User.objects.create_user(
            email="victim@example.com",
            password="Password123!",
            role=Role.CUSTOMER,
        )
        self.client.force_authenticate(user=user)
        response = self.client.patch(self.me_url, {"role": Role.ADMIN}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.CUSTOMER)  # Role remains CUSTOMER
