from rest_framework import serializers

from plans.models import Plan
from plans.services import invalidate_plans_cache


class PlanSerializer(serializers.ModelSerializer):
    provider_email = serializers.EmailField(source="provider.email", read_only=True)
    provider_name = serializers.CharField(source="provider.full_name", read_only=True)

    class Meta:
        model = Plan
        fields = (
            "id",
            "name",
            "description",
            "price",
            "billing_interval",
            "is_active",
            "provider",
            "provider_email",
            "provider_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "provider", "created_at", "updated_at")


class PlanCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "id",
            "name",
            "description",
            "price",
            "billing_interval",
            "is_active",
            "provider",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "provider", "created_at", "updated_at")

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price must be a non-negative number.")
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        plan = Plan.objects.create(provider=user, **validated_data)
        invalidate_plans_cache()
        return plan

    def update(self, instance, validated_data):
        plan = super().update(instance, validated_data)
        invalidate_plans_cache()
        return plan
