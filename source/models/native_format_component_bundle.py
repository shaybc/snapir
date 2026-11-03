"""Whole-format candidate with declarative original/native comparison metadata."""
from models.native_component_bundle import NativeComponentBundle
from models.unit_checklist_answers import UnitChecklistAnswers
from models.native_verification_binding import NativeVerificationBinding
from models.format_metadata_compatibility import discard_internal_chain_metadata
from pydantic import model_validator


class NativeFormatComponentBundle(NativeComponentBundle):
    """A format supplies whole-unit parser answers and API recipes, never executable adapters."""
    checklist_answers: UnitChecklistAnswers | None = None
    verification_binding: NativeVerificationBinding | None = None
    _read_historical_chain_metadata = model_validator(mode='before')(discard_internal_chain_metadata)
