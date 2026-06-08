# Prompt 01 — All Pydantic Models

## What you are building
You are implementing the complete set of Pydantic data models for the
Composer Sunset migration pipeline. This is Stage 1, Step 1 of the build
order. Every other component depends on these models. Nothing else is built yet.

## Project context
Composer Sunset is an offline ADK multi-agent pipeline that migrates IBM WSBCC
Composer operations to native Java/Spring Boot microservices. It runs on a local
workstation, uses SQLite for state, and calls a local LiteLLM proxy for LLM access.

## Reference documents
Read these before writing any code:
- `Implementation_plan_V8.md` — sections 8 (Data Models), 9 (Failure and Status
  Taxonomy), and the model definitions scattered through sections 2-7.
- `wsbcc_developer_manual_v2.md` — understand WSBCC concepts referenced in models.
- `skills/conversion_rules_skill.md` — conversion rules referenced in models.

## Your task
Create the complete `models/` package. Every model defined in the plan must be
implemented exactly as specified. Do not add models not in the plan.

## Package structure to create

```
models/
├── __init__.py
├── common_models/
│   ├── __init__.py
│   └── common.py
├── composer_models/
│   ├── __init__.py
│   └── composer.py
├── conversion_models/
│   ├── __init__.py
│   └── conversion.py
├── migration_models/
│   ├── __init__.py
│   └── migration.py
├── registry_models/
│   ├── __init__.py
│   └── registry.py
├── java_models/
│   ├── __init__.py
│   └── java.py
├── nodejs_models/
│   ├── __init__.py
│   └── nodejs.py
├── python_models/
│   ├── __init__.py
│   └── python.py
├── deployment_models/
│   ├── __init__.py
│   └── deployment.py
├── validation_models/
│   ├── __init__.py
│   └── validation.py
└── error_models/
    ├── __init__.py
    └── errors.py
```

## Models to implement

### `common_models/common.py`
- `RunMode(str, Enum)` — single_channel, multi_channel, full_inventory
- `TargetLanguage(str, Enum)` — java, nodejs, python
- `RunConfig` — all fields from plan section 3 including `include_operations`,
  `exclude_operations`
- `TaskStatus(str, Enum)` — full enum from plan section 9
- `ProcessLock` — task_id, run_id, process_id, hostname, started_at, heartbeat_at
- `InvalidationEvent` — event_id, run_id, corrected_artifact_id,
  corrected_artifact_kind, change_reason, old_hash, new_hash,
  affected_operation_ids (list[str]), affected_artifact_ids (list[str]),
  created_at, schema_version

### `composer_models/composer.py`
All fields from plan section 8:
- `ComposerOperation` — id, channel, source_file, source_hash, operation_context,
  host_key, operation_fields, write_to_log, write_to_ofec_stat,
  is_selective_journalising, ini_values (list[str]), steps (list[str]),
  ref_formats (dict[str,str]), inline_format_ids (list[str]), conversion_status
- `ComposerOpStep` — id, parent_operation_id, impl_class, source_file,
  source_hash, only_for, transitions (dict[str,str]),
  return_body_switches (dict[str,str]), parameters (dict[str,str]),
  conversion_status
- `ComposerFormat` — id, source_file, source_hash, shared (bool),
  used_by_operations (list[str]), has_serialization_flags (bool),
  serialization_flags (list[str]), database_lookups (list[dict]),
  decorator_chains (dict[str,list]), transparent_ccxml_nodes (list[str]),
  inferred_external_dependencies (list[str]), conversion_status
- `ComposerContext` — id, parent_id, type, source_file, source_hash,
  used_by_operations (list[str]), conversion_status
- `ComposerJavaClass` — fqcn, simple_name, package_name, source_file,
  source_hash, parent_class, interfaces (list[str]), shared (bool),
  used_by_steps (list[str]), behavior_types (list[str]),
  return_codes (dict[str,list[str]]), setter_names (list[str]),
  has_ibm_dependency (bool), ibm_imports (list[str]),
  inferred_external_dependencies (list[str]), conversion_status
- `UnresolvedReference` — kind, ref_id, referenced_from_ids (list[str])

### `conversion_models/conversion.py`
All models from plan sections 8, 9, and the closure/plan sections:
- `ConversionStatus(str, Enum)` — from plan section 9
- `BlockingReason(str, Enum)` — full enum from plan section 9
- `ValidationFailureClass(str, Enum)` — full enum from plan section 9 including
  `routing_mismatch`
- `ClosureStatus(str, Enum)` — READY, BLOCKED_MISSING_FORMAT,
  BLOCKED_MISSING_IMPL_CLASS, BLOCKED_UNKNOWN_TAG,
  BLOCKED_UNRESOLVED_REFERENCE, NEEDS_HUMAN_MAPPING
