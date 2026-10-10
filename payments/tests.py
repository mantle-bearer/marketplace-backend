from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from payments.models import Payment, PaymentStatus
from plans.models import BillingInterval, Plan
from subscriptions.models import Subscription, SubscriptionStatus
from user_accounts.models import Role, User


class PaymentWebhookAPITests(APITestCase):
    def setUp(self):
        self.provider = User.objects.create_user(
            email="provider@paytest.com",
            password="Password123!",
            role=Role.PROVIDER,
        )
        self.customer = User.objects.create_user(
            email="customer@paytest.com",
            password="Password123!",
            role=Role.CUSTOMER,
        )
        self.plan = Plan.objects.create(
            name="Premium Plan",
            price=Decimal("15000.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider,
            is_active=True,
        )
        self.subscription = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING,
        )
        self.payment = Payment.objects.create(
            subscription=self.subscription,
            amount=self.plan.price,
            currency="USD",
            status=PaymentStatus.PENDING,
            reference="PAY-8F92A1000001",
        )
        self.webhook_url = reverse("payments:payment_webhook")

    @patch("payments.tasks.send_payment_notification_email_task.delay")
    def test_successful_webhook_processing(self, mock_email_delay):
        """Test successful webhook marks payment SUCCESS, activates subscription, and enqueues email."""
        payload = {
            "event": "payment.success",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-123456",
            "amount": "15000.00",
        }
        response = self.client.post(self.webhook_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.payment.provider_reference, "STRIPE-123456")

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, SubscriptionStatus.ACTIVE)
        self.assertIsNotNone(self.subscription.start_date)
        self.assertIsNotNone(self.subscription.end_date)
        self.assertIsNotNone(self.subscription.next_billing_date)
        self.assertEqual(
            self.subscription.end_date, self.subscription.next_billing_date
        )

        mock_email_delay.assert_called_once()

    def test_failed_webhook_processing(self):
        """Test failed webhook marks payment FAILED and does NOT activate subscription."""
        payload = {
            "event": "payment.failed",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-FAILED-1",
            "amount": "15000.00",
        }
        response = self.client.post(self.webhook_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "failed")

        self.payment.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.FAILED)
        self.assertEqual(self.subscription.status, SubscriptionStatus.PENDING)

    def test_invalid_payment_reference(self):
        """Test webhook with unknown reference returns validation error."""
        payload = {
            "event": "payment.success",
            "reference": "PAY-NONEXISTENT",
            "provider_reference": "STRIPE-000",
            "amount": "15000.00",
        }
        response = self.client.post(self.webhook_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reference", response.data)

    def test_incorrect_payment_amount(self):
        """Test webhook with amount mismatch is rejected."""
        payload = {
            "event": "payment.success",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-123",
            "amount": "99.00",
        }
        response = self.client.post(self.webhook_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PENDING)

    @patch("payments.tasks.send_payment_notification_email_task.delay")
    def test_duplicate_webhook_is_idempotent(self, mock_email_delay):
        """Test repeated delivery of the same webhook produces NO duplicate side effects."""
        payload = {
            "event": "payment.success",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-123456",
            "amount": "15000.00",
        }

        resp1 = self.client.post(self.webhook_url, payload, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_email_delay.call_count, 1)

        resp2 = self.client.post(self.webhook_url, payload, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["status"], "idempotent_duplicate")

        self.assertEqual(mock_email_delay.call_count, 1)
