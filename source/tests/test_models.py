from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models.common_models.common import (
    InvalidationEvent,
    ProcessLock,
    RunConfig,
    RunMode,
    TargetLanguage,
    TaskStatus,
)
from models.composer_models.composer import (
    ComposerContext,
    ComposerFormat,
    ComposerJavaClass,
    ComposerOperation,
    ComposerOpStep,
    UnresolvedReference,
)
from models.conversion_models.conversion import (
    BlockingReason,
    BuildStep,
    ClosureBlockingIssue,
    ClosureStatus,
    ContextField,
    ContextFieldInventory,
    ContextHierarchy,
    ContextPlan,
    ContextPlanField,
    ConversionReviewResult,
    ConversionStatus,
    ConversionTaskPacket,
    ConversionUnit,
    DbLookupRequirement,
    EquivalenceReviewResult,
    ExcludedOpStep,
    FieldTransformation,
    FormatSet,
    InitEntry,
    JavaClassRef,
    NativeJavaArtifact,
    OperationClosure,
    ParseStep,
    RoutingPlan,
    RoutingStep,
    SerializationPlan,
    ServiceLayerRequirements,
    ValidationFailureClass,
)
from models.deployment_models.deployment import (
    DeploymentDefaults,
    DeploymentSpec,
    DeploymentTemplateRef,
    DeploymentValidationResult,
    RenderedManifest,
)
from models.error_models.errors import (
    BlockedOperation,
    HumanReviewItem,
    PipelineError,
    RetryDecision,
    UnsupportedTargetLanguageError,
    ValidationFailureRecord,
)
from models.java_models.java import (
    JavaBuildResult,
    JavaBuildSpec,
    JavaPackageSpec,
    JavaProjectSpec,
    JavaServiceSpec,
)
from models.migration_models.migration import (
    ManualOperationReviewRecord,
    MigrationBatch,
    MigrationPlan,
    MigrationTaskPacket,
    OperationGrouping,
    ServiceCandidate,
)
from models.registry_models.registry import (
    ArtifactReuseDecision,
    ComponentRegistryRecord,
    GeneratedArtifactRecord,
    SourceArtifactRecord,
)
from models.validation_models.validation import (
    ContextAccess,
    ContextWriteMismatch,
    ExecutionTrace,
    GoldenXmlPair,
    LogReplayCase,
    RcMismatch,
    StepTrace,
    StubSpec,
    TraceComparisonResult,
    ValidationPlan,
    ValidationReport,
    XmlDiffResult,
)


NOW = datetime(2026, 6, 9, 0, 0, tzinfo=UTC)


def run_config(**overrides):
    data = {
        "run_id": "run-1",
        "run_mode": RunMode.single_channel,
        "source_root": "source",
        "vault_root": "vault",
        "output_root": "out",
        "db_path": "state.db",
        "target_channels": ["INTERNET"],
        "target_languages": [TargetLanguage.java],
        "enable_git": False,
        "artifact_schema_version": "v1",
        "max_agent_task_retries": 3,
        "max_parallel_conversion_workers": 2,
        "max_parallel_llm_tasks": 2,
        "max_parallel_build_tasks": 1,
        "max_operations_per_batch": 10,
        "model_name": "local-model",
        "model_base_url": "http://localhost:4000",
        "auto_rerun_impacted_operations": True,
    }
    data.update(overrides)
    return RunConfig(**data)


def db_lookup():
    return DbLookupRequirement(
        field_name="description",
        from_table="LINK_TYPES",
        from_column="DESCRIPTION",
        key_value_field="link_id",
    )


def context_field():
    return ContextField(
        name="client_id",
        context_level="RequestContext",
        source="formatter",
        inferred_type="String",
        inherited=False,
    )


def java_ref():
    return JavaClassRef(
        fqcn="com.bank.GetClientLinksSP",
        source_file="src/GetClientLinksSP.java",
        has_ibm_dependency=True,
        return_codes={"0": ["success"]},
        shared=False,
    )


def format_set():
    return FormatSet(
        request_format_id="RequestFmt",
        reply_format_id="ReplyFmt",
        all_format_ids=["RequestFmt", "ReplyFmt"],
        formatter_tags=["CCString"],
        db_lookups=[db_lookup()],
    )


