import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("payments")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="payments.tasks.send_payment_notification_email_task",
)
def send_payment_notification_email_task(
    self,
    *,
    payment_reference,
    customer_email,
    amount,
    currency,
    plan_name,
):
    """
    Simulates sending an asynchronous confirmation email to the customer upon payment success.
    The HTTP request returns immediately without waiting for this task.
    """
    logger.info(
        f"Processing payment notification email for {customer_email} (Ref: {payment_reference})"
    )
    subject = f"Payment Confirmation - Subscription to {plan_name}"
    message = (
        f"Hello,\n\n"
        f"Thank you for your payment!\n"
        f"Your subscription to '{plan_name}' is now ACTIVE.\n\n"
        f"Details:\n"
        f"- Payment Reference: {payment_reference}\n"
        f"- Amount: {amount} {currency}\n\n"
        f"Best regards,\n"
        f"The Marketplace Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@marketplace.com"),
            recipient_list=[customer_email],
            fail_silently=False,
        )
        logger.info(f"Payment confirmation email successfully sent to {customer_email}")
        return {
            "status": "sent",
            "customer_email": customer_email,
            "payment_reference": payment_reference,
        }
    except Exception as exc:
        logger.exception(
            f"Failed to send payment email to {customer_email}. Retrying..."
        )
        raise self.retry(exc=exc)
