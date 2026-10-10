import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from subscriptions.models import Subscription, SubscriptionStatus

logger = logging.getLogger("subscriptions")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="subscriptions.tasks.expire_subscriptions_task",
)
def expire_subscriptions_task(self):
    """
    Periodic Celery Beat task:
    Scans for ACTIVE subscriptions whose end_date is in the past and marks them as EXPIRED.
    Employs transaction locking to avoid conflicts with concurrent renewals or cancellations.
    """
    now = timezone.now()
    logger.info(f"Running expire_subscriptions_task at {now.isoformat()}")

    try:
        with transaction.atomic():
            expired_candidates = Subscription.objects.select_for_update(skip_locked=True).filter(
                status=SubscriptionStatus.ACTIVE,
                end_date__lte=now,
            )

            count = 0
            for sub in expired_candidates:
                sub.status = SubscriptionStatus.EXPIRED
                sub.updated_at = now
                sub.save(update_fields=["status", "updated_at"])
                count += 1

            logger.info(f"Successfully expired {count} subscriptions.")
            return {"expired_count": count, "timestamp": now.isoformat()}
    except Exception as exc:
        logger.exception("Error in expire_subscriptions_task")
        raise self.retry(exc=exc)
