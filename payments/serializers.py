from rest_framework import serializers

from payments.models import Payment


class PaymentWebhookPayloadSerializer(serializers.Serializer):
    event = serializers.ChoiceField(
        choices=["payment.success", "payment.failed"],
        required=True,
    )
    reference = serializers.CharField(max_length=64, required=True)
    provider_reference = serializers.CharField(
        max_length=128, required=False, allow_blank=True, allow_null=True
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)


class PaymentSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(
        source="subscription.customer.email", read_only=True
    )
    plan_name = serializers.CharField(source="subscription.plan.name", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "reference",
            "subscription",
            "customer_email",
            "plan_name",
            "amount",
            "currency",
            "status",
            "provider_reference",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
