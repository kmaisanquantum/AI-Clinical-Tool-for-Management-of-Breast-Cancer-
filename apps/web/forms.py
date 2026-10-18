from django import forms

from apps.clinical.models import Encounter
from apps.decision_support.models import ClinicianReview
from apps.investigations.models import (
    BiomarkerResult,
    HistopathologyReport,
    StagingAssessment,
)
from apps.registry.models import Patient, PatientIdentity


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ("year_of_birth", "sex", "region")
        widgets = {
            "year_of_birth": forms.NumberInput(attrs={"class": "form-control", "min": 1900, "max": 2100}),
            "sex": forms.Select(attrs={"class": "form-control"}),
            "region": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Port Moresby"}),
        }


class PatientIdentityForm(forms.ModelForm):
    class Meta:
        model = PatientIdentity
        fields = ("full_name", "national_id_or_mrn", "date_of_birth", "phone_number", "address")
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "national_id_or_mrn": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. MRN-12345"}),
            "date_of_birth": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class EncounterForm(forms.ModelForm):
    notes = forms.CharField(widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}), required=False)

    class Meta:
        model = Encounter
        fields = ("encounter_type", "encounter_date")
        widgets = {
            "encounter_type": forms.Select(attrs={"class": "form-control"}),
            "encounter_date": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        }


class HistopathologyReportForm(forms.ModelForm):
    class Meta:
        model = HistopathologyReport
        fields = ("specimen_type", "histological_type", "grade", "margin_status", "description")
        widgets = {
            "specimen_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Core needle biopsy"}),
            "histological_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Invasive ductal carcinoma"}),
            "grade": forms.Select(attrs={"class": "form-control"}),
            "margin_status": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class BiomarkerResultForm(forms.ModelForm):
    class Meta:
        model = BiomarkerResult
        fields = ("er_status", "pr_status", "her2_status", "ki67_index")
        widgets = {
            "er_status": forms.Select(attrs={"class": "form-control"}),
            "pr_status": forms.Select(attrs={"class": "form-control"}),
            "her2_status": forms.Select(attrs={"class": "form-control"}),
            "ki67_index": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "e.g. 25.0"}),
        }


class StagingAssessmentForm(forms.ModelForm):
    class Meta:
        model = StagingAssessment
        fields = ("t_stage", "n_stage", "m_stage", "overall_stage")
        widgets = {
            "t_stage": forms.Select(attrs={"class": "form-control"}),
            "n_stage": forms.Select(attrs={"class": "form-control"}),
            "m_stage": forms.Select(attrs={"class": "form-control"}),
            "overall_stage": forms.Select(attrs={"class": "form-control"}),
        }


class ClinicianReviewForm(forms.ModelForm):
    class Meta:
        model = ClinicianReview
        fields = ("agree_with_recommendation", "clinician_action_taken", "notes")
        widgets = {
            "agree_with_recommendation": forms.RadioSelect(choices=[(True, "Agree / Confirm"), (False, "Disagree / Override")]),
            "clinician_action_taken": forms.TextInput(attrs={"class": "form-control", "placeholder": "Action taken..."}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Clinical justification..."}),
        }
