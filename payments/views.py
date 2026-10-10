import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.serializers import PaymentWebhookPayloadSerializer
from payments.services import PaymentWebhookService

logger = logging.getLogger("payments")


class PaymentWebhookView(APIView):
    """
    POST /api/payments/webhook/
    Webhook endpoint receiving payment outcome notifications from the payment gateway.
    
    Guarantees:
    - Concurrency-safe via row-level locks on Payment.
    - Idempotent: repeated processing returns 200 OK without duplicate side-effects.
    - Activates subscription only on payment.success.
    - Triggers async Celery email notification to the customer.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Payment Provider Webhook",
        description="Receives payment success or failure notifications from the payment provider.",
        request=PaymentWebhookPayloadSerializer,
        responses={
            200: OpenApiResponse(description="Webhook processed successfully or duplicate acknowledged"),
            400: OpenApiResponse(description="Invalid payload or amount mismatch"),
            404: OpenApiResponse(description="Payment reference not found"),
        },
    )
    def post(self, request, *args, **kwargs):
        signature_header = request.headers.get("X-Webhook-Signature", "")
        if signature_header and not PaymentWebhookService.verify_signature(request.body, signature_header):
            return Response(
                {"detail": "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentWebhookPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = PaymentWebhookService.process_webhook(data=serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)
