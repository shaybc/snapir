# ADK Agent Deep Dive

This guide expands the agent roster from `docs/architecture_v3.md`. It gives each agent a practical implementation contract: role, tools, state expectations, and a suggested prompt/instruction.

## Global Rules

- Every durable agent starts with `state_store_tool.get_checkpoint(task_id)` and returns cached output when status is `COMPLETED`.
- Python tools own deterministic work: parsing, file I/O, graph traversal, hashing, DB state, Maven, XML/YAML validation, HTTP calls, and diffs.
- LLM agents own semantic work only: ambiguity resolution, Java generation, behavior extraction, code review, and report synthesis.
- Agents receive explicit task packets. Do not let LLM agents scan the repository freely.
- Generated Java must be native Java/Spring Boot with no IBM WSBCC, WebSphere, WAS, EJB, or `com.ibm` dependencies.
- Parallel agents use slot-scoped state keys, for example `temp:flow_task_0` and `flow_result_0`.
- Suggested task id format: `{run_id}:{agent_name}:{scope_id}:{artifact_schema_version}` or `{run_id}:{agent_name}:{operation_id}:{attempt}`.

## Tool Catalog

| Tool | Primary users | Purpose |
|---|---|---|
| `state_store_tool` | All durable agents | Checkpoints, run state, operation status, task output |
| `xml_parser_tool` | Inventory, dependency, format, semantics | Parse XML operations, opSteps, contexts, formats, tag usage |
| `dse_ini_parser_tool` | DSE inventory | Parse `dse.ini` tag-to-class mappings |
| `cross_validate_tool` | DSE inventory | Detect unmapped/conflicting tags |
| `java_source_scanner_tool` | Java inventory, dependency, semantics, DB repo | Locate classes, setters, execute methods, return codes, DB patterns |
| `dependency_graph_tool` | Dependency, operation flow | Build/query per-operation dependency graphs |
| `component_registry_tool` | Shared conversion, service generation, flow | Enforce artifact immutability and resolve generated paths |
| `tag_semantics_tool` | Tag semantics, operation flow | Store/read tag behavior contracts |
| `read_file_tool` | LLM generators/reviewers | Read only explicit files from task packets |
| `write_file_tool` | LLM generators | Write generated Java/YAML/test artifacts |
| `dependency_check_tool` | Converters, critics, flow | Reject forbidden imports/dependencies |
| `xml_serializer_strategy_tool` | Serializer generator | Convert `fmtDef` XML into deterministic serializer plans |
| `maven_compile_tool` | Compile/build/test | Run Maven compile/install/test |
| `yaml_validator_tool` | Manifest generation | Validate OpenShift/Kubernetes YAML |
| `xml_golden_test_tool` | XML compatibility | Run golden XML request/response tests |
| `behavioral_test_tool` | Behavioral equivalence | Invoke legacy/new service or offline golden fallback |
| `xml_diff_tool` | XML validation | Compare XML byte-level and schema-level output |
| `human_approval_tool` | Approval gates | Pause, present gate report, record operator decision |
| `context_size_guard_tool` | LLM-heavy agents | Reject/split oversized prompts |
| `llm_queue_tool` | LLM-heavy agents | Bound concurrent local LiteLLM calls |
| `AgentTool(...)` | Coordinators | Invoke sub-agents with explicit task packets |

## Phase All

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `RootMigrationOrchestratorAgent` | `SequentialAgent` / no | Owns strict phase order and approval gate placement. It should not inspect artifacts or perform conversion logic. It succeeds only when every downstream phase writes the expected checkpoint and final Phase 6 sign-off is complete. | None directly | Run the pipeline for `run_id={run_id}` in this order: Inventory, Gate 0, Dependency Graph, Shared Components, Gate 2, Common-Lib Build, Tag Semantics, Operation Flow, Gate 3, Spring Boot Service Generation, Validation, Gate 5, Behavioral Equivalence. Do not skip gates. Stop on rejected gates or failed hard gates. |
| `HumanApprovalAgent` | `LlmAgent` / yes | Converts DB state into operator-facing gate summaries. It records `approved`, `rejected`, or `modified` decisions and halts downstream execution when approval is not granted. | `human_approval_tool` | Prepare `gate={gate_id}` approval summary from DB state. Include completed checkpoints, blockers, failures, low-confidence semantic records, and sample artifact paths. Call `human_approval_tool`, persist the decision, and stop downstream execution unless approved. |

