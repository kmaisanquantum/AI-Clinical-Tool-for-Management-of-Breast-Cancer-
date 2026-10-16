from django.db import models

from apps.clinical.models import ClinicalValueBase


class ImagingReport(ClinicalValueBase):
    """Imaging report (mammography, breast ultrasound, MRI)."""
    MODALITY_CHOICES = (
        ("mammogram", "Mammogram"),
        ("ultrasound", "Ultrasound"),
        ("mri", "MRI"),
    )
    BIRADS_CHOICES = (
        ("0", "BI-RADS 0 (Incomplete)"),
        ("1", "BI-RADS 1 (Negative)"),
        ("2", "BI-RADS 2 (Benign)"),
        ("3", "BI-RADS 3 (Probably Benign)"),
        ("4", "BI-RADS 4 (Suspicious)"),
        ("4a", "BI-RADS 4a (Low Suspicion)"),
        ("4b", "BI-RADS 4b (Moderate Suspicion)"),
        ("4c", "BI-RADS 4c (High Suspicion)"),
        ("5", "BI-RADS 5 (Highly Suggestive of Malignancy)"),
        ("6", "BI-RADS 6 (Known Biopsy-Proven Malignancy)"),
    )

    encounter = models.ForeignKey(
        "clinical.Encounter",
        on_delete=models.CASCADE,
        related_name="imaging_reports",
    )
    modality = models.CharField(max_length=50, choices=MODALITY_CHOICES, default="ultrasound")
    birads_category = models.CharField(max_length=10, choices=BIRADS_CHOICES, default="0")
    findings = models.TextField(blank=True)
    impression = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ImagingReport({self.modality} BI-RADS {self.birads_category})"


class HistopathologyReport(ClinicalValueBase):
    """Biopsy and pathology result."""
    GRADE_CHOICES = (
        ("1", "Grade 1 (Well differentiated)"),
        ("2", "Grade 2 (Moderately differentiated)"),
        ("3", "Grade 3 (Poorly differentiated)"),
        ("GX", "Grade cannot be assessed"),
    )

    encounter = models.ForeignKey(
        "clinical.Encounter",
        on_delete=models.CASCADE,
        related_name="histopathology_reports",
    )
    specimen_type = models.CharField(max_length=100, default="core_needle_biopsy")
    histological_type = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES, default="GX")
    margin_status = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Histopathology({self.specimen_type} - {self.histological_type})"


class BiomarkerResult(ClinicalValueBase):
    """
    Biomarker status for breast cancer molecular subtyping
    (ER, PR, HER2, Ki-67).
    """
    STATUS_POSITIVE = "positive"
    STATUS_NEGATIVE = "negative"
    STATUS_EQUIVOCAL = "equivocal"
    STATUS_PENDING = "pending"

    MARKER_CHOICES = (
        (STATUS_POSITIVE, "Positive"),
        (STATUS_NEGATIVE, "Negative"),
        (STATUS_EQUIVOCAL, "Equivocal"),
        (STATUS_PENDING, "Pending"),
    )

    HER2_CHOICES = (
        ("0", "0 (Negative)"),
        ("1+", "1+ (Negative)"),
        ("2+", "2+ (Equivocal)"),
        ("3+", "3+ (Positive)"),
        (STATUS_POSITIVE, "Positive"),
        (STATUS_NEGATIVE, "Negative"),
        (STATUS_EQUIVOCAL, "Equivocal"),
        (STATUS_PENDING, "Pending"),
    )

    histopathology_report = models.ForeignKey(
        HistopathologyReport,
        on_delete=models.CASCADE,
        related_name="biomarkers",
    )
    er_status = models.CharField(max_length=20, choices=MARKER_CHOICES, default=STATUS_PENDING)
    pr_status = models.CharField(max_length=20, choices=MARKER_CHOICES, default=STATUS_PENDING)
    her2_status = models.CharField(max_length=20, choices=HER2_CHOICES, default=STATUS_PENDING)
    ki67_index = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    molecular_subtype = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def determine_molecular_subtype(self) -> str:
        """
        Helper method to infer molecular subtype from ER, PR, HER2, Ki-67:
        - Luminal A: ER+, PR+, HER2-, low Ki-67 (<20%)
        - Luminal B: ER+, HER2- with high Ki-67 (>=20%) OR ER+, HER2+
        - HER2-enriched: ER-, PR-, HER2+
        - Triple-negative: ER-, PR-, HER2-
        """
        er_pos = self.er_status == self.STATUS_POSITIVE
        pr_pos = self.pr_status == self.STATUS_POSITIVE
        her2_pos = self.her2_status in (self.STATUS_POSITIVE, "3+")
        her2_neg = self.her2_status in (self.STATUS_NEGATIVE, "0", "1+")

        if er_pos or pr_pos:
            if her2_pos:
                return "Luminal B (HER2-positive)"
            if her2_neg:
                if self.ki67_index is not None and self.ki67_index >= 20:
                    return "Luminal B (HER2-negative)"
                return "Luminal A"
            return "Luminal (HER2-unknown)"
        if not er_pos and not pr_pos and self.er_status == self.STATUS_NEGATIVE and self.pr_status == self.STATUS_NEGATIVE:
            if her2_pos:
                return "HER2-enriched"
            if her2_neg:
                return "Triple-negative"
        return "Unclassified"

    def save(self, *args, **kwargs):
        if not self.molecular_subtype or self.molecular_subtype == "Unclassified":
            subtype = self.determine_molecular_subtype()
            if subtype != "Unclassified":
                self.molecular_subtype = subtype
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Biomarker(ER:{self.er_status}, PR:{self.pr_status}, HER2:{self.her2_status}, Subtype:{self.molecular_subtype})"


class StagingAssessment(ClinicalValueBase):
    """Anatomical TNM staging assessment."""
    T_CHOICES = (("T0", "T0"), ("Tis", "Tis"), ("T1", "T1"), ("T2", "T2"), ("T3", "T3"), ("T4", "T4"), ("TX", "TX"))
    N_CHOICES = (("N0", "N0"), ("N1", "N1"), ("N2", "N2"), ("N3", "N3"), ("NX", "NX"))
    M_CHOICES = (("M0", "M0"), ("M1", "M1"), ("MX", "MX"))
    STAGE_CHOICES = (
        ("0", "Stage 0"),
        ("I", "Stage I"),
        ("IIA", "Stage IIA"),
        ("IIB", "Stage IIB"),
        ("IIIA", "Stage IIIA"),
        ("IIIB", "Stage IIIB"),
        ("IIIC", "Stage IIIC"),
        ("IV", "Stage IV"),
        ("Unknown", "Unknown"),
    )

    encounter = models.ForeignKey(
        "clinical.Encounter",
        on_delete=models.CASCADE,
        related_name="staging_assessments",
    )
    t_stage = models.CharField(max_length=10, choices=T_CHOICES, default="TX")
    n_stage = models.CharField(max_length=10, choices=N_CHOICES, default="NX")
    m_stage = models.CharField(max_length=10, choices=M_CHOICES, default="MX")
    overall_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="Unknown")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Staging({self.t_stage}{self.n_stage}{self.m_stage} - {self.overall_stage})"
