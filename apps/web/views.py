from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.permissions import user_has_permission


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


@login_required
def dashboard(request):
    return _page(request, "web/dashboard.html", "dashboard")


@login_required
def patients(request):
    return _page(request, "web/patients.html", "patients")


@login_required
def patient_detail(request, pk):
    return _page(request, "web/patient_detail.html", "patients", patient_id=pk)


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
