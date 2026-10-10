import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class SubscriptionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past Due"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
        db_index=True,
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    DoesNotExist = models.ObjectDoesNotExist

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"], name="sub_cust_status_idx"),
            models.Index(fields=["plan", "status"], name="sub_plan_status_idx"),
            models.Index(fields=["status", "end_date"], name="sub_status_end_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "plan"],
                condition=Q(status=SubscriptionStatus.ACTIVE),
                name="unique_active_subscription_per_customer_plan",
            ),
            models.UniqueConstraint(
                fields=["customer", "plan"],
                condition=Q(status=SubscriptionStatus.PENDING),
                name="unique_pending_subscription_per_customer_plan",
            ),
            models.CheckConstraint(
                condition=Q(status__in=SubscriptionStatus.values),
                name="subscription_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(start_date__isnull=True, end_date__isnull=True)
                    | Q(
                        start_date__isnull=False,
                        end_date__isnull=False,
                        end_date__gte=models.F("start_date"),
                    )
                ),
                name="subscription_dates_consistent",
            ),
        ]

    def __str__(self):
        customer_email = getattr(self.customer, "email", "")
        plan_name = getattr(self.plan, "name", "")
        return f"Subscription #{self.id} - {customer_email} -> {plan_name} ({self.status})"
