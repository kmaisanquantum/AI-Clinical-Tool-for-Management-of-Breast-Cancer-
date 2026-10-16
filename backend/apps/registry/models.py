import uuid
from django.db import models


class Patient(models.Model):
    """
    Pseudonymous patient record.
    Identifiable information (name, MRN, phone, address) is kept strictly separate
    in PatientIdentity table to allow safe analytics and clinical workflows.
    """
    SEX_CHOICES = (
        ("F", "Female"),
        ("M", "Male"),
        ("O", "Other"),
        ("U", "Unknown"),
    )

    pseudonym_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    year_of_birth = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=20, choices=SEX_CHOICES, default="U")
    region = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Patient({self.pseudonym_id})"


class PatientIdentity(models.Model):
    """
    Strictly restricted identifiable patient table.
    Access to this model is controlled by dedicated permission ('view_patient_identity').
    """
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name="identity")
    full_name = models.CharField(max_length=255)
    national_id_or_mrn = models.CharField(max_length=100, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Identity({self.full_name} - {self.national_id_or_mrn})"
