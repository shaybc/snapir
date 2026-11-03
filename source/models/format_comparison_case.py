"""One directional format fixture and the runtime requirements it exercises."""
from typing import Literal
from pydantic import Field, field_validator
import re
from models.boundary_case import BoundaryCase
from models.format_context_requirement import FormatSourceCitation


class FormatComparisonCase(BoundaryCase):
    """Carry inputs only; expected XML, values and business results are forbidden."""
    binding_id: str
    roundtrip_binding_id: str | None = None
    configuration_attributes: dict[str, str | None] | None = None
    required_inputs: list[str] | None = None
    intentionally_absent: list[str] = Field(default_factory=list)
    origin: Literal['supplied', 'source_backed', 'exploratory', 'regression'] = 'supplied'
    citations: list[FormatSourceCitation] = Field(default_factory=list)
    targeted_branch_ids: list[str] = Field(default_factory=list)
    targeted_branch_outcomes: dict[str, str] = Field(default_factory=dict)

    @field_validator('case_id')
    @classmethod
    def safe_case_directory(cls, value):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', value):
            raise ValueError('Case identity must be a safe bounded directory name')
        return value

