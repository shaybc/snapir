from pydantic import Field

from models.common_models.common import SnapirBaseModel


class ComposerOperation(SnapirBaseModel):
    id: str
    channel: str
    source_file: str
    source_hash: str
    operation_context: str | None = None
    host_key: str | None = None
    operation_fields: str | None = None
    write_to_log: str | None = None
    write_to_ofec_stat: str | None = None
    is_selective_journalising: str | None = None
    ini_values: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    ref_formats: dict[str, str] = Field(default_factory=dict)
    inline_format_ids: list[str] = Field(default_factory=list)
    conversion_status: str


class ComposerOpStep(SnapirBaseModel):
    id: str
    parent_operation_id: str
    impl_class: str | None = None
    source_file: str
    source_hash: str
    only_for: str | None = None
    transitions: dict[str, str] = Field(default_factory=dict)
    return_body_switches: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, str] = Field(default_factory=dict)
    conversion_status: str


class ComposerFormat(SnapirBaseModel):
    id: str
    source_file: str
    source_hash: str
    shared: bool
    used_by_operations: list[str] = Field(default_factory=list)
    has_serialization_flags: bool
    serialization_flags: list[str] = Field(default_factory=list)
    database_lookups: list[dict] = Field(default_factory=list)
    decorator_chains: dict[str, list] = Field(default_factory=dict)
    transparent_ccxml_nodes: list[str] = Field(default_factory=list)
    inferred_external_dependencies: list[str] = Field(default_factory=list)
    conversion_status: str


class ComposerContext(SnapirBaseModel):
    id: str
    parent_id: str | None = None
    type: str
    source_file: str
    source_hash: str
    used_by_operations: list[str] = Field(default_factory=list)
    conversion_status: str


class ComposerJavaClass(SnapirBaseModel):
    fqcn: str
    simple_name: str
    package_name: str
    source_file: str
    source_hash: str
    parent_class: str | None = None
    interfaces: list[str] = Field(default_factory=list)
    shared: bool
    used_by_steps: list[str] = Field(default_factory=list)
    behavior_types: list[str] = Field(default_factory=list)
    return_codes: dict[str, list[str]] = Field(default_factory=dict)
    setter_names: list[str] = Field(default_factory=list)
    has_ibm_dependency: bool
    ibm_imports: list[str] = Field(default_factory=list)
    inferred_external_dependencies: list[str] = Field(default_factory=list)
    conversion_status: str


class UnresolvedReference(SnapirBaseModel):
    kind: str
    ref_id: str
    referenced_from_ids: list[str] = Field(default_factory=list)
