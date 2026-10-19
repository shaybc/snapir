"""Source-backed external resource bindings for one configured Composer unit."""

from pydantic import BaseModel, Field


class ServiceConnection(BaseModel):
    """Keep channel instance identity, driver evidence and ownership separate."""

    connection_id: str
    channel: str
    service_id: str
    service_tag: str = ''
    implementation: str = ''
    connector_id: str = ''
    resource_kind: str = 'external'
    database_type: str | None = None
    driver_class: str | None = None
    driver_dependency: dict | None = None
    driver_candidates: list[dict] = Field(default_factory=list)
    configuration: dict = Field(default_factory=dict)
    connector_configuration: dict = Field(default_factory=dict)
    source_evidence: list[dict] = Field(default_factory=list)
    supporting_sources: list[str] = Field(default_factory=list)
    supporting_hashes: dict[str, str] = Field(default_factory=dict)
    ownership: dict = Field(default_factory=dict)
    conditions: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    fingerprint: str = ''
    decision_id: str = ''
    decision_fingerprint: str = ''