def operation_closure(**overrides):
    data = {
        "operation_id": "GetClientLinks",
        "channel": "INTERNET",
        "run_id": "run-1",
        "status": ClosureStatus.READY,
        "source_xml_path": "operations/GetClientLinks.xml",
        "included_opstep_ids": ["GetClientLinksSP"],
        "java_classes": [java_ref()],
        "formats": format_set(),
        "context_id": "RequestContext",
        "context_chain": ["RequestContext"],
        "context_fields": [context_field()],
        "source_hash_composite": "abc123",
    }
    data.update(overrides)
    return OperationClosure(**data)


def migration_task():
    return MigrationTaskPacket(
        task_id="task-1",
        run_id="run-1",
        operation_id="GetClientLinks",
        channel="INTERNET",
        target_language=TargetLanguage.java,
        group=OperationGrouping.one_step,
        status=TaskStatus.pending,
    )


def java_package():
    return JavaPackageSpec(
        group_id="com.bank",
        artifact_id="get-client-links",
        version="1.0.0",
    )


def deployment_template():
    return DeploymentTemplateRef(
        platform="kubernetes",
        template_dir="templates/k8s",
        defaults_path="templates/defaults.yaml",
        environment="dev",
    )


def golden_pair():
    return GoldenXmlPair(
        operation_id="GetClientLinks",
        request_xml="<request/>",
        expected_response_xml="<response/>",
        scenario="success",
    )


def xml_diff():
    return XmlDiffResult(
        operation_id="GetClientLinks",
        scenario="success",
        passed=True,
        diff_count=0,
    )


def context_access():
    return ContextAccess(field_name="client_id", context_level="RequestContext")


def step_trace():
    return StepTrace(
        step_id="GetClientLinksSP",
        step_index=0,
        impl_class="com.bank.GetClientLinksSP",
        return_code=0,
        context_reads=[context_access()],
        context_writes=[context_access()],
        routing_rule_used="on0Do",
    )


def trace_comparison():
    return TraceComparisonResult(
        matched=True,
        step_sequence_match=True,
        rc_per_step_match=True,
        context_writes_match=True,
        reply_format_match=True,
        final_xml_match=True,
    )


