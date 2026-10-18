from django.urls import path

from .views import DashboardSummaryView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]
