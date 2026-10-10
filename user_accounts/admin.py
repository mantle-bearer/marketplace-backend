from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from user_accounts.models import Role, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "full_name",
        "role",
        "is_active",
        "email_verified",
        "created_at",
    )
    list_filter = ("role", "is_active", "email_verified", "created_at")
    search_fields = ("email", "full_name", "username")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at", "email_verified_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal Info",
            {"fields": ("full_name", "username")},
        ),
        (
            "Role & Permissions",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Verification",
            {"fields": ("email_verified", "email_verified_at")},
        ),
        (
            "Timestamps",
            {"fields": ("id", "created_at", "updated_at")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password",
                    "role",
                    "full_name",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


class ProviderProxy(User):
    class Meta(User.Meta):
        proxy = True
        verbose_name = "Provider"
        verbose_name_plural = "Providers"


@admin.register(ProviderProxy)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "is_active", "created_at")
    search_fields = ("email", "full_name")
    list_filter = ("is_active", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role=Role.PROVIDER)
