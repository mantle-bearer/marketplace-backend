from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response

from plans.models import Plan
from plans.permissions import IsPlanOwnerOrReadOnly, IsProviderUser
from plans.serializers import PlanCreateUpdateSerializer, PlanSerializer
from plans.services import (
    get_cached_plans_response,
    invalidate_plans_cache,
    set_cached_plans_response,
)


class PlanListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/plans/ - List active subscription plans (cached via Redis for high performance).
    POST /api/plans/ - Create a new subscription plan (Provider only).
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsProviderUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["billing_interval", "is_active", "provider"]
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PlanCreateUpdateSerializer
        return PlanSerializer

    def get_queryset(self):
        # Optimized query with provider select_related to eliminate N+1 queries
        qs = Plan.objects.select_related("provider")
        user = self.request.user

        if user.is_authenticated and (user.is_staff or user.role == "admin"):
            return qs.all()
        if user.is_authenticated and user.role == "provider" and self.request.query_params.get("my_plans"):
            return qs.filter(provider=user)

        return qs.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        has_query_params = bool(request.query_params)
        if not has_query_params:
            cached_data = get_cached_plans_response()
            if cached_data is not None:
                return Response(cached_data)

        response = super().list(request, *args, **kwargs)

        if not has_query_params and response.status_code == status.HTTP_200_OK:
            set_cached_plans_response(response.data)

        return response


class PlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/plans/{id}/ - Retrieve plan details.
    PATCH  /api/plans/{id}/ - Update plan (Owner Provider only).
    DELETE /api/plans/{id}/ - Delete plan (Owner Provider only).
    """

    queryset = Plan.objects.select_related("provider").all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsPlanOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return PlanCreateUpdateSerializer
        return PlanSerializer

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_plans_cache()
