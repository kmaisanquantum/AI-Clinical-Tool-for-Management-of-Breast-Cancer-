from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import user_has_permission
from apps.decision_support.models import DecisionSupportAssessment, RuleVersion
from apps.investigations.models import (
    HistopathologyReport,
    ImagingReport,
    StagingAssessment,
)
from apps.registry.models import Patient, PatientIdentity


def _page(request, template, section, **context):
    """Shared context for the application shell."""
    return render(
        request,
        template,
        {
            "section": section,
            "can_view_identity": user_has_permission(request.user, "view_patient_identity"),
            **context,
        },
    )


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "web/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "dashboard"
        context["can_view_identity"] = user_has_permission(self.request.user, "view_patient_identity")
        context["patient_count"] = Patient.objects.count()
        context["assessment_count"] = DecisionSupportAssessment.objects.count()
        context["active_rule_count"] = RuleVersion.objects.filter(status="active").count()
        context["recent_patients"] = Patient.objects.all().order_by("-created_at")[:5]
        context["recent_assessments"] = (
            DecisionSupportAssessment.objects.select_related("encounter__patient")
            .order_by("-calculated_at")[:5]
        )
        return context


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "web/patient_list.html"
    context_object_name = "patients"
    ordering = ["-created_at"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "patients"
        context["can_view_identity"] = user_has_permission(self.request.user, "view_patient_identity")
        return context


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "web/patient_detail.html"
    context_object_name = "patient"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.object
        context["section"] = "patients"
        context["patient_id"] = patient.id
        context["can_view_identity"] = user_has_permission(self.request.user, "view_patient_identity")

        if context["can_view_identity"]:
            context["identity"] = PatientIdentity.objects.filter(patient=patient).first()

        encounters = list(patient.encounters.select_related("recorded_by").order_by("-encounter_date"))
        for enc in encounters:
            enc.imaging_list = list(ImagingReport.objects.filter(encounter=enc))
            histo_reports = list(HistopathologyReport.objects.filter(encounter=enc))
            for h in histo_reports:
                h.biomarker_data = h.biomarkers.first()
            enc.histo_list = histo_reports
            enc.staging_list = list(StagingAssessment.objects.filter(encounter=enc))
            enc.dsa_list = list(
                DecisionSupportAssessment.objects.filter(encounter=enc).prefetch_related(
                    "rule_versions_applied"
                )
            )

        context["encounters"] = encounters
        return context


class AssessmentListView(LoginRequiredMixin, ListView):
    model = DecisionSupportAssessment
    template_name = "web/assessment_list.html"
    context_object_name = "assessments"
    ordering = ["-calculated_at"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("encounter__patient")
            .prefetch_related("rule_versions_applied")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "assessments"
        context["can_view_identity"] = user_has_permission(self.request.user, "view_patient_identity")
        return context


class AssessmentDetailView(LoginRequiredMixin, DetailView):
    model = DecisionSupportAssessment
    template_name = "web/assessment_detail.html"
    context_object_name = "assessment"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("encounter__patient", "encounter__recorded_by")
            .prefetch_related("rule_versions_applied__decision_rule__guideline_version__guideline")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "assessments"
        context["can_view_identity"] = user_has_permission(self.request.user, "view_patient_identity")
        context["rule_versions"] = self.object.rule_versions_applied.all()
        return context


@login_required
def dashboard(request):
    return DashboardView.as_view()(request)


@login_required
def patients(request):
    return PatientListView.as_view()(request)


@login_required
def patient_detail(request, pk):
    return PatientDetailView.as_view()(request, pk=pk)


@login_required
def assessments(request):
    return AssessmentListView.as_view()(request)


@login_required
def assessment_detail(request, pk):
    return AssessmentDetailView.as_view()(request, pk=pk)


@login_required
def encounters(request):
    return _page(request, "web/encounters.html", "encounters")


@login_required
def encounter_detail(request, pk):
    return _page(request, "web/encounter_detail.html", "encounters", encounter_id=pk)


@login_required
def triage(request):
    return _page(request, "web/triage.html", "triage")


@login_required
def audit(request):
    return _page(request, "web/audit.html", "audit")
