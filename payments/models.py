import uuid
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator
from django.db import models


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


def generate_payment_reference():
    """Generates a unique payment reference formatted like PAY-8F92A1..."""
    return f"PAY-{uuid.uuid4().hex[:12].upper()}"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    reference = models.CharField(
        max_length=64,
        unique=True,
        default=generate_payment_reference,
        db_index=True,
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    provider_reference = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subscription", "status"], name="pay_sub_status_idx"),
            models.Index(fields=["reference"], name="pay_reference_idx"),
            models.Index(fields=["status", "created_at"], name="pay_status_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=PaymentStatus.values),
                name="payment_status_valid",
            ),
        ]

    def __str__(self):
        return f"Payment {self.reference} ({self.amount} {self.currency}) - {self.status}"


class WebhookEventLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    reference = models.CharField(max_length=64, db_index=True)
    event = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=128, null=True, blank=True)
    payload = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    processed_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        db_table = "payment_webhook_logs"
        ordering = ["-processed_at"]
        indexes = [
            models.Index(fields=["reference", "event"], name="webhook_ref_event_idx"),
        ]

    def __str__(self):
        return f"Webhook {self.event} for {self.reference} at {self.processed_at}"
