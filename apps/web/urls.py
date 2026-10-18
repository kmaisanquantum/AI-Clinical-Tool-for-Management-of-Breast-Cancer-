from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("patients/", views.patients, name="patients"),
    path("patients/<int:pk>/", views.patient_detail, name="patient-detail"),
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
