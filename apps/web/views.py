from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import user_has_permission
from apps.audit.models import AuditEvent
from apps.clinical.models import ClinicalNote, Encounter
from apps.decision_support.engine import evaluate_encounter
from apps.decision_support.models import (
    DecisionSupportAssessment,
    ManagementPlan,
    RuleVersion,
)
from apps.investigations.models import (
    HistopathologyReport,
    ImagingReport,
    StagingAssessment,
)
from apps.registry.models import Patient, PatientIdentity

from .forms import (
    BiomarkerResultForm,
    ClinicianReviewForm,
    EncounterForm,
    HistopathologyReportForm,
    PasswordResetForm,
    PatientForm,
    PatientIdentityForm,
    StagingAssessmentForm,
    UserCreateForm,
    UserEditForm,
)


def _page(request, template, section, **context):
    """Shared context for the application shell."""
    return render(
        request,
        template,
        {
            "section": section,
            "can_view_identity": user_has_permission(request.user, "view_patient_identity"),
            "can_record_clinical": user_has_permission(request.user, "record_clinical"),
            **context,
        },
    )


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "web/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "dashboard"
        context["can_view_identity"] = user_has_permission(self.request.user, "view_patient_identity")
        context["can_record_clinical"] = user_has_permission(self.request.user, "record_clinical")
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
        context["can_record_clinical"] = user_has_permission(self.request.user, "record_clinical")
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
        context["can_record_clinical"] = user_has_permission(self.request.user, "record_clinical")

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
        context["can_record_clinical"] = user_has_permission(self.request.user, "record_clinical")
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
        context["can_record_clinical"] = user_has_permission(self.request.user, "record_clinical")
        context["rule_versions"] = self.object.rule_versions_applied.all()
        return context


@login_required
def patient_create(request):
    if not user_has_permission(request.user, "record_clinical"):
        raise PermissionDenied("You do not have permission to register patients.")

    can_view_identity = user_has_permission(request.user, "view_patient_identity")

    if request.method == "POST":
        p_form = PatientForm(request.POST)
        id_form = PatientIdentityForm(request.POST) if can_view_identity else None

        if p_form.is_valid() and (not id_form or id_form.is_valid()):
            patient = p_form.save()
            if id_form and id_form.cleaned_data.get("full_name"):
                identity = id_form.save(commit=False)
                identity.patient = patient
                identity.save()

            messages.success(request, f"Patient #{patient.id} registered successfully.")
            return redirect(f"/ui/patients/{patient.id}/")
    else:
        p_form = PatientForm()
        id_form = PatientIdentityForm() if can_view_identity else None

    return _page(
        request,
        "web/patient_form.html",
        "patients",
        p_form=p_form,
        id_form=id_form,
        can_view_identity=can_view_identity,
    )


@login_required
def encounter_create(request, pk):
    if not user_has_permission(request.user, "record_clinical"):
        raise PermissionDenied("You do not have permission to record encounters.")

    patient = get_object_or_404(Patient, id=pk)

    if request.method == "POST":
        form = EncounterForm(request.POST)
        if form.is_valid():
            encounter = form.save(commit=False)
            encounter.patient = patient
            encounter.recorded_by = request.user
            if not encounter.encounter_date:
                encounter.encounter_date = timezone.now()
            encounter.save()

            notes = form.cleaned_data.get("notes")
            if notes:
                ClinicalNote.objects.create(
                    encounter=encounter,
                    note_type="progress_note",
                    content=notes,
                    recorded_by=request.user,
                )

            messages.success(request, f"Encounter #{encounter.id} created for Patient #{patient.id}.")
            return redirect(f"/ui/patients/{patient.id}/")
    else:
        form = EncounterForm(initial={"encounter_date": timezone.now().strftime("%Y-%m-%dT%H:%M")})

    return _page(request, "web/encounter_form.html", "patients", patient=patient, form=form)