## Phase 0 - Inventory

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `InventoryCoordinatorAgent` | `SequentialAgent` / no | Sequences XML inventory, DSE mapping, Java source indexing, and ambiguity resolution. Its output is the Gate 0 inventory package. | None directly | Coordinate Phase 0 for `run_id={run_id}`. Run XML inventory, DSE inventory, Java source inventory, and ambiguity resolution. Produce a Gate 0 summary with operation count, tag count, mapped/unmapped tags, ambiguous files, and blockers. |
| `XmlInventoryToolAgent` | `LlmAgent` thin shell / no on happy path | Calls XML scanning only. It records operation names, source XML paths, tag names, context references, format references, and parser ambiguity diagnostics. | `xml_parser_tool`, `state_store_tool` | `task_id={run_id}:XmlInventoryToolAgent:scan:1`. Check checkpoint. Call `scan_all_xml_operations(composer_root, run_id)`. Persist `inventory_xml_scanned`. Return operation and ambiguity counts. Do not infer semantics. |
| `DseIniInventoryToolAgent` | `LlmAgent` thin shell / no on happy path | Builds the authoritative tag-to-Java map from `dse.ini`. Cross-validation turns unknown or conflicting tag mappings into blocker records before conversion starts. | `dse_ini_parser_tool`, `cross_validate_tool`, `state_store_tool` | `task_id={run_id}:DseIniInventoryToolAgent:dse_ini:1`. Check checkpoint. Parse `dse.ini`, cross-validate discovered XML tags, write `blocker_tags` for missing/conflicting mappings, and persist `inventory_dse_mapped`. |
| `JavaInventoryToolAgent` | `LlmAgent` thin shell / no on happy path | Indexes Java source structurally: class path, imports, setters, `execute()` signatures, return code literals, and likely DB access markers. | `java_source_scanner_tool`, `state_store_tool` | `task_id={run_id}:JavaInventoryToolAgent:java_scan:1`. Check checkpoint. Scan Java source roots and record class names, source paths, setters, execute methods, imports, and return code literals. Persist `inventory_java_scanned`. |
| `InventoryAmbiguityResolverAgent` | `LlmAgent` / yes | Reviews only ambiguous records produced by tools. It may classify edge cases but must mark uncertain cases for human review instead of guessing. | `xml_parser_tool`, `state_store_tool` | Review only ambiguous inventory records in the task packet. Classify each as `resolved`, `needs_human_review`, or `blocker`. Use explicit parser diagnostics and XML snippets only. Persist corrections and unresolved blockers. |

## Phase 1 - Dependency Graph

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `DependencyGraphCoordinatorAgent` | `LlmAgent` coordinator / no | Pages the operation inventory and dispatches one operation dependency task at a time or in safe batches. It does not build graph contents itself. | `state_store_tool`, `AgentTool(OperationDependencyAgent)` | Read operations for `run_id={run_id}`. For each operation, create a task packet with `operation_id`, `source_xml`, DSE mappings, and `run_id`. Dispatch `OperationDependencyAgent`. Set `dependency_graph_done` only after all graph tasks complete. |
| `OperationDependencyAgent` | `LlmAgent` thin shell / no | Creates the source-of-truth dependency graph for one operation: opSteps, formats, context chain, implementation classes, DB-bound classes, and unresolved references. | `xml_parser_tool`, `dependency_graph_tool`, `state_store_tool`, `AgentTool(FormatDependencyAgent)`, `AgentTool(ContextDependencyAgent)`, `AgentTool(JavaImplDependencyAgent)` | `task_id={run_id}:OperationDependencyAgent:{operation_id}:1`. Check checkpoint. Build the operation graph using `dependency_graph_tool`. Delegate format, context, and Java details. Persist `dependency_graph_done` for this operation. |
| `FormatDependencyAgent` | `LlmAgent` thin shell / no | Resolves request/response `refFormat` chains to concrete `fmtDef` files, nested tags, `dataName` values, and serializer-relevant structure. | `xml_parser_tool`, `state_store_tool` | Resolve all format references for `operation_id={operation_id}`. Follow `refFormat` chains across files. Record `fmtDef` ids, nested tags, `dataName` values, source paths, and unresolved references. Do not generate DTOs. |
| `ContextDependencyAgent` | `LlmAgent` thin shell / no | Resolves `operationContext -> context -> parent` chains and records declared/inherited context fields. Semantic reads/writes are left to Phase 2.5. | `xml_parser_tool`, `state_store_tool` | Resolve operation context and parent context chain for `operation_id={operation_id}`. Record context tag names, declared fields, inherited fields, source paths, and unresolved references. Do not infer semantic field usage. |
| `JavaImplDependencyAgent` | `LlmAgent` thin shell / no | Links implementation tags to indexed Java classes and records structural metadata needed by converters and semantic extractors. | `java_source_scanner_tool`, `state_store_tool` | For each `implClass` in `operation_id={operation_id}`, locate source and record source path, setters, execute signature, return code literals, imports, and side-effect/DB markers. Persist structural metadata only. |

