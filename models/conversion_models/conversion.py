from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from models.common_models.common import SnapirBaseModel


class ConversionStatus(str, Enum):
    pending = "pending"
    converting = "converting"
    converted = "converted"
    validated = "validated"
    blocked = "blocked"
    needs_human_review = "needs_human_review"
    failed = "failed"


class BlockingReason(str, Enum):
    unresolved_reference = "unresolved_reference"
    unknown_decorator = "unknown_decorator"
    missing_error_format = "missing_error_format"
    missing_implclass_source = "missing_implclass_source"
    context_cycle = "context_cycle"
    compile_failed = "compile_failed"
    behavior_mismatch = "behavior_mismatch"
    ibm_dependency_found = "ibm_dependency_found"
    equivalence_gap = "equivalence_gap"
    max_retries_exceeded = "max_retries_exceeded"
    needs_human_mapping = "needs_human_mapping"
    upstream_blocked = "upstream_blocked"


class ValidationFailureClass(str, Enum):
    build_failure = "build_failure"
    conversion_gap = "conversion_gap"
    equivalence_gap = "equivalence_gap"
    shared_component_gap = "shared_component_gap"
    routing_mismatch = "routing_mismatch"
    validation_fixture_gap = "validation_fixture_gap"


class ClosureStatus(str, Enum):
    READY = "READY"
    BLOCKED_MISSING_FORMAT = "BLOCKED_MISSING_FORMAT"
    BLOCKED_MISSING_IMPL_CLASS = "BLOCKED_MISSING_IMPL_CLASS"
    BLOCKED_UNKNOWN_TAG = "BLOCKED_UNKNOWN_TAG"
    BLOCKED_UNRESOLVED_REFERENCE = "BLOCKED_UNRESOLVED_REFERENCE"
    NEEDS_HUMAN_MAPPING = "NEEDS_HUMAN_MAPPING"


class ConversionUnit(SnapirBaseModel):
    conversion_id: str
    kind: Literal["ibm_java", "xml_fmtdef", "xml_context", "xml_operation"]
    channel: str
    source_files: list[str] = Field(default_factory=list)
    operation_ids: list[str] = Field(default_factory=list)
    shared: bool
    status: ConversionStatus
    blocking_reason: BlockingReason | None = None
    native_java_path: str | None = None
    source_hash: str
    schema_version: str = "v1"


class ConversionTaskPacket(SnapirBaseModel):
    conversion_id: str
    kind: str
    channel: str
    primary_source_content: str
    supporting_source_contents: dict[str, str] = Field(default_factory=dict)
    channel_filtered_opstep_ids: list[str] | None = None
    return_body_switches: dict[str, str] | None = None
    operation_fields: str | None = None
    ini_values: list[str] | None = None
    service_layer_requirements: list[dict] | None = None
    relationship_context: str
    target_kind: str
    schema_version: str = "v1"


class ExcludedOpStep(SnapirBaseModel):
    id: str
    reason: str


class JavaClassRef(SnapirBaseModel):
    fqcn: str
    source_file: str
    parent_class: str | None = None
    interfaces: list[str] = Field(default_factory=list)
    has_ibm_dependency: bool
    ibm_imports: list[str] = Field(default_factory=list)
    return_codes: dict[str, list[str]] = Field(default_factory=dict)
    shared: bool


class DbLookupRequirement(SnapirBaseModel):
    field_name: str
    from_table: str
    from_column: str
    key_value_field: str


class ClosureBlockingIssue(SnapirBaseModel):
    kind: ClosureStatus
    entity_id: str
    detail: str


class FormatSet(SnapirBaseModel):
    request_format_id: str | None = None
    reply_format_id: str | None = None
    error_reply_format_id: str | None = None
    all_format_ids: list[str] = Field(default_factory=list)
    formatter_tags: list[str] = Field(default_factory=list)
    decorator_chains: dict[str, list] = Field(default_factory=dict)
    transparent_ccxml_nodes: list[str] = Field(default_factory=list)
    db_lookups: list[DbLookupRequirement] = Field(default_factory=list)
    unresolved_format_refs: list[str] = Field(default_factory=list)
    blocking_issues: list[ClosureBlockingIssue] = Field(default_factory=list)


class ContextField(SnapirBaseModel):
    name: str
    context_level: str
    source: Literal["formatter", "implclass"]
    written_by: list[str] = Field(default_factory=list)
    read_by: list[str] = Field(default_factory=list)
    inferred_type: str
    inherited: bool