@login_required
def investigation_create_or_edit(request, pk):
    if not user_has_permission(request.user, "record_clinical"):
        raise PermissionDenied("You do not have permission to record clinical investigations.")

    encounter = get_object_or_404(Encounter, id=pk)
    histo = HistopathologyReport.objects.filter(encounter=encounter).first()
    bm = histo.biomarkers.first() if histo else None
    stg = StagingAssessment.objects.filter(encounter=encounter).first()

    if request.method == "POST":
        histo_form = HistopathologyReportForm(request.POST, instance=histo)
        bm_form = BiomarkerResultForm(request.POST, instance=bm)
        stg_form = StagingAssessmentForm(request.POST, instance=stg)

        if histo_form.is_valid() and bm_form.is_valid() and stg_form.is_valid():
            h_obj = histo_form.save(commit=False)
            h_obj.encounter = encounter
            h_obj.recorded_by = request.user
            h_obj.save()

            bm_obj = bm_form.save(commit=False)
            bm_obj.histopathology_report = h_obj
            bm_obj.recorded_by = request.user
            bm_obj.save()

            s_obj = stg_form.save(commit=False)
            s_obj.encounter = encounter
            s_obj.recorded_by = request.user
            s_obj.save()

            messages.success(request, f"Investigations updated for Encounter #{encounter.id}.")
            return redirect(f"/ui/patients/{encounter.patient_id}/")
    else:
        histo_form = HistopathologyReportForm(instance=histo)
        bm_form = BiomarkerResultForm(instance=bm)
        stg_form = StagingAssessmentForm(instance=stg)

    return _page(
        request,
        "web/investigations_form.html",
        "patients",
        encounter=encounter,
        histo_form=histo_form,
        bm_form=bm_form,
        stg_form=stg_form,
    )


@login_required
def encounter_evaluate(request, pk):
    if not user_has_permission(request.user, "record_clinical"):
        raise PermissionDenied("You do not have permission to trigger triage evaluations.")

    encounter = get_object_or_404(Encounter, id=pk)
    eval_result = evaluate_encounter(encounter)

    assessment = DecisionSupportAssessment.objects.create(
        encounter=encounter,
        triage_level=eval_result["triage_level"],
        summary_recommendation=eval_result["summary_recommendation"],
        molecular_subtype=eval_result.get("molecular_subtype", ""),
        molecular_subtype_fk=eval_result.get("molecular_subtype_fk"),
        incomplete_data=eval_result.get("incomplete_data", False),
        management_plan=eval_result.get("management_plan", []),
        referral_recommendation=eval_result.get("referral_recommendation", ""),
        ai_suggestion=eval_result.get("ai_suggestion", {}),
        ai_provider_version=eval_result.get("ai_provider_version", ""),
        reasoning_payload=eval_result["reasoning_payload"],
    )

    for item in eval_result.get("management_plan", []):
        ManagementPlan.objects.create(
            assessment=assessment,
            plan_type=item.get("plan_type", "general"),
            recommendation_text=item.get("recommendation_text", ""),
            requires_referral=item.get("requires_referral", False),
            referral_destination=item.get("referral_destination", ""),
            timeframe_days=item.get("timeframe_days"),
            resource_level=item.get("resource_level", ""),
        )

    matched_rule_versions = eval_result.get("matched_rule_versions", [])
    if matched_rule_versions:
        assessment.rule_versions_applied.set(matched_rule_versions)

    AuditEvent.objects.create(
        user=request.user,
        action="CREATE",
        resource_type="DecisionSupportAssessment",
        resource_id=str(assessment.id),
        details={"encounter_id": encounter.id, "triage_level": assessment.triage_level},
    )

    messages.success(request, f"Triage assessment #{assessment.id} generated for Encounter #{encounter.id}.")
    return redirect(f"/ui/assessments/{assessment.id}/")


@login_required
def assessment_review(request, pk):
    assessment = get_object_or_404(DecisionSupportAssessment, id=pk)

    if request.method == "POST":
        form = ClinicianReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.assessment = assessment
            review.reviewer = request.user
            review.save()

            AuditEvent.objects.create(
                user=request.user,
                action="CREATE",
                resource_type="ClinicianReview",
                resource_id=str(review.id),
                details={"assessment_id": assessment.id, "agree": review.agree_with_recommendation},
            )

            messages.success(request, f"Clinician review submitted for Assessment #{assessment.id}.")
            return redirect(f"/ui/assessments/{assessment.id}/")

    messages.error(request, "Failed to submit clinician review.")
    return redirect(f"/ui/assessments/{assessment.id}/")


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
    """Live clinical worklist: pending encounters & assessments awaiting review."""
    pending_encounters = Encounter.objects.filter(decision_assessments__isnull=True).select_related("patient", "recorded_by").order_by("-encounter_date")
    pending_assessments = DecisionSupportAssessment.objects.filter(clinician_reviews__isnull=True).select_related("encounter__patient").order_by("-calculated_at")

    return _page(
        request,
        "web/triage.html",
        "triage",
        pending_encounters=pending_encounters,
        pending_assessments=pending_assessments,
    )