## Phase 2 - Shared Component Conversion

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `SharedComponentCoordinatorAgent` | `SequentialAgent` / no | Reads unique components from all graphs, applies hash/schema immutability checks, and dispatches only unconverted artifacts. | `component_registry_tool`, `AgentTool(JavaClassConverterAgent)`, `AgentTool(FormatConverterAgent)`, `AgentTool(ContextConverterAgent)`, `AgentTool(DbRepositoryGeneratorAgent)` | Read unique components for `run_id={run_id}`. Check registry before dispatch. Convert only missing artifacts for `ARTIFACT_SCHEMA_VERSION`. Route implClasses, formats, contexts, serializers, and DB repositories to specialist agents. |
| `JavaClassConverterAgent` | `LlmAgent` / yes | Converts one IBM-dependent implementation class to Java 17, preserving setters, execute behavior, return codes, and context side effects. | `read_file_tool`, `write_file_tool`, `component_registry_tool`, `dependency_check_tool`, `context_size_guard_tool` | Convert the provided WSBCC implClass to native Java 17. Preserve behavior, setter configuration, return codes, and context effects. Remove IBM/WebSphere/WAS/EJB imports. Use only task-packet files. Run dependency check, write output, and register it. |
| `FormatConverterAgent` | `LlmAgent` / yes | Produces a DTO from a `fmtDef`. It must not hand-roll XML structure; exact XML parsing/serialization is delegated. | `read_file_tool`, `write_file_tool`, `xml_parser_tool`, `component_registry_tool`, `AgentTool(XmlSerializerGeneratorAgent)` | Generate a Java DTO for the `fmtDef`. Preserve field meaning and `dataName` to camelCase mapping. Do not implement exact XML rendering in the DTO. Delegate serializer/parser generation and register DTO plus serializer paths. |
| `XmlSerializerGeneratorAgent` | `LlmAgent` / yes | Uses a deterministic serializer plan for exact legacy XML shape: transparent wrappers, lists, dates, numbers, table lookups, and null decorators. | `read_file_tool`, `write_file_tool`, `xml_serializer_strategy_tool`, `dependency_check_tool` | Build a serializer plan from `fmtDef` XML. Generate parser/serializer Java that follows the plan exactly. Do not invent elements. Include XML escaping and parsing. Run dependency check before writing. |
| `ContextConverterAgent` | `LlmAgent` / yes | Creates the strongly typed state carrier used by generated flows. Fields come from request/response formats, context definitions, and tag semantic writes. | `read_file_tool`, `write_file_tool`, `component_registry_tool`, `dependency_check_tool` | Generate a Java context class with fields for request `dataName`, response `dataName`, declared context fields, and tag semantic `context_writes`. Use camelCase names, standard getters/setters, and no IBM imports. |
| `DbRepositoryGeneratorAgent` | `LlmAgent` / yes | Converts DB-bound implClasses into Spring repository interfaces/implementations, normally backed by `JdbcTemplate` or stored procedure calls. | `read_file_tool`, `write_file_tool`, `java_source_scanner_tool`, `component_registry_tool`, `dependency_check_tool` | Generate a Spring repository for the DB-bound implClass. Preserve input parameters, result mapping into context, and return-code semantics. Use constructor injection. Do not instantiate DB clients in operation flows. |
| `ConversionCriticAgent` | `LlmAgent` / yes | Reviews generated code for semantic gaps and architecture violations before compile retry loops proceed. | `dependency_check_tool`, `state_store_tool`, `read_file_tool` | Review the generated artifact against its task packet. Check forbidden dependencies, setter preservation, return-code coverage, context reads/writes, XML shape, repository injection, and imports. Return `APPROVED` only if ready to compile. |
| `ConversionCompileAgent` | `LlmAgent` thin shell / no | Runs Maven compile for one component or operation flow. On success it should set ADK `escalate=True` to exit the loop. | `maven_compile_tool`, `state_store_tool` | Run Maven compile for `module_path={module_path}`. Persist stdout, stderr, exit code, and `checkpoint_type={compile_checkpoint}`. On success set `escalate=True`; on failure return exact diagnostics. |
| `SharedComponentRefinementLoopAgent` | `LoopAgent` / mixed | Wraps `ConversionCriticAgent -> ConversionCompileAgent` for a shared component until approval/compile success or `MAX_LOOP_RETRIES`. | None directly | For the current shared component, run critic then compile. Repeat until compile succeeds and escalation occurs, or `MAX_LOOP_RETRIES` is reached. Persist final diagnostics. |

