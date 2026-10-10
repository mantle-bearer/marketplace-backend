from django.contrib import admin

from payments.models import Payment, WebhookEventLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "subscription",
        "amount",
        "currency",
        "status",
        "provider_reference",
        "created_at",
    )
    list_select_related = ("subscription", "subscription__customer", "subscription__plan")
    list_filter = (
        "status",
        "currency",
        "subscription__status",
        "subscription__plan__provider",
        "created_at",
    )
    search_fields = (
        "reference",
        "provider_reference",
        "subscription__customer__email",
        "subscription__plan__name",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WebhookEventLog)
class WebhookEventLogAdmin(admin.ModelAdmin):
    list_display = ("reference", "event", "provider_reference", "processed_at")
    list_filter = ("event", "processed_at")
    search_fields = ("reference", "provider_reference")
    ordering = ("-processed_at",)
    readonly_fields = ("reference", "event", "provider_reference", "payload", "processed_at")
