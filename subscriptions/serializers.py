from rest_framework import serializers

from plans.serializers import PlanSerializer
from subscriptions.models import Subscription


class SubscriptionCreateSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField(required=True)


class SubscriptionCreateResponseSerializer(serializers.Serializer):
    subscription_id = serializers.UUIDField()
    payment_reference = serializers.CharField()
    status = serializers.CharField()


class SubscriptionPaymentMiniSerializer(serializers.Serializer):
    reference = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class SubscriptionListDetailSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    payments = SubscriptionPaymentMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "customer",
            "customer_email",
            "customer_name",
            "plan",
            "status",
            "start_date",
            "end_date",
            "next_billing_date",
            "created_at",
            "updated_at",
            "payments",
        )
        read_only_fields = fields
