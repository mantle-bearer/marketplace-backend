import logging

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from payments.models import Payment, PaymentStatus, generate_payment_reference
from plans.models import Plan
from subscriptions.models import Subscription, SubscriptionStatus

logger = logging.getLogger("subscriptions")


class SubscriptionService:
    @staticmethod
    def create_subscription(*, customer, plan_id):
        """
        Atomically creates a subscription in PENDING state along with a Payment record.
        
        Concurrency and integrity protections:
        - Acquires row-level lock on Plan (select_for_update) to guarantee active status is checked atomically.
        - Prevents duplicate active subscriptions for the same customer and plan.
        - Employs transaction.atomic() to ensure either both Subscription & Payment are created or neither.
        """
        with transaction.atomic():
            try:
                plan = Plan.objects.select_for_update().get(id=plan_id)
            except Plan.DoesNotExist:
                raise ValidationError({"plan_id": "Plan not found."})

            if not plan.is_active:
                raise ValidationError({"plan_id": "Inactive plans cannot receive new subscriptions."})

            existing_active = Subscription.objects.select_for_update().filter(
                customer=customer,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
            ).first()

            if existing_active:
                raise ValidationError({
                    "plan_id": "A customer must not have two active subscriptions to the same plan."
                })

            existing_pending = Subscription.objects.select_for_update().filter(
                customer=customer,
                plan=plan,
                status=SubscriptionStatus.PENDING,
            ).first()

            if existing_pending:
                payment = existing_pending.payments.filter(status=PaymentStatus.PENDING).first()
                if payment:
                    return existing_pending, payment

            try:
                subscription = Subscription.objects.create(
                    customer=customer,
                    plan=plan,
                    status=SubscriptionStatus.PENDING,
                )
            except IntegrityError as exc:
                logger.info(
                    f"Integrity constraint resolved concurrent race for {customer.email}: {exc}"
                )
                existing = Subscription.objects.filter(
                    customer=customer,
                    plan=plan,
                    status=SubscriptionStatus.PENDING,
                ).first()
                if existing:
                    pay = existing.payments.filter(status=PaymentStatus.PENDING).first()
                    if pay:
                        return existing, pay
                raise ValidationError({
                    "plan_id": "A customer must not have two active or pending subscriptions to the same plan."
                })

            payment = Payment.objects.create(
                subscription=subscription,
                amount=plan.price,
                currency="USD",
                status=PaymentStatus.PENDING,
                reference=generate_payment_reference(),
            )

            logger.info(
                f"Created pending subscription {subscription.id} with payment {payment.reference} for user {customer.email}"
            )
            return subscription, payment

    @staticmethod
    def cancel_subscription(*, subscription, user):
        """
        Cancels an active or pending subscription.
        """
        with transaction.atomic():
            sub = Subscription.objects.select_for_update().get(id=subscription.id)

            if sub.status == SubscriptionStatus.CANCELLED:
                return sub

            if sub.status == SubscriptionStatus.EXPIRED:
                raise ValidationError({"detail": "Cannot cancel an already expired subscription."})

            sub.status = SubscriptionStatus.CANCELLED
            sub.updated_at = timezone.now()
            sub.save(update_fields=["status", "updated_at"])

            logger.info(f"Subscription {sub.id} cancelled by {user.email}")
            return sub
