from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("patients/", views.PatientListView.as_view(), name="patients"),
    path("patients/new/", views.patient_create, name="patient-create"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient-detail"),
    path("patients/<int:pk>/encounters/new/", views.encounter_create, name="encounter-create"),
    path("encounters/<int:pk>/investigations/", views.investigation_create_or_edit, name="investigation-edit"),
    path("encounters/<int:pk>/evaluate/", views.encounter_evaluate, name="encounter-evaluate"),
    path("assessments/", views.AssessmentListView.as_view(), name="assessment-list"),
    path("assessments/<int:pk>/", views.AssessmentDetailView.as_view(), name="assessment-detail"),
    path("assessments/<int:pk>/review/", views.assessment_review, name="assessment-review"),
    path("encounters/", views.encounters, name="encounters"),
    path("encounters/<int:pk>/", views.encounter_detail, name="encounter-detail"),
    path("triage/", views.triage, name="triage"),
    path("audit/", views.audit, name="audit"),
    path("settings/users/", views.user_list, name="user-list"),
    path("settings/users/new/", views.user_create, name="user-create"),
    path("settings/users/<int:pk>/edit/", views.user_edit, name="user-edit"),
    path("settings/users/<int:pk>/reset-password/", views.user_password_reset, name="user-password-reset"),
    path("settings/users/<int:pk>/toggle-active/", views.user_toggle_active, name="user-toggle-active"),
    path("settings/roles/", views.role_list, name="role-list"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="web/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
