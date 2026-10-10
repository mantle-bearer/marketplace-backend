from rest_framework import permissions

from user_accounts.models import Role


class IsCustomer(permissions.BasePermission):
    """Allows access only to authenticated customers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.CUSTOMER
        )


class IsProvider(permissions.BasePermission):
    """Allows access only to authenticated providers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.PROVIDER
        )


class IsAdminUserRole(permissions.BasePermission):
    """Allows access to users with ADMIN role, staff, or superusers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.role == Role.ADMIN
                or request.user.is_staff
                or request.user.is_superuser
            )
        )