## Phase 2b - Common-Lib Build

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `CommonLibBuildAgent` | `LlmAgent` thin shell / no | Hard gate. Builds and installs the common-lib JAR. No generated microservice should compile until this passes. | `maven_compile_tool`, `state_store_tool` | `task_id={run_id}:CommonLibBuildAgent:common_lib:1`. Run Maven install on common-lib. Persist `common_lib_built` only on zero-error success. Halt downstream phases and record Maven diagnostics on failure. |

## Phase 2.5 - Tag Semantics

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `TagSemanticsCoordinatorAgent` | `SequentialAgent` / no | Dispatches one semantic extraction task per unique WSBCC tag. Low-confidence tags are accepted only as `NEEDS_REVIEW`. | `state_store_tool`, `AgentTool(TagSemanticExtractorAgent)`, `AgentTool(TagSemanticCriticAgent)` | Read unique tags for `run_id={run_id}`. For each tag, send tag name, Java class, source path, DSE entry, and XML usage examples to extraction and critique. Mark done only when every tag is completed or `NEEDS_REVIEW`. |
| `TagSemanticExtractorAgent` | `LlmAgent` / yes | Extracts a contract with `behavior_type`, inputs, context reads/writes, side effects, return codes, native Java equivalent, and confidence. | `read_file_tool`, `java_source_scanner_tool`, `xml_parser_tool`, `tag_semantics_tool`, `state_store_tool`, `context_size_guard_tool` | Analyze only provided tag source, DSE entry, and XML examples. Produce semantic contract JSON with required fields. If unsure, set confidence low. Store the contract and persist `tag_semantics_extracted`. |
| `TagSemanticCriticAgent` | `LlmAgent` / yes | Prevents weak contracts from contaminating Phase 3. Missing fields, invalid behavior types, or uncertain return codes become `NEEDS_REVIEW`. | `state_store_tool`, `tag_semantics_tool` | Review semantic contract completeness. Verify inputs cover XML attributes, return codes are represented, context reads/writes are plausible, and behavior type is valid. Mark `NEEDS_REVIEW` when confidence is low or required fields are missing. |

## Phase 3 - Operation Flow Conversion

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `OperationBatchDispatcherAgent` | `LlmAgent` coordinator / no | Paginates ready operations into hardware-safe batches no larger than `MAX_PARALLEL_OPERATIONS`. | `state_store_tool`, `AgentTool(OperationBatchAgent)` | Read Phase 3-ready operations. Dispatch batches no larger than `MAX_PARALLEL_OPERATIONS`. Each slot gets a unique task id and temp state key. Persist batch status and delay between batches. |
| `OperationBatchAgent` | `ParallelAgent` / mixed | Runs flow conversion slots concurrently. Its main risk is state collision, so every output key must include the slot index. | None directly | Run one `OperationFlowConverterAgent` per assigned slot. Each slot reads only `temp:flow_task_{slot_index}` and writes only `flow_result_{slot_index}`. Do not share mutable state between slots. |
| `OperationFlowConverterAgent` | `LlmAgent` / yes | Converts one opStep return-code graph into Java switch-on-rc orchestration using generated components and semantic contracts. | `read_file_tool`, `write_file_tool`, `dependency_graph_tool`, `component_registry_tool`, `tag_semantics_tool`, `dependency_check_tool`, `state_store_tool` | Convert `operation_id={operation_id}` into a Java flow class. Query dependency graph and tag semantics for every opStep. Generate switch-on-return-code orchestration using generated components/repositories by constructor injection. Preserve paths, errors, return codes, and context mutations. |
| `OperationRefinementLoopAgent` | `LoopAgent` / mixed | Wraps `ConversionCriticAgent -> ConversionCompileAgent` for an operation flow until success or retry exhaustion. | None directly | For the current operation flow, run critic then compile. Repeat until compile succeeds and escalation occurs, or `MAX_LOOP_RETRIES` is reached. Persist operation-specific failure diagnostics. |

