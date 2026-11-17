"""Versioned converter evidence for diagnostic views, never conversion acceptance."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversionGraph(BaseModel):
    """Keep recorded facts and their provenance separate from diagram presentation."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['conversion-graph-v1'] = 'conversion-graph-v1'
    run_id: str
    snapshot_id: str = ''
    recorded_at: str = ''
    plan_fingerprint: str | None = None
    nodes: dict[str, dict] = Field(default_factory=dict)
    edges: list[dict] = Field(default_factory=list)
    roots: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)

    @model_validator(mode='after')
    def recorded_references(self):
        """Reject dangling references instead of silently hiding incomplete graph data."""
        if set(self.roots) - set(self.nodes):
            raise ValueError('Graph root has no recorded node')
        for key, node in self.nodes.items():
            if node.get('id') != key or not isinstance(node.get('label'), str):
                raise ValueError('Graph node identity or label is invalid')
        identities = set()
        for edge in self.edges:
            if edge.get('from') not in self.nodes or edge.get('to') not in self.nodes:
                raise ValueError('Graph edge has an unrecorded endpoint')
            if edge.get('id') in identities:
                raise ValueError('Graph edge identity is repeated')
            identities.add(edge.get('id'))
        return self
