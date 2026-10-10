import hashlib
import hmac
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from payments.models import Payment, PaymentStatus, WebhookEventLog
from payments.tasks import send_payment_notification_email_task
from plans.models import BillingInterval
from subscriptions.models import Subscription, SubscriptionStatus

logger = logging.getLogger("payments")


class PaymentWebhookService:
    @staticmethod
    def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
        """
        Verifies optional HMAC-SHA256 signature passed in X-Webhook-Signature header.
        """
        secret = getattr(settings, "WEBHOOK_SECRET", "")
        if not secret or not signature_header:
            return True  # If no secret or header provided, bypass for simulation

        expected = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    @classmethod
    def process_webhook(cls, *, data: dict) -> dict:
        """
        Processes payment webhook with strong concurrency and idempotency guarantees.
        
        Guarantees:
        - Row-level lock on Payment via select_for_update() serializes concurrent deliveries.
        - If payment is already in terminal state (SUCCESS / FAILED), idempotently acknowledges without duplicate side effects.
        - Verifies amount matches payment record.
        - Activates subscription only on payment.success and calculates subscription interval dates.
        - Queues Celery email notification asynchronously (non-blocking).
        """
        event = data.get("event")
        reference = data.get("reference")
        provider_reference = data.get("provider_reference")
        raw_amount = data.get("amount")

        if not event or not reference or raw_amount is None:
            raise ValidationError({
                "detail": "Missing required webhook fields: 'event', 'reference', and 'amount' are mandatory."
            })

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError):
            raise ValidationError({"amount": "Invalid amount format."})

        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .select_related("subscription", "subscription__plan", "subscription__customer")
                .filter(reference=reference)
                .first()
            )

            if not payment:
                raise ValidationError({"reference": f"Payment with reference '{reference}' not found."})

            if payment.amount != amount:
                logger.warning(
                    f"Webhook amount mismatch for {reference}: received {amount}, expected {payment.amount}"
                )
                raise ValidationError({
                    "amount": f"Amount mismatch: received {amount}, expected {payment.amount}"
                })

            clean_payload = {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in data.items()
            }
            WebhookEventLog.objects.create(
                reference=reference,
                event=event,
                provider_reference=provider_reference,
                payload=clean_payload,
            )

            if payment.status in [PaymentStatus.SUCCESS, PaymentStatus.FAILED]:
                logger.info(
                    f"Idempotent webhook: Payment {reference} is already {payment.status}. Skipping duplicate processing."
                )
                return {
                    "status": "idempotent_duplicate",
                    "payment_status": payment.status,
                    "subscription_id": payment.subscription_id,
                    "message": f"Webhook already processed. Payment status is already {payment.status}.",
                }

            subscription = payment.subscription
            plan = subscription.plan

            if event == "payment.success":
                payment.status = PaymentStatus.SUCCESS
                payment.provider_reference = provider_reference
                payment.updated_at = timezone.now()
                payment.save(update_fields=["status", "provider_reference", "updated_at"])

                sub = Subscription.objects.select_for_update().get(id=subscription.id)
                now = timezone.now()

                if plan.billing_interval == BillingInterval.YEARLY:
                    end_date = now + timedelta(days=365)
                else:
                    end_date = now + timedelta(days=30)

                sub.status = SubscriptionStatus.ACTIVE
                sub.start_date = now
                sub.end_date = end_date
                sub.next_billing_date = end_date
                sub.updated_at = now
                sub.save(
                    update_fields=[
                        "status",
                        "start_date",
                        "end_date",
                        "next_billing_date",
                        "updated_at",
                    ]
                )

                logger.info(
                    f"Activated subscription {sub.id} until {end_date.isoformat()} for customer {sub.customer.email}"
                )

                try:
                    send_payment_notification_email_task.delay(
                        payment_reference=payment.reference,
                        customer_email=sub.customer.email,
                        amount=str(payment.amount),
                        currency=payment.currency,
                        plan_name=plan.name,
                    )
                except Exception as task_exc:
                    logger.warning(f"Could not enqueue email task: {task_exc}")

                return {
                    "status": "success",
                    "payment_status": PaymentStatus.SUCCESS,
                    "subscription_id": sub.id,
                    "subscription_status": SubscriptionStatus.ACTIVE,
                    "start_date": sub.start_date.isoformat(),
                    "end_date": sub.end_date.isoformat(),
                }

            elif event == "payment.failed":
                payment.status = PaymentStatus.FAILED
                payment.provider_reference = provider_reference
                payment.updated_at = timezone.now()
                payment.save(update_fields=["status", "provider_reference", "updated_at"])

                logger.info(f"Marked payment {reference} as FAILED.")
                return {
                    "status": "failed",
                    "payment_status": PaymentStatus.FAILED,
                    "subscription_id": subscription.id,
                    "subscription_status": subscription.status,
                }

            else:
                raise ValidationError({"event": f"Unsupported webhook event type: '{event}'."})