@login_required
def audit(request):
    return _page(request, "web/audit.html", "audit")


# ==============================================================================
# SETTINGS & USER MANAGEMENT VIEWS
# ==============================================================================

def _check_manage_users(user):
    if not (user_has_permission(user, "manage_users") or user.is_superuser):
        raise PermissionDenied("You do not have permission to manage users.")


@login_required
def user_list(request):
    _check_manage_users(request.user)
    from apps.accounts.models import User
    users = User.objects.all().prefetch_related("user_roles__role").order_by("username")
    return _page(request, "web/user_list.html", "settings", users_list=users)


@login_required
def user_create(request):
    _check_manage_users(request.user)
    from apps.accounts.models import UserRole

    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()

            roles = form.cleaned_data.get("roles", [])
            for r in roles:
                UserRole.objects.create(user=user, role=r, assigned_by=request.user)

            AuditEvent.objects.create(
                user=request.user,
                action="CREATE",
                resource_type="User",
                resource_id=str(user.id),
                details={
                    "username": user.username,
                    "email": user.email,
                    "roles": [r.name for r in roles],
                },
            )

            messages.success(request, f"User '{user.username}' created successfully.")
            return redirect("/ui/settings/users/")
    else:
        form = UserCreateForm()

    return _page(request, "web/user_form.html", "settings", form=form, is_create=True)


@login_required
def user_edit(request, pk):
    _check_manage_users(request.user)
    from apps.accounts.models import User, UserRole

    target_user = get_object_or_404(User, pk=pk)

    if target_user.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("Only superusers can edit superuser accounts.")

    if request.method == "POST":
        form = UserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            user = form.save()

            # Re-assign roles
            UserRole.objects.filter(user=user).delete()
            roles = form.cleaned_data.get("roles", [])
            for r in roles:
                UserRole.objects.create(user=user, role=r, assigned_by=request.user)

            AuditEvent.objects.create(
                user=request.user,
                action="UPDATE",
                resource_type="User",
                resource_id=str(user.id),
                details={
                    "username": user.username,
                    "is_active": user.is_active,
                    "roles": [r.name for r in roles],
                },
            )

            messages.success(request, f"User '{user.username}' updated successfully.")
            return redirect("/ui/settings/users/")
    else:
        initial_roles = [ur.role for ur in target_user.user_roles.all()]
        form = UserEditForm(instance=target_user, initial={"roles": initial_roles})

    return _page(request, "web/user_form.html", "settings", form=form, is_create=False, target_user=target_user)


@login_required
def user_password_reset(request, pk):
    _check_manage_users(request.user)
    from apps.accounts.models import User

    target_user = get_object_or_404(User, pk=pk)

    if target_user.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("Only superusers can reset superuser passwords.")

    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            target_user.set_password(form.cleaned_data["new_password"])
            target_user.save()

            AuditEvent.objects.create(
                user=request.user,
                action="UPDATE",
                resource_type="User",
                resource_id=str(target_user.id),
                details={"action": "password_reset", "username": target_user.username},
            )

            messages.success(request, f"Password reset for user '{target_user.username}'.")
            return redirect("/ui/settings/users/")
    else:
        form = PasswordResetForm()

    return _page(request, "web/user_password_reset.html", "settings", form=form, target_user=target_user)


@login_required
def user_toggle_active(request, pk):
    _check_manage_users(request.user)
    from apps.accounts.models import User

    target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("/ui/settings/users/")

    if target_user.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("Only superusers can alter active status of superusers.")

    target_user.is_active = not target_user.is_active
    target_user.save()

    status_str = "activated" if target_user.is_active else "deactivated"

    AuditEvent.objects.create(
        user=request.user,
        action="UPDATE",
        resource_type="User",
        resource_id=str(target_user.id),
        details={"action": "toggle_active", "is_active": target_user.is_active, "username": target_user.username},
    )

    messages.success(request, f"User '{target_user.username}' {status_str}.")
    return redirect("/ui/settings/users/")


@login_required
def role_list(request):
    _check_manage_users(request.user)
    from apps.accounts.models import Role
    roles = Role.objects.all().prefetch_related("permissions").order_by("name")
    return _page(request, "web/role_list.html", "settings", roles_list=roles)
