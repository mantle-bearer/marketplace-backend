from django.urls import path

from subscriptions.views import (
    SubscriptionCancelView,
    SubscriptionDetailView,
    SubscriptionListCreateView,
)

app_name = "subscriptions"

urlpatterns = [
    path("", SubscriptionListCreateView.as_view(), name="subscription_list_create"),
    path("<uuid:pk>/", SubscriptionDetailView.as_view(), name="subscription_detail"),
    path("<uuid:pk>/cancel/", SubscriptionCancelView.as_view(), name="subscription_cancel"),
]
