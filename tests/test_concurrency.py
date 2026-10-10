from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError

from payments.models import Payment, PaymentStatus
from payments.services import PaymentWebhookService
from plans.models import BillingInterval, Plan
from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.services import SubscriptionService
from user_accounts.models import Role, User


class ConcurrencyAndIntegrityTests(TransactionTestCase):
    """
    Tests proving concurrency safety, race condition mitigation,
    and idempotency under parallel/concurrent worker threads.
    """

    def setUp(self):
        self.provider = User.objects.create_user(
            email="conc_provider@example.com",
            password="Password123!",
            role=Role.PROVIDER,
        )
        self.customer = User.objects.create_user(
            email="conc_customer@example.com",
            password="Password123!",
            role=Role.CUSTOMER,
        )
        self.plan = Plan.objects.create(
            name="Concurrent High-Load Plan",
            price=Decimal("99.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider,
            is_active=True,
        )

    def test_concurrent_subscription_creation_prevented(self):
        """
        Simulate two simultaneous subscription requests for the same customer and plan.
        Proves that duplicate subscriptions are prevented and only one subscription is generated.
        """
        results = []
        errors = []

        def attempt_subscription():
            connection.close()
            try:
                sub, pay = SubscriptionService.create_subscription(
                    customer=self.customer,
                    plan_id=self.plan.id,
                )
                results.append((sub.id, pay.reference))
            except Exception as exc:
                errors.append(str(exc))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_subscription)
            f2 = executor.submit(attempt_subscription)
            f1.result()
            f2.result()

        total_subs = Subscription.objects.filter(
            customer=self.customer, plan=self.plan
        ).count()
        self.assertEqual(
            total_subs, 1, "Exactly one subscription should exist in database."
        )

    @patch("payments.tasks.send_payment_notification_email_task.delay")
    def test_concurrent_webhook_processing_and_idempotency(self, mock_email_delay):
        """
        Simulate two workers processing the same payment webhook simultaneously.
        Proves select_for_update() serializes processing:
        - Exactly one worker activates the payment & subscription.
        - Exactly one email task is queued.
        - The second worker receives an idempotent response with no duplicate side effects.
        """
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING,
        )
        payment = Payment.objects.create(
            subscription=sub,
            amount=self.plan.price,
            currency="USD",
            status=PaymentStatus.PENDING,
            reference="PAY-CONCURRENT-01",
        )

        webhook_data = {
            "event": "payment.success",
            "reference": payment.reference,
            "provider_reference": "STRIPE-THREAD-RACE",
            "amount": "99.00",
        }

        outcomes = []

        def worker_process():
            connection.close()
            import time

            for _ in range(10):
                try:
                    res = PaymentWebhookService.process_webhook(data=webhook_data)
                    outcomes.append(res)
                    return
                except Exception as exc:
                    if "locked" in str(exc).lower():
                        time.sleep(0.05)
                        continue
                    outcomes.append({"status": "serialized_by_db", "error": str(exc)})
                    return
                finally:
                    connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            w1 = executor.submit(worker_process)
            w2 = executor.submit(worker_process)
            w1.result()
            w2.result()

        self.assertEqual(len(outcomes), 2)
        statuses = [o.get("status") for o in outcomes]
        self.assertIn("success", statuses)
        self.assertIn("idempotent_duplicate", statuses)
        self.assertEqual(mock_email_delay.call_count, 1)

        payment.refresh_from_db()
        sub.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)

    def test_plan_deactivation_during_subscription_rejected(self):
        """
        Proves that if a plan is deactivated, subsequent attempts to subscribe are rejected.
        """
        self.plan.is_active = False
        self.plan.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            SubscriptionService.create_subscription(
                customer=self.customer,
                plan_id=self.plan.id,
            )