def test_instantiates_every_model_with_valid_data():
    models = [
        run_config(),
        ProcessLock(
            task_id="task-1",
            run_id="run-1",
            process_id=123,
            hostname="host",
            started_at=NOW,
            heartbeat_at=NOW,
        ),
        InvalidationEvent(
            event_id="event-1",
            run_id="run-1",
            corrected_artifact_id="artifact-1",
            corrected_artifact_kind="format",
            change_reason="hash_mismatch",
            old_hash="old",
            new_hash="new",
            created_at=NOW,
        ),
        ComposerOperation(
            id="GetClientLinks",
            channel="INTERNET",
            source_file="operation.xml",
            source_hash="hash",
            conversion_status="pending",
        ),
        ComposerOpStep(
            id="GetClientLinksSP",
            parent_operation_id="GetClientLinks",
            source_file="operation.xml",
            source_hash="hash",
            conversion_status="pending",
        ),
        ComposerFormat(
            id="RequestFmt",
            source_file="format.xml",
            source_hash="hash",
            shared=False,
            has_serialization_flags=False,
            conversion_status="pending",
        ),
        ComposerContext(
            id="RequestContext",
            type="context",
            source_file="context.xml",
            source_hash="hash",
            conversion_status="pending",
        ),
        ComposerJavaClass(
            fqcn="com.bank.GetClientLinksSP",
            simple_name="GetClientLinksSP",
            package_name="com.bank",
            source_file="GetClientLinksSP.java",
            source_hash="hash",
            shared=False,
            has_ibm_dependency=True,
            conversion_status="pending",
        ),
        UnresolvedReference(kind="format", ref_id="MissingFmt"),
        ConversionUnit(
            conversion_id="conv-1",
            kind="ibm_java",
            channel="INTERNET",
            shared=False,
            status=ConversionStatus.pending,
            source_hash="hash",
        ),
        ConversionTaskPacket(
            conversion_id="conv-1",
            kind="ibm_java",
            channel="INTERNET",
            primary_source_content="class Source {}",
            relationship_context="operation GetClientLinks",
            target_kind="native_java",
        ),
        ExcludedOpStep(id="IvrOnly", reason="onlyFor=IVR"),
        java_ref(),
        format_set(),
        ClosureBlockingIssue(
            kind=ClosureStatus.BLOCKED_MISSING_FORMAT,
            entity_id="MissingFmt",
            detail="format not found",
        ),
        operation_closure(),
        db_lookup(),
        FieldTransformation(
            field_name="client_id",
            format_direction=["pad"],
            unformat_direction=["strip"],
        ),
        ServiceLayerRequirements(
            format_id="RequestFmt",
            channel="INTERNET",
            field_transformations=[
                FieldTransformation(
                    field_name="client_id",
                    format_direction=["pad"],
                    unformat_direction=["strip"],
                )
            ],
            db_lookups=[db_lookup()],
        ),
        ContextHierarchy(
            context_id="RequestContext",
            chain=["RequestContext"],
            root_id="RequestContext",
            has_cycle=False,
        ),
        context_field(),
        ContextFieldInventory(
            context_id="RequestContext",
            channel="INTERNET",
            full_chain=["RequestContext"],
            fields=[context_field()],
        ),
        RoutingStep(
            step_id="GetClientLinksSP",
            step_index=0,
            impl_class="com.bank.GetClientLinksSP",
        ),
        RoutingPlan(
            operation_id="GetClientLinks",
            channel="INTERNET",
            steps=[
                RoutingStep(
                    step_id="GetClientLinksSP",
                    step_index=0,
                    impl_class="com.bank.GetClientLinksSP",
                )
            ],
            has_finally_step=False,
        ),
        ContextPlanField(
            name="client_id",
            java_type="String",
            context_level="RequestContext",
            initialized_from="request_dto",
        ),
        InitEntry(field_name="client_id", source="request", value_or_expression="request.clientId"),
        ContextPlan(
            operation_id="GetClientLinks",
            channel="INTERNET",
            context_class="RequestContext",
            fields=[
                ContextPlanField(
                    name="client_id",
                    java_type="String",
                    context_level="RequestContext",
                    initialized_from="request_dto",
                )
            ],
            init_sequence=[
                InitEntry(
                    field_name="client_id",
                    source="request",
                    value_or_expression="request.clientId",
                )
            ],
        ),
        ParseStep(
            field_name="client_id",
            xml_path="/request/clientId",
            context_field="client_id",
            java_type="String",
        ),
        BuildStep(
            field_name="client_id",
            context_field="client_id",
            xml_element="clientId",
            nullable=False,
        ),
        SerializationPlan(
            operation_id="GetClientLinks",
            channel="INTERNET",
            request_parsing=[
                ParseStep(
                    field_name="client_id",
                    xml_path="/request/clientId",
                    context_field="client_id",
                    java_type="String",
                )
            ],
            response_building=[
                BuildStep(
                    field_name="client_id",
                    context_field="client_id",
                    xml_element="clientId",
                    nullable=False,
                )
            ],
            db_lookups=[db_lookup()],
        ),
        NativeJavaArtifact(
            conversion_id="conv-1",
            artifact_path="target/GetClientLinksSP.java",
            artifact_kind="ibm_java",
            compiles=True,
            review_status="approved",
            attempt_number=1,
            source_hash="hash",
        ),
        ConversionReviewResult(
            conversion_id="conv-1",
            confidence="high",
            review_status="approved",
        ),
        EquivalenceReviewResult(
            operation_id="GetClientLinks",
            confidence="high",
            review_status="approved",
        ),
        golden_pair(),
        xml_diff(),
        StubSpec(
            operation_id="GetClientLinks",
            backend_endpoint="/backend/links",
            scenarios=[{"name": "success"}],
        ),
        LogReplayCase(
            operation_id="GetClientLinks",
            raw_request_xml="<request/>",
            expected_response_xml="<response/>",
            source_log_ref="log-1",
        ),
        ValidationPlan(
            operation_id="GetClientLinks",
            golden_pairs=[golden_pair()],
        ),
        ValidationReport(
            run_id="run-1",
            operation_id="GetClientLinks",
            target_language=TargetLanguage.java,
            build_passed=True,
            test_passed=True,
            xml_compat_passed=True,
            ibm_guard_passed=True,
            behavior_equiv_passed=True,
            xml_diffs=[xml_diff()],
            attempt_number=1,
        ),
        context_access(),
        step_trace(),
        RcMismatch(step_id="GetClientLinksSP", legacy_rc=0, generated_rc=4),
        ContextWriteMismatch(
            step_id="GetClientLinksSP",
            field_name="client_id",
            legacy_value="1",
            generated_value="2",
        ),
        trace_comparison(),
        ExecutionTrace(
            operation_id="GetClientLinks",
            channel="INTERNET",
            scenario="success",
            request_xml="<request/>",
            steps_executed=[step_trace()],
            selected_reply_format="ReplyFmt",
            reply_format_switched=False,
            final_xml="<response/>",
            comparison=trace_comparison(),
        ),
        SourceArtifactRecord(
            artifact_id="artifact-1",
            kind="format",
            logical_id="RequestFmt",
            source_path="format.xml",
            source_hash="hash",
            shared=False,
            used_by_count=1,
            conversion_status="pending",
        ),
        GeneratedArtifactRecord(
            artifact_id="artifact-2",
            kind="service",
            logical_id="GetClientLinks",
            source_path="operation.xml",
            source_hash="hash",
            target_language=TargetLanguage.java,
            artifact_schema_version="v1",
            generated_path="generated/GetClientLinks.java",
            status=TaskStatus.pending,
            attempt_number=1,
        ),
        ComponentRegistryRecord(
            component_id="component-1",
            artifact_kind="format",
            logical_id="RequestFmt",
            source_path="format.xml",
            source_hash="hash",
            target_language=TargetLanguage.java,
            artifact_schema_version="v1",
            generated_path="generated/RequestFmt.java",
            status=ConversionStatus.pending,
            used_by_validated_operations=0,
        ),
        ArtifactReuseDecision(
            should_reuse=True,
            component_id="component-1",
            generated_path="generated/RequestFmt.java",
            reason="validated",
        ),
        ServiceCandidate(
            operation_id="GetClientLinks",
            channel="INTERNET",
            group=OperationGrouping.one_step,
            target_language=TargetLanguage.java,
            estimated_complexity=1,
        ),
        migration_task(),
        MigrationBatch(
            batch_id="batch-1",
            run_id="run-1",
            task_packets=[migration_task()],
            is_pilot=True,
            status=TaskStatus.pending,
        ),
        MigrationPlan(
            plan_id="plan-1",
            run_id="run-1",
            batches=[
                MigrationBatch(
                    batch_id="batch-1",
                    run_id="run-1",
                    task_packets=[migration_task()],
                    is_pilot=True,
                    status=TaskStatus.pending,
                )
            ],
            total_operations=1,
            unusual_count=0,
            status=TaskStatus.pending,
        ),
        ManualOperationReviewRecord(
            operation_id="GetClientLinks",
            review_status="approved",
            reviewed_by="reviewer",
            reviewed_at=NOW,
        ),
        java_package(),
        JavaServiceSpec(
            operation_id="GetClientLinks",
            service_name="GetClientLinksService",
            package_spec=java_package(),
            main_class="GetClientLinksApplication",
            port=8080,
            health_path="/actuator/health",
        ),
        JavaProjectSpec(
            service_spec=JavaServiceSpec(
                operation_id="GetClientLinks",
                service_name="GetClientLinksService",
                package_spec=java_package(),
                main_class="GetClientLinksApplication",
                port=8080,
                health_path="/actuator/health",
            )
        ),
        JavaBuildSpec(maven_goals=["test"], java_version="21", spring_boot_version="3.3.0"),
        JavaBuildResult(
            operation_id="GetClientLinks",
            target_language=TargetLanguage.java,
            success=True,
            stdout="ok",
            stderr="",
            duration_ms=100,
        ),
        DeploymentDefaults(
            namespace="default",
            replicas=1,
            image_pull_policy="IfNotPresent",
            container_port=8080,
            cpu_request="100m",
            cpu_limit="500m",
            memory_request="256Mi",
            memory_limit="512Mi",
            liveness_path="/actuator/health/liveness",
            readiness_path="/actuator/health/readiness",
            managed_by_label="snapir",
        ),
        deployment_template(),
        DeploymentSpec(
            operation_id="GetClientLinks",
            service_name="GetClientLinksService",
            target_language=TargetLanguage.java,
            image_name="get-client-links:latest",
            port=8080,
            template_ref=deployment_template(),
            platform="kubernetes",
        ),
        RenderedManifest(
            operation_id="GetClientLinks",
            platform="kubernetes",
            files={"deployment.yaml": "apiVersion: apps/v1"},
            validated=True,
        ),
        DeploymentValidationResult(operation_id="GetClientLinks", passed=True),
        PipelineError(code="E001", message="failed", recoverable=True),
        BlockedOperation(operation_id="GetClientLinks", reason="missing format"),
        HumanReviewItem(
            item_id="review-1",
            kind="operation",
            entity_id="GetClientLinks",
            summary="Needs review",
        ),
        RetryDecision(
            task_id="task-1",
            attempt_number=1,
            max_retries=3,
            should_retry=True,
            reason="transient",
        ),
        UnsupportedTargetLanguageError(
            code="E_LANG",
            message="unsupported",
            recoverable=False,
            target_language=TargetLanguage.nodejs,
        ),
        ValidationFailureRecord(
            failure_class=ValidationFailureClass.routing_mismatch,
            operation_id="GetClientLinks",
            recommended_feedback_target="routing_plan",
            requires_human_review=False,
        ),
    ]

    for model in models:
        assert isinstance(model.model_dump(), dict)


