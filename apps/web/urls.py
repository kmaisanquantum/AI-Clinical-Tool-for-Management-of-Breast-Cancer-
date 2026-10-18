from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("patients/", views.PatientListView.as_view(), name="patients"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient-detail"),
    path("assessments/", views.AssessmentListView.as_view(), name="assessment-list"),
    path("assessments/<int:pk>/", views.AssessmentDetailView.as_view(), name="assessment-detail"),
    path("encounters/", views.encounters, name="encounters"),
    path("encounters/<int:pk>/", views.encounter_detail, name="encounter-detail"),
    path("triage/", views.triage, name="triage"),
    path("audit/", views.audit, name="audit"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="web/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
