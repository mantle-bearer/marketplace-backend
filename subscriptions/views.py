from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from subscriptions.models import Subscription
from subscriptions.permissions import CanCancelSubscription, CanViewSubscription
from subscriptions.serializers import (
    SubscriptionCreateResponseSerializer,
    SubscriptionCreateSerializer,
    SubscriptionListDetailSerializer,
)
from subscriptions.services import SubscriptionService
from user_accounts.models import Role


class SubscriptionListCreateView(generics.ListCreateAPIView):
    """
    POST /api/subscriptions/
    Creates a new subscription in PENDING status, generates a unique payment reference,
    and returns payment details for customer settlement.

    GET /api/subscriptions/
    Lists subscriptions with pagination, filtering by status, and optimized SQL queries
    eliminating N+1 query patterns.
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "plan"]
    ordering_fields = ["created_at", "end_date", "start_date"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SubscriptionCreateSerializer
        return SubscriptionListDetailSerializer

    def get_queryset(self):
        # Query optimization: select_related customer, plan, and plan provider; prefetch related payments
        qs = (
            Subscription.objects.select_related("customer", "plan", "plan__provider")
            .prefetch_related("payments")
            .all()
        )
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        if user.role == Role.ADMIN or user.is_staff:
            return qs

        if user.role == Role.PROVIDER:
            return qs.filter(plan__provider=user)

        return qs.filter(customer=user)

    @extend_schema(
        summary="Subscribe to a plan",
        request=SubscriptionCreateSerializer,
        responses={
            201: SubscriptionCreateResponseSerializer,
            400: OpenApiResponse(
                description="Validation error or duplicate active subscription"
            ),
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription, payment = SubscriptionService.create_subscription(
            customer=request.user,
            plan_id=serializer.validated_data["plan_id"],
        )

        response_payload = {
            "subscription_id": subscription.id,
            "payment_reference": payment.reference,
            "status": subscription.status,
        }
        return Response(response_payload, status=status.HTTP_201_CREATED)


class SubscriptionDetailView(generics.RetrieveAPIView):
    """
    GET /api/subscriptions/{id}/
    Retrieves full details of a specific subscription.
    """

    queryset = (
        Subscription.objects.select_related("customer", "plan", "plan__provider")
        .prefetch_related("payments")
        .all()
    )
    serializer_class = SubscriptionListDetailSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewSubscription]


class SubscriptionCancelView(APIView):
    """
    POST /api/subscriptions/{id}/cancel/
    Cancels an active or pending subscription.
    """

    permission_classes = [permissions.IsAuthenticated, CanCancelSubscription]
    serializer_class = SubscriptionListDetailSerializer

    @extend_schema(
        summary="Cancel a subscription",
        request=None,
        responses={
            200: SubscriptionListDetailSerializer,
            400: OpenApiResponse(description="Cannot cancel expired subscription"),
            404: OpenApiResponse(description="Subscription not found"),
        },
    )
    def post(self, request, pk=None):
        try:
            subscription = Subscription.objects.select_related("customer", "plan").get(
                pk=pk
            )
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND
            )

        self.check_object_permissions(request, subscription)

        cancelled_sub = SubscriptionService.cancel_subscription(
            subscription=subscription,
            user=request.user,
        )

        serializer = SubscriptionListDetailSerializer(cancelled_sub)
        return Response(serializer.data, status=status.HTTP_200_OK)
