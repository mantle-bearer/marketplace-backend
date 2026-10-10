from django.contrib import admin

from plans.models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "price",
        "billing_interval",
        "is_active",
        "provider",
        "created_at",
    )
    list_select_related = ("provider",)
    list_filter = ("is_active", "billing_interval", "provider", "created_at")
    search_fields = ("name", "description", "provider__email", "provider__full_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