## Phase 4 - Spring Boot Service Generation

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `SpringBootServiceGeneratorAgent` | `SequentialAgent` / no | Sequences controller, service, and OpenShift generation for one operation after flow conversion is approved. | None directly | Generate the service for `operation_id={operation_id}` by running controller, service, and manifest generation. The service must accept legacy XML, execute the flow, and return legacy XML. Persist `service_generated`. |
| `ControllerGeneratorAgent` | `LlmAgent` / yes | Creates a thin `@RestController` that accepts raw legacy XML and delegates to the service layer. | `write_file_tool`, `component_registry_tool`, `dependency_check_tool` | Generate a Spring `@RestController` for `operation_id={operation_id}`. Accept raw legacy XML request body, delegate to the service layer, and return raw legacy XML response. Use constructor injection and no IBM dependencies. |
| `ServiceGeneratorAgent` | `LlmAgent` / yes | Wires deserialization, context creation, flow execution, repository dependencies, and response serialization. | `write_file_tool`, `component_registry_tool`, `dependency_check_tool` | Generate a Spring `@Service` that deserializes request XML into context, calls the flow, and serializes context to exact response XML. Wire components/repositories with constructor injection. |
| `OpenShiftManifestAgent` | `LlmAgent` / yes | Emits deployment-ready OpenShift YAML for each generated service. | `write_file_tool`, `yaml_validator_tool` | Generate Deployment, Service, Route, and ConfigMap YAML for `operation_id={operation_id}` using names, labels, ports, env vars, and resources from the task packet. Validate YAML before writing. |

## Phase 5 - Compile, Test, XML Compatibility

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `ServiceCompileTestAgent` | `LlmAgent` thin shell / no | Runs `mvn test` for one generated service and records diagnostics. | `maven_compile_tool`, `state_store_tool` | `task_id={run_id}:ServiceCompileTestAgent:{operation_id}:1`. Run Maven test for the service module. Persist stdout, stderr, exit code, and `service_tested` on success. Mark operation failed on compile/test failure. |
| `XmlCompatibilityAgent` | `LlmAgent` thin shell / no | Verifies exact legacy XML compatibility before behavioral testing. | `xml_golden_test_tool`, `xml_diff_tool`, `state_store_tool` | Run golden XML compatibility tests for `operation_id={operation_id}`. Compare generated responses against golden legacy XML at byte and schema level. Persist pass only if all comparisons pass; store diff paths on failure. |
| `FinalReviewAgent` | `LlmAgent` / yes | Aggregates the migration state into the report consumed by Gate 5. | `state_store_tool`, `read_file_tool` | Create the `run_id={run_id}` migration review report. Summarize inventory, components, common-lib build, tag semantics quality, flows, services, compile/test results, XML compatibility, blockers, and residual risks. Do not mark migration complete. |

## Phase 6 - Behavioral Equivalence

| Agent | Type / LLM | Deep dive | Tools | Suggested prompt / instruction |
|---|---|---|---|---|
| `BehavioralEquivalenceCoordinatorAgent` | `SequentialAgent` / no | Dispatches runtime equivalence tests after Gate 5. It chooses live legacy endpoint or offline golden fallback based on constants. | None directly | For every operation selected for Phase 6, dispatch `BehavioralEquivalenceAgent`. Use `BEHAVIORAL_TEST_MODE` to choose live legacy endpoint or offline golden fallback. Mark migration complete only after required tests pass or accepted waivers are recorded. |
| `BehavioralEquivalenceAgent` | `LlmAgent` thin shell / no | Sends the same request to legacy and generated services, or uses offline golden response, then compares schema, values, formatting, and exact XML where required. | `behavioral_test_tool`, `xml_diff_tool`, `state_store_tool` | `task_id={run_id}:BehavioralEquivalenceAgent:{operation_id}:1`. Run behavioral equivalence for the operation. Compare legacy/offline response to generated response for schema, values, date/number formatting, and exact XML where required. Persist pass only on full pass and store diff artifacts on failure. |

## Implementation Notes

- `LlmAgent` agents marked as LLM=no should be procedural wrappers around `FunctionTool` calls.
- `component_registry_tool.check_if_converted` should run before any expensive LLM conversion.
- `ConversionCriticAgent` and `ConversionCompileAgent` are intentionally reusable across Phase 2 and Phase 3.
- Low-confidence tag semantics should not block extraction, but must be surfaced at Gate 3 before bulk flow conversion.
