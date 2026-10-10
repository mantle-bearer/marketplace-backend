from django.urls import path

from plans.views import PlanDetailView, PlanListCreateView

app_name = "plans"

urlpatterns = [
    path("", PlanListCreateView.as_view(), name="plan_list_create"),
    path("<uuid:pk>/", PlanDetailView.as_view(), name="plan_detail"),
]
