from decimal import Decimal

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from plans.models import BillingInterval, Plan
from user_accounts.models import Role, User


class PlanAPITests(APITestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.provider1 = User.objects.create_user(
            email="provider1@test.com",
            password="Password123!",
            role=Role.PROVIDER,
        )
        self.provider2 = User.objects.create_user(
            email="provider2@test.com",
            password="Password123!",
            role=Role.PROVIDER,
        )
        self.customer = User.objects.create_user(
            email="customer@test.com",
            password="Password123!",
            role=Role.CUSTOMER,
        )
        self.plans_url = reverse("plans:plan_list_create")

    def test_provider_creates_plan_successfully(self):
        """Test authenticated provider can create a subscription plan."""
        self.client.force_authenticate(user=self.provider1)
        payload = {
            "name": "Standard Tier",
            "description": "Access to standard features",
            "price": "49.99",
            "billing_interval": BillingInterval.MONTHLY,
            "is_active": True,
        }
        response = self.client.post(self.plans_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Standard Tier")
        self.assertEqual(response.data["provider"], self.provider1.id)

    def test_customer_cannot_create_plan(self):
        """Test customer is forbidden from creating subscription plans."""
        self.client.force_authenticate(user=self.customer)
        payload = {
            "name": "Unauthorized Plan",
            "price": "99.99",
            "billing_interval": BillingInterval.MONTHLY,
        }
        response = self.client.post(self.plans_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_provider_cannot_modify_another_providers_plan(self):
        """Test provider 2 cannot modify plan owned by provider 1."""
        plan = Plan.objects.create(
            name="Provider 1 Original",
            price=Decimal("20.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider1,
        )
        detail_url = reverse("plans:plan_detail", kwargs={"pk": plan.id})

        self.client.force_authenticate(user=self.provider2)
        response = self.client.patch(detail_url, {"name": "Hacked Name"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.provider1)
        response = self.client.patch(
            detail_url, {"name": "Updated Name"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")

    def test_plan_caching_and_invalidation(self):
        """Test public plan list caching and invalidation upon plan mutation."""
        Plan.objects.create(
            name="Cached Plan",
            price=Decimal("15.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider1,
            is_active=True,
        )

        res1 = self.client.get(self.plans_url)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res1.data.get("results", res1.data)), 1)

        Plan.objects.create(
            name="Uncached DB Plan",
            price=Decimal("30.00"),
            billing_interval=BillingInterval.YEARLY,
            provider=self.provider1,
            is_active=True,
        )

        res2 = self.client.get(self.plans_url)
        self.assertEqual(len(res2.data.get("results", res2.data)), 1)

        self.client.force_authenticate(user=self.provider1)
        self.client.post(
            self.plans_url,
            {
                "name": "API Triggered Plan",
                "price": "40.00",
                "billing_interval": BillingInterval.MONTHLY,
            },
            format="json",
        )

        self.client.force_authenticate(user=None)
        res3 = self.client.get(self.plans_url)
        self.assertEqual(len(res3.data.get("results", res3.data)), 3)