@pytest.mark.parametrize(
    "model",
    [
        run_config(),
        operation_closure(),
        ValidationReport(
            run_id="run-1",
            operation_id="GetClientLinks",
            target_language=TargetLanguage.java,
            build_passed=True,
            test_passed=True,
            xml_compat_passed=True,
            ibm_guard_passed=True,
            behavior_equiv_passed=True,
            attempt_number=1,
        ),
        MigrationPlan(
            plan_id="plan-1",
            run_id="run-1",
            batches=[],
            total_operations=0,
            unusual_count=0,
            status=TaskStatus.pending,
        ),
        GeneratedArtifactRecord(
            artifact_id="artifact-2",
            kind="service",
            logical_id="GetClientLinks",
            source_path="operation.xml",
            source_hash="hash",
            target_language=TargetLanguage.java,
            artifact_schema_version="v1",
            generated_path="generated/GetClientLinks.java",
            status=TaskStatus.pending,
            attempt_number=1,
        ),
        ServiceLayerRequirements(format_id="RequestFmt", channel="INTERNET"),
        RoutingPlan(operation_id="GetClientLinks", channel="INTERNET", has_finally_step=False),
        SerializationPlan(operation_id="GetClientLinks", channel="INTERNET"),
        ExecutionTrace(
            operation_id="GetClientLinks",
            channel="INTERNET",
            scenario="success",
            request_xml="<request/>",
            selected_reply_format="ReplyFmt",
            reply_format_switched=False,
            final_xml="<response/>",
        ),
        PipelineError(code="E001", message="failed", recoverable=True),
    ],
)
def test_model_dump_round_trip_for_key_models(model):
    dumped = model.model_dump(mode="json")
    restored = model.__class__.model_validate(dumped)

    assert restored.model_dump(mode="json") == dumped