class OperationClosure(SnapirBaseModel):
    operation_id: str
    channel: str
    run_id: str
    status: ClosureStatus
    blocking_issues: list[ClosureBlockingIssue] = Field(default_factory=list)
    source_xml_path: str
    operation_fields: str | None = None
    ini_values: list[str] = Field(default_factory=list)
    host_key: str | None = None
    ref_formats: dict[str, str] = Field(default_factory=dict)
    return_body_switches: dict[str, str] = Field(default_factory=dict)
    included_opstep_ids: list[str] = Field(default_factory=list)
    excluded_opsteps: list[ExcludedOpStep] = Field(default_factory=list)
    routing_graph: dict[str, dict] = Field(default_factory=dict)
    java_classes: list[JavaClassRef] = Field(default_factory=list)
    formats: FormatSet
    context_id: str
    context_chain: list[str] = Field(default_factory=list)
    context_fields: list[ContextField] = Field(default_factory=list)
    shared_formats: list[str] = Field(default_factory=list)
    shared_java_classes: list[str] = Field(default_factory=list)
    source_hash_composite: str
    schema_version: str = "v1"

    @model_validator(mode="after")
    def ready_closure_has_no_blocking_issues(self) -> "OperationClosure":
        if self.status == ClosureStatus.READY and self.blocking_issues:
            raise ValueError("READY OperationClosure must not have blocking_issues")
        return self


class FieldTransformation(SnapirBaseModel):
    field_name: str
    format_direction: list[str] = Field(default_factory=list)
    unformat_direction: list[str] = Field(default_factory=list)


class ServiceLayerRequirements(SnapirBaseModel):
    format_id: str
    channel: str
    field_transformations: list[FieldTransformation] = Field(default_factory=list)
    db_lookups: list[DbLookupRequirement] = Field(default_factory=list)
    schema_version: str = "v1"


class ContextHierarchy(SnapirBaseModel):
    context_id: str
    chain: list[str] = Field(default_factory=list)
    root_id: str
    has_cycle: bool
    schema_version: str = "v1"


class ContextFieldInventory(SnapirBaseModel):
    context_id: str
    channel: str
    full_chain: list[str] = Field(default_factory=list)
    fields: list[ContextField] = Field(default_factory=list)
    schema_version: str = "v1"


class RoutingStep(SnapirBaseModel):
    step_id: str
    step_index: int
    impl_class: str
    parameters: dict[str, str] = Field(default_factory=dict)
    transitions: dict[str, int | str] = Field(default_factory=dict)
    return_body_switches: dict[str, str] = Field(default_factory=dict)


class RoutingPlan(SnapirBaseModel):
    operation_id: str
    channel: str
    steps: list[RoutingStep] = Field(default_factory=list)
    has_finally_step: bool
    schema_version: str = "v1"


class ContextPlanField(SnapirBaseModel):
    name: str
    java_type: str
    context_level: str
    initialized_from: Literal[
        "request_dto",
        "operation_fields",
        "ini_value",
        "opstep_write",
        "db_lookup",
    ]
    initialized_by: str | None = None


class InitEntry(SnapirBaseModel):
    field_name: str
    source: str
    value_or_expression: str


class ContextPlan(SnapirBaseModel):
    operation_id: str
    channel: str
    context_class: str
    fields: list[ContextPlanField] = Field(default_factory=list)
    init_sequence: list[InitEntry] = Field(default_factory=list)
    schema_version: str = "v1"


class ParseStep(SnapirBaseModel):
    field_name: str
    xml_path: str
    context_field: str
    decorator_chain: list[str] = Field(default_factory=list)
    java_type: str


class BuildStep(SnapirBaseModel):
    field_name: str
    context_field: str
    xml_element: str
    decorator_chain: list[str] = Field(default_factory=list)
    nullable: bool


class SerializationPlan(SnapirBaseModel):
    operation_id: str
    channel: str
    request_parsing: list[ParseStep] = Field(default_factory=list)
    response_building: list[BuildStep] = Field(default_factory=list)
    error_response_building: list[BuildStep] = Field(default_factory=list)
    db_lookups: list[DbLookupRequirement] = Field(default_factory=list)
    schema_version: str = "v1"


class NativeJavaArtifact(SnapirBaseModel):
    conversion_id: str
    artifact_path: str
    artifact_kind: str
    compiles: bool
    review_status: str
    review_notes: list[str] = Field(default_factory=list)
    attempt_number: int
    source_hash: str
    invalidation_event_id: str | None = None
    schema_version: str = "v1"


class ConversionReviewResult(SnapirBaseModel):
    conversion_id: str
    issues: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    review_status: str
    schema_version: str = "v1"


class EquivalenceReviewResult(SnapirBaseModel):
    operation_id: str
    missing_steps: list[str] = Field(default_factory=list)
    missing_rc_branches: list[str] = Field(default_factory=list)
    context_mutation_issues: list[str] = Field(default_factory=list)
    logic_differences: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    review_status: str
    schema_version: str = "v1"
