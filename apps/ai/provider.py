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


def get_ai_provider() -> AIProviderInterface:
    """Factory helper returning the configured AI provider."""
    if getattr(settings, "AI_ENABLED", False):
        return NullProvider()
    return NullProvider()