- `ConversionUnit` — conversion_id, kind, channel, source_files, operation_ids,
  shared, status (ConversionStatus), blocking_reason, native_java_path,
  source_hash, schema_version
- `ConversionTaskPacket` — all fields from plan section 8
- `ExcludedOpStep` — id, reason
- `JavaClassRef` — fqcn, source_file, parent_class, interfaces, has_ibm_dependency,
  ibm_imports, return_codes (dict[str,list[str]]), shared
- `FormatSet` — request_format_id, reply_format_id, error_reply_format_id,
  all_format_ids, formatter_tags, decorator_chains (dict[str,list]),
  transparent_ccxml_nodes, db_lookups (list[DbLookupRequirement]),
  unresolved_format_refs
- `ClosureBlockingIssue` — kind (ClosureStatus), entity_id, detail
- `OperationClosure` — all fields from plan section 5 Phase 2
- `DbLookupRequirement` — field_name, from_table, from_column, key_value_field
- `FieldTransformation` — field_name, format_direction (list[str]),
  unformat_direction (list[str])
- `ServiceLayerRequirements` — format_id, channel, field_transformations,
  db_lookups, schema_version
- `ContextHierarchy` — context_id, chain (list[str]), root_id, has_cycle, schema_version
- `ContextField` — name, context_level, source (Literal["formatter","implclass"]),
  written_by (list[str]), read_by (list[str]), inferred_type, inherited (bool)
- `ContextFieldInventory` — context_id, channel, full_chain (list[str]),
  fields (list[ContextField]), schema_version
- `RoutingStep` — step_id, step_index, impl_class, parameters (dict[str,str]),
  transitions (dict[str,str]), return_body_switches (dict[str,str])
- `RoutingPlan` — operation_id, channel, steps (list[RoutingStep]),
  has_finally_step, schema_version
- `ContextPlanField` — name, java_type, context_level,
  initialized_from (Literal[...]), initialized_by
- `InitEntry` — field_name, source, value_or_expression
- `ContextPlan` — operation_id, channel, context_class, fields, init_sequence,
  schema_version
- `ParseStep` — field_name, xml_path, context_field, decorator_chain (list[str]),
  java_type
- `BuildStep` — field_name, context_field, xml_element,
  decorator_chain (list[str]), nullable
- `SerializationPlan` — operation_id, channel, request_parsing (list[ParseStep]),
  response_building (list[BuildStep]), error_response_building (list[BuildStep]),
  db_lookups (list[DbLookupRequirement]), schema_version
- `NativeJavaArtifact` — conversion_id, artifact_path, artifact_kind,
  compiles (bool), review_status, review_notes (list[str]), attempt_number,
  source_hash, invalidation_event_id
- `ConversionReviewResult` — conversion_id, issues (list[str]),
  confidence (Literal["high","medium","low"]), review_status
- `EquivalenceReviewResult` — operation_id, missing_steps (list[str]),
  missing_rc_branches (list[str]), context_mutation_issues (list[str]),
  logic_differences (list[str]), confidence, review_status

### `validation_models/validation.py`
- `GoldenXmlPair` — operation_id, request_xml, expected_response_xml, scenario
- `XmlDiffResult` — operation_id, scenario, passed (bool), diff_count, diffs (list[str])
- `StubSpec` — operation_id, backend_endpoint, scenarios (list[dict])
- `LogReplayCase` — operation_id, raw_request_xml, expected_response_xml, source_log_ref
- `ValidationPlan` — operation_id, golden_pairs, stub_specs, log_replay_cases
- `ValidationReport` — schema_version, run_id, operation_id, target_language,
  build_passed, test_passed, xml_compat_passed, ibm_guard_passed,
  behavior_equiv_passed, xml_diffs (list[XmlDiffResult]),
  failure_class (ValidationFailureClass | None), attempt_number, evidence_paths
- `ContextAccess` — field_name, value_before, value_after, context_level
- `StepTrace` — step_id, step_index, impl_class, return_code,
  context_reads (list[ContextAccess]), context_writes (list[ContextAccess]),
  next_step_id, routing_rule_used
- `RcMismatch` — step_id, legacy_rc, generated_rc
- `ContextWriteMismatch` — step_id, field_name, legacy_value, generated_value
- `TraceComparisonResult` — matched, step_sequence_match, rc_per_step_match,
  context_writes_match, reply_format_match, final_xml_match,
  step_sequence_diff (list[str]), rc_mismatches, context_write_mismatches,
  reply_format_mismatch, final_xml_diff (list[str]), failure_class
