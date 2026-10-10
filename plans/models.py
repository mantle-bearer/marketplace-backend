import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class BillingInterval(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    YEARLY = "YEARLY", "Yearly"


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
    )
    is_active = models.BooleanField(default=True)
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    DoesNotExist = models.ObjectDoesNotExist

    class Meta:
        db_table = "subscription_plans"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider"], name="plan_provider_idx"),
            models.Index(fields=["is_active"], name="plan_is_active_idx"),
            models.Index(fields=["billing_interval"], name="plan_interval_idx"),
            models.Index(fields=["created_at"], name="plan_created_at_idx"),
            models.Index(fields=["is_active", "created_at"], name="plan_active_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="plan_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(billing_interval__in=BillingInterval.values),
                name="plan_interval_valid",
            ),
        ]

    def __str__(self):
        provider_email = getattr(self.provider, "email", "")
        return f"{self.name} (${self.price}/{self.billing_interval}) by {provider_email}"
