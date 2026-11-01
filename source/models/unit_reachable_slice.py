"""Conservative method/initialization evidence, separate from behavioral acceptance."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.reachable_code_node import ReachableCodeNode
from models.reachable_call_edge import ReachableCallEdge


class UnitReachableSlice(BaseModel):
    """Unbounded edges and unrun tracing are never represented as verified equivalence."""

    model_config = ConfigDict(extra='forbid')

    status: Literal['analyzed', 'verification_incomplete', 'not_run'] = 'not_run'
    candidate_universe: Literal['supplied_unit_evidence'] = 'supplied_unit_evidence'
    source_manifest_hash: str
    configuration_hash: str
    roots: dict[str, list[str]] = Field(default_factory=dict)
    nodes: list[ReachableCodeNode] = Field(default_factory=list)
    edges: list[ReachableCallEdge] = Field(default_factory=list)
    external_signatures: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    runtime_tracing_status: Literal['not_run'] = 'not_run'
    verification_status: Literal['not_run'] = 'not_run'
    boundary_call_classification: Literal['pending'] = 'pending'
    schema_version: str = 'unit-reachable-slice-v1'
