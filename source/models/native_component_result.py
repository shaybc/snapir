"""Artifact-backed component progress; never whole-unit behavioral acceptance."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NativeComponentResult(BaseModel):
    """The trusted caller must revalidate build/test evidence and every retained file on reuse."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['native-component-result-v1'] = 'native-component-result-v1'
    component_id: str
    contract_revision: str = Field(min_length=1)
    input_revision: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    files: dict[str,str] = Field(min_length=1)
    validation_report: str = Field(min_length=1)
    validation_report_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    validation_scope: Literal['build_and_tests'] = 'build_and_tests'
    status: Literal['component_validated'] = 'component_validated'
    behavioral_equivalence: Literal['not_established'] = 'not_established'
    unit_acceptance_enabled: Literal[False] = False