- `ExecutionTrace` — operation_id, channel, scenario, request_xml,
  steps_executed (list[StepTrace]), selected_reply_format, reply_format_switched,
  switch_triggered_by, final_xml, comparison (TraceComparisonResult | None),
  schema_version

### `registry_models/registry.py`
- `SourceArtifactRecord` — artifact_id, kind, logical_id, source_path,
  source_hash, shared, used_by_count, used_by_ids (list[str]), conversion_status
- `GeneratedArtifactRecord` — artifact_id, kind, logical_id, source_path,
  source_hash, target_language, artifact_schema_version, generated_path,
  status (TaskStatus), blocking_reason (BlockingReason | None),
  invalidation_event_id, attempt_number
- `ComponentRegistryRecord` — component_id, artifact_kind, logical_id,
  source_path, source_hash, target_language, artifact_schema_version,
  generated_path, status (ConversionStatus), used_by_operations (list[str]),
  used_by_validated_operations (int)
- `ArtifactReuseDecision` — should_reuse (bool), component_id, generated_path,
  reason

### `migration_models/migration.py`
- `OperationGrouping(str, Enum)` — one_step, multi_step_linear, branch_heavy,
  db_bound, shared_format_context, unusual_manual_review
- `ServiceCandidate` — operation_id, channel, group, target_language,
  estimated_complexity
- `MigrationTaskPacket` — task_id, run_id, operation_id, channel, target_language,
  group, generation_notes (list[str]), status (TaskStatus)
- `MigrationBatch` — batch_id, run_id, task_packets (list[MigrationTaskPacket]),
  is_pilot, status
- `MigrationPlan` — plan_id, run_id, batches (list[MigrationBatch]),
  total_operations, unusual_count, status
- `ManualOperationReviewRecord` — operation_id, review_status, reviewed_by,
  reviewed_at, reason_for_manual_review (list[str]), generation_notes (list[str])

### `java_models/java.py`
- `JavaPackageSpec` — group_id, artifact_id, version, dependencies (list[dict])
- `JavaServiceSpec` — operation_id, service_name, package_spec, main_class,
  port, health_path
- `JavaProjectSpec` — service_spec, src_files (list[str]),
  test_files (list[str]), schema_version
- `JavaBuildSpec` — maven_goals (list[str]), java_version, spring_boot_version
- `JavaBuildResult` — operation_id, target_language, success (bool),
  stdout, stderr, duration_ms

### `deployment_models/deployment.py`
- `DeploymentDefaults` — namespace, replicas, image_pull_policy, container_port,
  cpu_request, cpu_limit, memory_request, memory_limit, liveness_path,
  readiness_path, managed_by_label
- `DeploymentTemplateRef` — platform, template_dir, defaults_path, environment
- `DeploymentSpec` — operation_id, service_name, target_language, image_name,
  port, health_paths (dict), env_vars (dict[str,str]), template_ref, platform
- `RenderedManifest` — operation_id, platform, files (dict[str,str]), validated
- `DeploymentValidationResult` — operation_id, passed, errors, warnings

### `error_models/errors.py`
- `PipelineError` — code, message, task_id, operation_id, recoverable, schema_version
- `BlockedOperation` — operation_id, blocked_by (list[str]), reason
- `HumanReviewItem` — item_id, kind, entity_id, summary,
  evidence_paths (list[str]), required_actions (list[str]),
  blocking_operation_ids (list[str]), schema_version
- `RetryDecision` — task_id, attempt_number, max_retries, should_retry, reason
- `UnsupportedTargetLanguageError(PipelineError)` — target_language
- `ValidationFailureRecord` — failure_class (ValidationFailureClass),
  operation_id, affected_component_ids (list[str]),
  evidence_paths (list[str]), recommended_feedback_target,
  requires_human_review (bool)

## Rules
1. Every durable model (written to SQLite) must have `schema_version: str = "v1"`.
2. Every operation-scoped model must have `operation_id: str`.
3. All enums use lowercase string values except ClosureStatus (uppercase READY etc.).
4. All models must be JSON-serialisable via `model.model_dump()`.
5. Use `datetime` with timezone for all timestamp fields.
6. All list fields default to empty list, all dict fields default to empty dict.
7. All optional string fields default to None.

## Tests to write
Write `tests/test_models.py` covering:
- Instantiation of every model with valid data
- `model_dump()` round-trip for 10 key models
- Enum value rejection for invalid strings on TaskStatus, BlockingReason,
  ValidationFailureClass, ClosureStatus
- Cross-field validation: OperationClosure with status=READY must have empty
  blocking_issues
- RunConfig: include_operations and exclude_operations both None by default
