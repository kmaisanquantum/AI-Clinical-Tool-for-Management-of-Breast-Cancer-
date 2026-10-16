from rest_framework import serializers
from .models import Patient, PatientIdentity


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ("id", "pseudonym_id", "year_of_birth", "sex", "region", "created_at", "updated_at")
        read_only_fields = ("id", "pseudonym_id", "created_at", "updated_at")


class PatientIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientIdentity
        fields = (
            "id",
            "patient",
            "full_name",
            "national_id_or_mrn",
            "date_of_birth",
            "phone_number",
            "address",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