@pytest.mark.parametrize(
    ("model_cls", "field_name"),
    [
        (GeneratedArtifactRecord, "status"),
        (ConversionUnit, "blocking_reason"),
        (ValidationReport, "failure_class"),
        (OperationClosure, "status"),
    ],
)
def test_enum_value_rejection(model_cls, field_name):
    valid_data = {
        GeneratedArtifactRecord: {
            "artifact_id": "artifact-2",
            "kind": "service",
            "logical_id": "GetClientLinks",
            "source_path": "operation.xml",
            "source_hash": "hash",
            "target_language": TargetLanguage.java,
            "artifact_schema_version": "v1",
            "generated_path": "generated/GetClientLinks.java",
            "status": TaskStatus.pending,
            "attempt_number": 1,
        },
        ConversionUnit: {
            "conversion_id": "conv-1",
            "kind": "ibm_java",
            "channel": "INTERNET",
            "shared": False,
            "status": ConversionStatus.pending,
            "blocking_reason": BlockingReason.unresolved_reference,
            "source_hash": "hash",
        },
        ValidationReport: {
            "run_id": "run-1",
            "operation_id": "GetClientLinks",
            "target_language": TargetLanguage.java,
            "build_passed": False,
            "test_passed": False,
            "xml_compat_passed": False,
            "ibm_guard_passed": True,
            "behavior_equiv_passed": False,
            "failure_class": ValidationFailureClass.routing_mismatch,
            "attempt_number": 1,
        },
        OperationClosure: operation_closure().model_dump(),
    }[model_cls]

    valid_data[field_name] = "not_a_real_enum_value"

    with pytest.raises(ValidationError):
        model_cls(**valid_data)


def test_operation_closure_ready_requires_empty_blocking_issues():
    with pytest.raises(ValidationError):
        operation_closure(
            blocking_issues=[
                ClosureBlockingIssue(
                    kind=ClosureStatus.BLOCKED_MISSING_FORMAT,
                    entity_id="MissingFmt",
                    detail="format not found",
                )
            ]
        )


def test_run_config_include_and_exclude_operations_default_to_none():
    config = run_config()

    assert config.include_operations is None
    assert config.exclude_operations is None
