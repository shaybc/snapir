"""Whole-format candidate with declarative original/native comparison metadata."""
from models.native_component_bundle import NativeComponentBundle
from models.unit_checklist_answers import UnitChecklistAnswers
from models.native_verification_binding import NativeVerificationBinding


class NativeFormatComponentBundle(NativeComponentBundle):
    """A format supplies whole-unit parser answers and API recipes, never executable adapters."""
    checklist_answers: UnitChecklistAnswers | None = None
    verification_binding: NativeVerificationBinding | None = None
