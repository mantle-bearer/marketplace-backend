from django.contrib import admin

from subscriptions.models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "plan",
        "status",
        "start_date",
        "end_date",
        "next_billing_date",
        "created_at",
    )
    list_select_related = ("customer", "plan", "plan__provider")
    list_filter = (
        "status",
        "plan__provider",
        "created_at",
        "end_date",
    )
    search_fields = (
        "customer__email",
        "customer__full_name",
        "plan__name",
        "payments__reference",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
