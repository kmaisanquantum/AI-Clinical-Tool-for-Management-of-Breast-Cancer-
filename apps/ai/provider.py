"""
AI abstraction layer for clinical decision support.

OFF BY DEFAULT (AI_ENABLED=False).
This module defines the provider interface for future on-premises model integrations.

CRITICAL PRIVACY/DEPLOYMENT DIRECTIVES:
- Any future AI provider MUST run on-premises within local hospital infrastructure.
- NO patient-identifiable data or clinical data may ever be transmitted to external
  cloud services or third-party APIs.
- When AI_ENABLED is False (default), the NullProvider returns an empty/disabled payload
  and no AI logic is executed in the clinical workflow.
"""

from django.conf import settings


class AIProviderInterface:
    """Base interface for decision-support AI abstraction providers."""

    def assess(self, encounter_context: dict) -> dict:
        raise NotImplementedError("AIProviderInterface subclasses must implement assess()")


class NullProvider(AIProviderInterface):
    """Default no-op provider used when AI_ENABLED is False."""

    def assess(self, encounter_context: dict) -> dict:
        return {"enabled": False, "suggestion": None, "provider_version": "null-v0.1.0"}


class OnPremHeuristicProvider(AIProviderInterface):
    """
    On-premises, deterministic heuristic provider.

    Executes locally without external API or network calls. Composes auditable
    draft suggestions derived directly from fired rules and clinical context.
    """

    def assess(self, encounter_context: dict) -> dict:
        triage_level = encounter_context.get("triage_level", "ROUTINE")
        molecular_subtype = encounter_context.get("molecular_subtype", "Incomplete")

        summary = f"AI Assistive Draft ({triage_level} Triage - {molecular_subtype} Subtype)"
        rationale = "Draft summary generated from deterministic rule evaluation without external network calls."

        considerations = [
            f"Review molecular subtype classification ({molecular_subtype}).",
            "Confirm complete diagnostic imaging and histopathology documentation.",
        ]

        red_flags = []
        if triage_level == "URGENT":
            red_flags.append("Urgent triage level triggered. Expedited MDT and specialist review recommended.")

        return {
            "enabled": True,
            "suggestion": {
                "summary": summary,
                "rationale": rationale,
                "considerations": considerations,
                "red_flags": red_flags,
            },
            "provider_version": "onprem-heuristic-v1.0.0",
        }


def get_ai_provider() -> AIProviderInterface:
    """Factory helper returning the configured AI provider."""
    if getattr(settings, "AI_ENABLED", False):
        return OnPremHeuristicProvider()
    return NullProvider()
