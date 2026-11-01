"""Versioned opt-in policy for citation-free isolated boundary verification."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator
from models.executable_input_fixture import ExecutableInputFixture
from models.comparison_mutation_settings import ComparisonMutationSettings


class ExecutableVerificationSettings(BaseModel):
    """Keep rollout explicit; coverage gaps never silently become verified behavior."""
    model_config=ConfigDict(extra='forbid')
    mode: Literal['checklist_v1','executable_boundary_v1']='checklist_v1'
    max_cases: int=Field(default=512,ge=1,le=512)
    require_branch_coverage: bool=True
    seed: int=Field(default=1729,ge=-(2**63),le=2**63-1)
    clock_millis: int=Field(default=1704153600000,ge=-(2**63),le=2**63-1)
    random_cases: int=Field(default=12,ge=0,le=64)
    max_domain_values: int=Field(default=32,ge=11,le=128)
    max_case_chars: int=Field(default=131072,ge=256,le=1000000)
    max_collection_items: int=Field(default=8,ge=1,le=64)
    coverage_expansion_rounds: int=Field(default=2,ge=0,le=8)
    coverage_expansion_cases: int=Field(default=16,ge=0,le=128)
    coverage_expansion_batch_size: int=Field(default=4,ge=1,le=16)
    coverage_expansion_seconds: float=Field(default=30,gt=0,le=300)
    comparison_mutations: ComparisonMutationSettings=Field(default_factory=ComparisonMutationSettings)
    fixtures: dict[str,list[ExecutableInputFixture]]=Field(default_factory=dict)
    replays: dict[str,list[dict]]=Field(default_factory=dict)
    schema_version: Literal['executable-verification-policy-v1']='executable-verification-policy-v1'

    @field_validator('replays')
    @classmethod
    def validate_replays(cls,units):
        """Replay values describe controlled dependencies, never boundary expectations."""
        for responses in units.values():ExecutableInputFixture.validate_replays(responses)
        return units
