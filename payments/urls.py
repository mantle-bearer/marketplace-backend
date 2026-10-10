from django.urls import path

from payments.views import PaymentWebhookView

app_name = "payments"

urlpatterns = [
    path("webhook/", PaymentWebhookView.as_view(), name="payment_webhook"),
]
