from rest_framework import permissions

from user_accounts.models import Role


class IsProviderUser(permissions.BasePermission):
    """Allows write operations only to users with role=PROVIDER."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.PROVIDER
        )


class IsPlanOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission allowing only the provider who owns a plan to modify/delete it.
    Admins can also view/manage.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == Role.ADMIN or request.user.is_staff:
            return True

        return obj.provider_id == request.user.id
