from rest_framework import permissions

from user_accounts.models import Role


class CanViewSubscription(permissions.BasePermission):
    """
    Access rules:
    - Customer can view only their own subscriptions.
    - Provider can view subscriptions belonging to their plans.
    - Admin can view all subscriptions.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role == Role.ADMIN or user.is_staff:
            return True

        if user.role == Role.CUSTOMER and obj.customer_id == user.id:
            return True

        return bool(user.role == Role.PROVIDER and obj.plan.provider_id == user.id)


class CanCancelSubscription(permissions.BasePermission):
    """
    Only the subscription's customer or an admin can cancel the subscription.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role == Role.ADMIN or user.is_staff:
            return True

        return obj.customer_id == user.id
