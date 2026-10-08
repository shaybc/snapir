from pydantic import Field

from models.common_models.common import SnapirBaseModel, TargetLanguage
from models.conversion_models.conversion import ValidationFailureClass


class GoldenXmlPair(SnapirBaseModel):
    operation_id: str
    request_xml: str
    expected_response_xml: str
    scenario: str
    schema_version: str = "v1"


class XmlDiffResult(SnapirBaseModel):
    operation_id: str
    scenario: str
    passed: bool
    diff_count: int
    diffs: list[str] = Field(default_factory=list)
    schema_version: str = "v1"


class StubSpec(SnapirBaseModel):
    operation_id: str
    backend_endpoint: str
    scenarios: list[dict] = Field(default_factory=list)
    schema_version: str = "v1"


class LogReplayCase(SnapirBaseModel):
    operation_id: str
    raw_request_xml: str
    expected_response_xml: str
    source_log_ref: str
    schema_version: str = "v1"


class ValidationPlan(SnapirBaseModel):
    operation_id: str
    golden_pairs: list[GoldenXmlPair] = Field(default_factory=list)
    stub_specs: list[StubSpec] = Field(default_factory=list)
    log_replay_cases: list[LogReplayCase] = Field(default_factory=list)
    schema_version: str = "v1"


class ValidationReport(SnapirBaseModel):
    schema_version: str = "v1"
    run_id: str
    operation_id: str
    target_language: TargetLanguage
    build_passed: bool
    test_passed: bool
    xml_compat_passed: bool
    ibm_guard_passed: bool
    behavior_equiv_passed: bool
    xml_diffs: list[XmlDiffResult] = Field(default_factory=list)
    failure_class: ValidationFailureClass | None = None
    attempt_number: int
    evidence_paths: list[str] = Field(default_factory=list)


class ContextAccess(SnapirBaseModel):
    field_name: str
    value_before: str | None = None
    value_after: str | None = None
    context_level: str


class StepTrace(SnapirBaseModel):
    step_id: str
    step_index: int
    impl_class: str
    return_code: int
    context_reads: list[ContextAccess] = Field(default_factory=list)
    context_writes: list[ContextAccess] = Field(default_factory=list)
    next_step_id: str | None = None
    routing_rule_used: str


class RcMismatch(SnapirBaseModel):
    step_id: str
    legacy_rc: int
    generated_rc: int


class ContextWriteMismatch(SnapirBaseModel):
    step_id: str
    field_name: str
    legacy_value: str | None = None
    generated_value: str | None = None


class TraceComparisonResult(SnapirBaseModel):
    matched: bool
    step_sequence_match: bool
    rc_per_step_match: bool
    context_writes_match: bool
    reply_format_match: bool
    final_xml_match: bool
    step_sequence_diff: list[str] = Field(default_factory=list)
    rc_mismatches: list[RcMismatch] = Field(default_factory=list)
    context_write_mismatches: list[ContextWriteMismatch] = Field(default_factory=list)
    reply_format_mismatch: str | None = None
    final_xml_diff: list[str] = Field(default_factory=list)
    failure_class: ValidationFailureClass | None = None


class ExecutionTrace(SnapirBaseModel):
    operation_id: str
    channel: str
    scenario: str
    request_xml: str
    steps_executed: list[StepTrace] = Field(default_factory=list)
    selected_reply_format: str
    reply_format_switched: bool
    switch_triggered_by: str | None = None
    final_xml: str
    comparison: TraceComparisonResult | None = None
    schema_version: str = "v1"
