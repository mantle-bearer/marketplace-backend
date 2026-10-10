from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from plans.models import BillingInterval, Plan
from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.tasks import expire_subscriptions_task
from user_accounts.models import Role, User


class SubscriptionAPITests(APITestCase):
    client: APIClient

    def setUp(self):
        self.provider = User.objects.create_user(
            email="provider@subtest.com",
            password="Password123!",
            role=Role.PROVIDER,
        )
        self.customer = User.objects.create_user(
            email="customer@subtest.com",
            password="Password123!",
            role=Role.CUSTOMER,
        )
        self.plan = Plan.objects.create(
            name="Pro Subscription",
            price=Decimal("150.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider,
            is_active=True,
        )
        self.subscriptions_url = reverse("subscriptions:subscription_list_create")

    def test_successful_subscription_creation(self):
        """Test subscribing returns PENDING status and unique payment reference."""
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            self.subscriptions_url,
            {"plan_id": self.plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("subscription_id", response.data)
        self.assertIn("payment_reference", response.data)
        self.assertEqual(response.data["status"], SubscriptionStatus.PENDING)
        self.assertTrue(response.data["payment_reference"].startswith("PAY-"))

    def test_inactive_plan_cannot_receive_subscriptions(self):
        """Test subscribing to an inactive plan is rejected."""
        inactive_plan = Plan.objects.create(
            name="Decommissioned Plan",
            price=Decimal("50.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider,
            is_active=False,
        )
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            self.subscriptions_url,
            {"plan_id": inactive_plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("plan_id", response.data)

    def test_duplicate_active_subscription_prevented(self):
        """Test customer cannot create a duplicate subscription if they already have an ACTIVE one."""
        Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
        )

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            self.subscriptions_url,
            {"plan_id": self.plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("plan_id", response.data)

    def test_subscription_cancellation(self):
        """Test customer can cancel their subscription."""
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
        )
        cancel_url = reverse("subscriptions:subscription_cancel", kwargs={"pk": sub.id})

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubscriptionStatus.CANCELLED)

    def test_subscription_expiry_periodic_task(self):
        """Test Celery Beat task identifies subscriptions past end_date and marks them EXPIRED."""
        expired_sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now() - timedelta(days=40),
            end_date=timezone.now() - timedelta(days=10),
        )

        active_sub = Subscription.objects.create(
            customer=self.customer,
            plan=Plan.objects.create(
                name="Another Plan",
                price=Decimal("10.00"),
                provider=self.provider,
            ),
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=20),
        )

        result = expire_subscriptions_task()
        self.assertEqual(result["expired_count"], 1)

        expired_sub.refresh_from_db()
        active_sub.refresh_from_db()
        self.assertEqual(expired_sub.status, SubscriptionStatus.EXPIRED)
        self.assertEqual(active_sub.status, SubscriptionStatus.ACTIVE)

    def test_subscription_listing_filters_and_pagination(self):
        """Test GET /api/subscriptions/ supports ?status=ACTIVE and pagination."""
        for i in range(12):
            plan = Plan.objects.create(
                name=f"Sub Plan {i}",
                price=Decimal("10.00"),
                provider=self.provider,
            )
            Subscription.objects.create(
                customer=self.customer,
                plan=plan,
                status=SubscriptionStatus.ACTIVE if i % 2 == 0 else SubscriptionStatus.CANCELLED,
            )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(f"{self.subscriptions_url}?status=ACTIVE")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data["results"]:
            self.assertEqual(item["status"], SubscriptionStatus.ACTIVE)

        p2_response = self.client.get(f"{self.subscriptions_url}?page=2")
        self.assertEqual(p2_response.status_code, status.HTTP_200_OK)
