from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

from django.db import IntegrityError
from django.test import TransactionTestCase
from django.utils import timezone

from payments.models import Payment, PaymentStatus
from plans.models import BillingInterval, Plan
from subscriptions.models import Subscription, SubscriptionStatus
from user_accounts.models import Role, User


class DatabaseConstraintIntegrityTests(TransactionTestCase):
    """
    Direct database-level tests proving that consistency, state invariants,
    and mutual exclusivity are enforced by PostgreSQL database constraints,
    rather than solely relying on application-layer validation.
    """

    def setUp(self):
        user_manager = cast(Any, User.objects)
        self.provider = user_manager.create_user(
            email="constraint_provider@example.com",
            password="Password123!",
            role=Role.PROVIDER,
        )
        self.customer = user_manager.create_user(
            email="constraint_customer@example.com",
            password="Password123!",
            role=Role.CUSTOMER,
        )
        self.plan = Plan.objects.create(
            name="Constraint Test Plan",
            price=Decimal("100.00"),
            billing_interval=BillingInterval.MONTHLY,
            provider=self.provider,
            is_active=True,
        )

    def test_plan_price_non_negative_constraint(self):
        """Database constraint rejects negative plan price."""
        with self.assertRaises(IntegrityError):
            Plan.objects.create(
                name="Negative Plan",
                price=Decimal("-25.00"),
                billing_interval=BillingInterval.MONTHLY,
                provider=self.provider,
            )

    def test_plan_interval_valid_constraint(self):
        """Database constraint rejects invalid billing interval."""
        with self.assertRaises(IntegrityError):
            Plan.objects.create(
                name="Bogus Interval Plan",
                price=Decimal("25.00"),
                billing_interval="HOURLY",
                provider=self.provider,
            )

    def test_unique_active_subscription_constraint(self):
        """Database partial unique constraint rejects two active subscriptions to the same plan."""
        Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
        )

        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                customer=self.customer,
                plan=self.plan,
                status=SubscriptionStatus.ACTIVE,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
            )

    def test_unique_pending_subscription_constraint(self):
        """Database partial unique constraint rejects two pending subscriptions to the same plan."""
        Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING,
        )

        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                customer=self.customer,
                plan=self.plan,
                status=SubscriptionStatus.PENDING,
            )

    def test_subscription_status_valid_constraint(self):
        """Database check constraint rejects non-existent subscription status."""
        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                customer=self.customer,
                plan=self.plan,
                status="INVALID_STATUS",
            )

    def test_subscription_dates_order_constraint(self):
        """Database check constraint rejects subscription where end_date precedes start_date."""
        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                customer=self.customer,
                plan=self.plan,
                status=SubscriptionStatus.ACTIVE,
                start_date=timezone.now(),
                end_date=timezone.now()
                - timedelta(days=5),  # end_date before start_date
            )

    def test_payment_amount_non_negative_constraint(self):
        """Database check constraint rejects negative payment amount."""
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING,
        )
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                subscription=sub,
                amount=Decimal("-50.00"),
                currency="USD",
                status=PaymentStatus.PENDING,
            )

    def test_payment_status_valid_constraint(self):
        """Database check constraint rejects invalid payment status."""
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING,
        )
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                subscription=sub,
                amount=Decimal("50.00"),
                currency="USD",
                status="INVALID_STATUS",
            )
