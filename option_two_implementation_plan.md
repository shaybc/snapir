# Option two implementation plan

Status: implemented as the opt-in `behavior_units` strategy following user approval.
The whole-job CCComplex scope check, approved dependency plan and per-operation
completion workflow below remain pending; they are not covered by this status.
The design authority is [option_two_design.md](C:/GitHub/shaybc/snapir/option_two_design.md).
The existing implementation is preserved at `option1_stable`.

The pending revision's development increments, acceptance checks and proposed
files are in the [staged implementation plan](docs/plans/operation_conversion_workflow_implementation_plan.md).
The requirements below describe runtime behavior, not additional runtime phases.

## Pending revision: operation-call scope and sequential completion

Design authority: [Operation dependencies and approved sequential conversion](option_two_design.md#operation-dependencies-and-approved-sequential-conversion)
and [Calls between Composer operations](docs/operation_calls.md). The following
is required work, not a record of an already completed implementation.

1. **Preflight the entire conversion run inside intake.** Traverse direct and indirect
   CCComplex operation calls before pilot selection or plan approval. Resolve
   explicitly identified out-of-scope/channel targets without guessing. Preserve
   target evidence beyond the requested channel/include/exclude filter. Every
   dependency must be part of the job with conversion evidence or be found in a
   trusted published-service registry, including previous jobs. Display reused
   services and bind their API records to this job. Block on missing evidence,
   ambiguity or absent targets; show their call paths and ask the user to include
   or resolve them. Do not silently expand scope or permit ignored dependencies,
   generated placeholders or null-return substitutes.
2. **Detect cycles and block.** Show the complete cycle with call-site evidence
   and request user resolution. Recalculate after correction; do not force a
   sequence or treat a cycle as an automatic combined conversion unit.
3. **Produce intake's plan and approval handoff.** Calculate waves and an explicit
   operation order after preflight passes. Display the complete scope, direct
   prerequisites, reused services and any pilot. Pilot complexity/grouping rules
   must respect dependency order. Make the plan the final intake output and obtain
   acceptance once for the conversion run before the thin wrapper starts. Reuse
   existing approval machinery with a separately saved run-plan policy, defaulting
   to human review; automatic/skip policy affects only human approval. Persist the
   accepted scope, graph, order, API references and approval evidence; material
   changes require renewed acceptance. Missing dependencies/cycles remain blockers.
4. **Coordinate the existing workflow sequentially.** Add a thin outer operation
   loop in the approved order. Invoke the current conversion workflow for one
   operation through assembly, service generation/packaging, existing tests,
   validation and its four gates. Generate only what that operation requires and
   reuse accepted shared artifacts. Publish its completed API record/checkpoint,
   then invoke the next operation. Reuse existing stage implementations; do not
   copy or invent another conversion, testing, correction or approval pipeline.
   Adapt only the entry points and state integration required to avoid job-wide
   stage barriers. Global inventory and ownership planning may still precede
   execution.
5. **Publish and reuse trusted service contracts.** Keep the database per run and
   add a separate shared registry database per migrated source application, outside
   run folders, for use by all of its channels, modules and future runs. A published
   record contains the source application/operation/channel identity, artifact/API
   revision, route and method, supported media types, input/output structures and
   parameters, errors/outcomes, address
   configuration and completion evidence. Publish a complete registry entry, then
   save its reference and completion checkpoint in the run database before advancing;
   interrupted writes must support recovery. Planned/assembled records remain in
   run state and cannot satisfy readiness. Preserve initial XML support; record
   JSON contracts only when supported. Callers generate HTTP
   clients from the trusted record, not Composer dispatch or copied callee logic.
   Ordinary caller reuse does not repeat the callee's conversion validation, and
   readiness-only changes do not change API identity.
   A trusted published service satisfies that dependency boundary; do not expand
   its internal conversion dependency tree again for a new caller.
6. **Preserve failure and Resume behavior.** A failed operation pauses the
   sequence; later operations do not start. Keep accepted work and resume the
   approved order from its saved checkpoint. Retain existing correction limits,
   gate policies, source/API invalidation and validation requirements. Reuse
   per-operation input/output/error testing; add no separate exhaustive chain
   suite. Mock/runtime-test configuration remains a separate follow-up topic.

Implementation acceptance must demonstrate missing transitive and out-of-scope
dependencies blocking before generation, published-service reuse across jobs,
cycle display/blocking, configured plan approval before execution, and C completing
through API publication before B starts in an A -> B -> C chain. It must also
demonstrate that a failure stops progression and Resume retains completed services. This document
update does not execute that validation or claim the workflow already passes it.

### Shared registry and run-state ownership

There are two database roles, not a third database for snapshots or execution
flow. Run databases continue to own scope, approvals, dependency plans, attempts,
draft interfaces, validation evidence, progress and checkpoints. The shared
database owns successfully converted operation-to-microservice mappings and
their saved callable API definitions. An optional Swagger/OpenAPI link is
additional documentation, not the only persisted contract. Associate URL/port
values or address configuration references with the appropriate environment.

During preflight, each new run looks up dependencies in the same application
registry and records the exact published identity/revision, contract data and
address configuration it uses in its existing run database. These are API-use
snapshot records. Resume preserves those choices instead of silently selecting
the latest contract. Publication makes completed services available to later
jobs without merging old run databases or revalidating the completed target.
Archiving an old run must not remove its shared registry entries.

Implementation acceptance also needs to demonstrate two different runs reusing
the same application registry across channels/modules and retaining their own
API-use records. The physical registry/schema and recovery mechanics remain
implementation work; this documentation change creates no database files.

## Implementation record

The new strategy is dispatched by checkpoints without altering legacy conversion
or six-pass assembly. Internet Transfer opts in; the wizard exposes the strategy
and retains its legacy default for rollout. Existing saved runs are not migrated.

Five focused models define unit evidence, operation data/API and Jackson wire-type
contracts, source bundles, build evidence, and native ownership. The additive
`behavior_snapshots` and `behavior_attempts` tables store categorized contracts,
manifests, reviews, revisions, corrections and ownership. Existing `agent_tasks`
also records task status and clears current errors on acceptance. This consolidates
the proposed separate native-bundle tables; no unused table/module was created.

The runtime package implements bounded source analysis, contract reconciliation,
complete-unit ownership, dependency ordering, candidate staging, schema/API/source
validation, compiler and review corrections, native service-flow generation, and
adapters into the existing service-generation and finalization stages. Composer
knowledge stays centralized and is attached to every new request. The model
converts business behavior; it is not asked to preserve legacy names or categories.

Consumers include compatible discovered uses outside the selected migration.
Whole-format direction/configuration and step configuration determine the initial
identity. Relevant public APIs and recursively referenced contract types determine
final compatibility; unrelated operation DTOs do not prevent sharing. Shared
dependencies are installed before their consumers. Generated helpers remain owned
by their complete bundle; independent helper promotion is a future refinement.
Below threshold, one compatible generation can be published and compiled locally
in each consumer's project; operations do not acquire dependencies on another
microservice just to reuse a local unit. Indirect consumers propagate through the
native dependency graph before final placement. Internally referenced format and
context definitions accompany their owning step's evidence packet.

Candidate projects build outside accepted workspaces. Acceptance requires real
test execution for the files cited by requirement coverage. Source and POM
manifests detect changed accepted artifacts; configured XML is checked against
intake. Review-driven and final-validation corrections have persisted budgets.
Gate reports bind to current contracts, ownership and bundle evidence. Gate Four
still requires explicit runtime/compatibility evidence; compilation is not
reported as legacy equivalence.

Focused offline fixtures cover conversion, sharing, corrections, Resume, gates
and packaging handoff. A real Java 25/Maven fixture runs four Jackson mapping
tests. Read-only bank-demo evidence collection found fourteen configured steps
and three complete formats. No live model migration or saved user run was changed.
The full Internet Transfer pilot remains the next validation step.

Additional focused implementation files are
[contract_identity.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/contract_identity.py),
[revisions.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/revisions.py),
[corrections.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/corrections.py),
[review.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/review.py),
[evidence.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/evidence.py), and
[behavior_evidence_freshness.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/behavior_evidence_freshness.py).
They keep new responsibilities outside legacy modules. Existing closure/inventory,
agent-task, gate, assembly, and finalization modules were reused directly where
their APIs were sufficient, rather than modifying every proposed file below.

This plan follows the revised three-part, configured-behavior-unit approach. It
does not implement the earlier proposal for an unrestricted whole-operation design
agent or require a separate exhaustive analysis of every legacy class.

## 1. Intended change

Keep discovery and operational infrastructure. Replace one-to-one legacy class
conversion with complete-format and configured op-step conversion tasks. Each task
can produce a bundle of native Java types. Connect the bundles using explicit
contracts and ordinary operation control flow.

The result is a Spring service accepting XML initially, with business contracts
independent of transport so JSON can be added later. Jackson performs structural
XML binding. Explicit generated methods perform the established format/decorator
transformations. The business service does not depend on Composer Context or a
generic replacement framework.

## 2. Keep, adapt, and retire from option-two execution

| Existing capability | Treatment | Reason |
|---|---|---|
| Mapper/intake, XML/tag/channel discovery | Keep | Finds original operation evidence |
| Java source graph, hashes and classpath discovery | Keep | Collects supporting sources and detects changes |
| Dependency closure and framework boundaries | Adapt outputs | Readiness of evidence, not a required generated-class list |
| Central embedded Composer knowledge | Keep | Explains execution and transformation semantics |
| Run folders, SQLite state and task APIs | Extend additively | Durable bundle tasks, contracts and Resume |
| Model executor, literal prompts, correction/logging machinery | Reuse | Does not depend on one-to-one conversion |
| Per-run JDK, Maven, dependency management | Reuse | Builds ordinary native artifacts |
| Existing reviewed-library ownership | Adapt | Ownership follows native bundles and contracts |
| Single-public-type response contract | Replace for new task kinds | A unit can generate several source files |
| Original class-name/type-category preservation | Retire for new task kinds | Native outputs need not mirror legacy types |
| Independent context/formatter/decorator class conversion | Retire for new task kinds | These behaviors belong in typed contracts and mappers |
| Six fixed Composer assembly methods | Retire for new task kinds | The service uses direct calls and branches |
| Review gates, reports, deployment/finalization infrastructure | Adapt evidence | Approvals bind to bundles and operation behavior |

Keep option-one modules available for existing runs during rollout. Do not delete
them or silently migrate their generated artifacts. Physical removal is a separate
decision after option two is validated.

## 3. Saved strategy and compatibility

Add `conversion_strategy` with values `legacy_components` and `behavior_units`.
Missing fields in old saved profiles resolve to `legacy_components`.

Initially enable `behavior_units` explicitly for the pilot. After validation, the
new-config wizard can default to it. Do not change an existing run's strategy by
editing a configuration file it no longer reads. A new option-two run captures its
own strategy and evidence snapshot.

Put the strategy dispatcher in a small module. It calls the existing managed
converter/assembly for legacy runs and the new unit runners for option-two runs.
Avoid adding the full new implementation to checkpoints.py or managed_projects.py.

## 4. Discover the operation and build unit inputs

Reuse closure and configured-use inventory to resolve:

- Request, success-response and error-response format definitions.
- Configured op-steps and channel-applicable routing.
- Context fields as evidence of data access, not a class to regenerate.
- Formatter/decorator and op-step implementation sources.
- Relevant recursive helpers and library boundaries.
- Exact XML attributes, source identities and content hashes.

Add a `behavior_unit_builder` that produces:

1. `request_unformat` units for input formats.
2. `response_format` units for success and error formats.
3. `configured_step` units for op-step occurrences.

Each unit has a stable identity, consumer operation/channel, configuration identity,
source references, external contracts and direction. Repeated instances of one Java
class remain separate configured behaviors unless compatible reuse is established.

Keep XML-only contexts and nil-parent normalization. Keep source ambiguity and
freshness checks. A READY evidence closure does not prove that every behavior is
known; unresolved transformation contracts must remain explicit in unit validation.

## 5. Data contracts before implementation

Extract a bounded operation contract from XML and source data accesses before
generating independent units. It includes:

- Request wire fields and business input fields.
- Business values produced and consumed by each step.
- Response/error fields and their sources.
- Method input/output contracts and step outcomes.
- Missing/null/empty distinctions where known.
- External collaborators and allowed API signatures.

The model may help identify dynamic accesses or custom logic, but Snapir validates
the result against evidence and reconciles all units. This is contract extraction,
not permission to invent the entire service architecture.

If types cannot be established, create a focused question or explicit assumption
for review. Do not default everything to String, Object, or a generic context map.
Preserve runtime configuration as explicit parameters when a reusable class needs
it; otherwise bind the configured behavior intentionally.

## 6. Complete-format conversion

Input: format tree, configured attributes, formatter/decorator source and helpers,
relevant embedded semantics, and the approved operation data contract.

Output: a bundle containing Jackson wire models, input or output mapping methods,
justified helpers, dependencies, interface metadata, traceability and tests.

Request units implement:

```text
XML -> Jackson wire object -> native input transformations -> business input
```

Response units implement:

```text
business result -> native output transformations -> Jackson wire object -> XML
```

Preserve correct decorator ordering and conversions from actual evidence. Keep raw
lexical fields where transformations need them. Do not assume decimalPlaces implies
input scaling. Do not recreate a runtime interpreter of Composer tags.

Known structure can be generated deterministically after a normalized mapping
contract exists. The first implementation may use one model task for the bundle;
the split between deterministic model generation and custom transformation
generation is an explicit refinement point, not an already-decided feature.

Unknown roots, namespaces, repeated elements, absent/nil semantics and decorator
behavior need targeted validation. Jackson annotations alone do not enforce all
wire constraints. XSD generation is optional and cannot invent legacy rules.

## 7. Configured op-step conversion

Input: one configured step's XML, implementation and relevant helper source,
agreed inputs/outputs/outcomes, dependencies and semantic evidence.

Output: a native business method/class plus helpers and adapters where justified.
Remove context reads/writes by mapping them to explicit values. Remove framework
inheritance and dispatch. Preserve calculations, integration contracts, side-effect
ordering and error outcomes.

Do not make database or HTTP calls through an invented API. Use agreed collaborator
interfaces, including exact relevant third-party API evidence. The existing JAR
version-discovery open issue remains open; it is not solved by this redesign.

## 8. Bundle response and file acceptance

Define new strict models; retain the legacy response parser for old runs:

- `BehaviorUnitInput`: evidence/configuration/contract references and direction.
- `OperationDataContract`: typed data, flow and outcome contracts.
- `NativeSourceFile`: relative path, package/type identity and Java source.
- `NativeUnitBundle`: sources, Maven dependencies, exposed APIs, requirement
  coverage, test scenarios, evidence and unresolved questions.
- `NativeUnitValidation`: schema, interface, build and behavior results.
- `NativeOwnershipPlan`: accepted bundle owners and consumer contracts.

Generation can return multiple files, but each file must have a safe relative path
inside the designated staging directory. Reject traversal, duplicate outputs,
unplanned overwrites, conflicting types and native-package violations.

Validate each public type in its own file. Do not require its category/name to
match the original class. Check exposed APIs against the accepted contract and
reject undeclared collaborators and retained Composer dependencies.

Stage candidates separately. Publish the accepted bundle manifest only after
required checks pass; a partial write or failed compilation is not an accepted
bundle. Shared-project builds still detect conflicts across accepted bundles.

## 9. Bounded requests and correction

Keep one logical unit while splitting large evidence across analysis requests.
Retain evidence-backed summaries with source hashes. Build a bounded input packet
for final generation. Never silently truncate code or send the full organization
tree. Count the whole request, including instructions and semantic evidence.

Reuse literal instruction delivery, enclosing-fence cleanup and bounded JSON
correction. Generalize new-task parsing to NativeUnitBundle. Include the schema in
the request and require JSON self-checking. Reject unsafe or mixed output.

Correction inputs carry schema errors, interface mismatches, forbidden references,
or compiler/behavior failures. Identify the failing artifact: a project-wide error
in an earlier accepted artifact must not blindly rewrite the current candidate.
If correction needs a contract change, invalidate dependent tasks and return to
review rather than silently modifying accepted interfaces.

Every attempt records unit identity, queue position, input identity and output.
Keep existing console grouping and redacted file diagnostics. Clear stale current
errors on success while retaining attempt history.

## 10. Scheduling, ownership and integration

For the pending operation-call revision, first complete the whole-job scope and
approval steps above. The following steps then execute to completion for one
operation at a time before starting the next operation. They are not separate
job-wide passes through all selected operations.

Schedule by the new data/contract dependency graph, not legacy inheritance:

1. Extract/reconcile operation contracts.
2. Generate wire/data types and collaborator interfaces as required.
3. Generate format mapping bundles and configured step bundles.
4. Validate and confirm local/shared placement.
5. Generate the service flow and thin controller.
6. Build, test and review the full operation.

Propose sharing before generation to avoid conflicting packages and duplicated
types. Confirm it from resulting behavior/API/configuration before acceptance.
Retain `shared_library_min_usage` and `broad_library_usage_threshold`, counting
distinct channel-qualified operation consumers rather than raw references.

The placement unit is a complete configured format definition, with its full
referenced structure/transformations, or a configured op-step behavior unit. Tags,
decorators, and nested format fragments do not receive independent placement
decisions. A nested definition separately referenced as an operation's complete
request/response can form a complete unit for that separate use.

Partition uses by compatible behavior, data/API contracts, format direction, and
configuration before computing consumer counts. Below the minimum threshold,
place locally; at or above it, assign the existing consumer-group shared library;
above the broad threshold, assign the common library. Configuration differences
can share only through an explicit compatible parameter contract; otherwise count
separate groups. Verify the generated bundle still fulfills the planned shared
contract before acceptance. Preserve the existing thresholds and grouping policy;
change their input identities from legacy classes/tags to these complete units.

Reuse Maven library installation/versioning and fingerprint mechanics where their
identities can refer to native bundles. Introduce native ownership keys rather
than pretending a bundle has one original source implementation key.

Service assembly receives accepted contracts, bundle APIs and the original routing
table. It generates ordinary method calls and branches. Preserve return/error-body
semantics without six fixed methods or a generic op-step engine.

## 11. State, Resume and review gates

Reuse agent_tasks with new agent/scope/schema identities. Add tables for operation
contracts, unit evidence, bundle manifests/validation, ownership and attempt history.
Store source references separately when needed to avoid duplicating large evidence.

Fingerprint reuse with strategy, direction, configuration, source hashes, contract
revision, semantic/prompt/schema versions, relevant external dependencies, Java
settings and model settings. Changes invalidate only affected descendants, then
the approvals that bind to them. Never import option-one cached outputs as native
bundle results.

The existing implementation uses seven top-level stages and four gates. Retain
their checks and approval policies; the pending operation-call workflow must
apply required conversion, assembly, packaging and validation checks within each
operation's lifecycle rather than waiting for every selected operation at a
job-wide stage barrier.

The thin wrapper invokes these existing stages and gates rather than duplicating
their implementations. Intake's run-plan approval precedes the wrapper once per
conversion run, using the same decision machinery with a separate saved policy.
All four existing gates then apply per operation with their current numbers and
human/automatic/skip settings. Their reports reference the accepted plan and
current operation scope. All-human settings can require four decisions per
operation in addition to the single run-plan approval. Automatic/skip policy does not
bypass failed technical checks, missing dependencies or cycles. Scope gate reports
and saved decisions to the current operation and gate; retain the existing
content-bound approval behavior and Resume evidence. Pause at a pending/rejected
gate without starting the next operation. Reuse the current approval mechanism;
do not duplicate it for the run-plan handoff. The established responsibilities remain:

- Gate One: selected scope, known boundaries and preliminary contracts/ownership.
- Stage Three: closure, finalized contracts and unit generation.
- Gate Two: accepted unit bundles and final data/API/ownership contracts.
- Stage Five: native operation flow/controller integration.
- Gate Three: complete operation behavior and build evidence.
- Gate Four: delivery and acceptance evidence.

Do not repurpose Gate Two as a mandatory pre-generation design gate from the older
proposal. Material changes to Gate-One-reviewed scope still require reapproval.
Keep established stage labels initially; any label changes need an explicit later
decision applied consistently to reports, console and README.

## 12. Tests and pilot

Use mocked model responses for pipeline tests. Test evidence collection, configured
instances, schema failures, safe bundle writes, interface consistency, invalidation,
retry exhaustion, review fingerprints and strategy compatibility.

Compile disposable candidate bundles with the selected JDK/Maven. Test XML roots,
nesting, attributes, collections, null/empty values, decorators, precision and
conversion failures using established expectations. Test step data/outcome and
integration calls independently, then routing and success/error serialization.

Pilot incrementally: one TransferFunds request format, response/error formats,
one configured op-step, then the remaining steps and operation integration. Demo
stubs must be declared fixtures, not evidence of production behavior. Where runtime
captures are absent, report evidence-based checks without claiming full equivalence.

## Expected files to change:

The list below records the original option-two pipeline buildout. It is not an
instruction to rebuild that converter for the pending operation-call revision.
Limit the revision to dependency preflight/planning, the shared registry, the
sequential coordinator and necessary integration with existing workflow entry
points, gate evidence and run checkpoints. Reuse the existing stage bodies.

### Modify existing files

- [pipeline_configuration.py](C:/GitHub/shaybc/snapir/source/models/pipeline_configuration.py): saved strategy and request-budget settings.
- [configuration_wizard.py](C:/GitHub/shaybc/snapir/source/cli/configuration_wizard.py): strategy selection/defaults during rollout.
- [pipeline_runner.py](C:/GitHub/shaybc/snapir/source/runtime/pipeline_runner.py): initialize strategy-specific state.
- [checkpoints.py](C:/GitHub/shaybc/snapir/source/runtime/checkpoints.py): strategy dispatch and durable new checkpoints.
- [closure_builder_tool.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/closure_builder_tool.py): checked evidence output.
- [conversion_component_set.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/conversion_component_set.py): reusable evidence selection without mandatory output identity.
- [component_inventory.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/component_inventory.py): scoped unit evidence queries.
- [db.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/db.py): additive schema registration.
- [agent_tasks.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/agent_tasks.py): current-error clearing/history integration where existing APIs are insufficient.
- [gate_one_reports.py](C:/GitHub/shaybc/snapir/source/runtime/gate_one_reports.py): strategy-specific scope and preliminary ownership evidence.
- [component_review/evidence.py](C:/GitHub/shaybc/snapir/source/runtime/component_review/evidence.py): bundle evidence adapter.
- [component_review/reviewer.py](C:/GitHub/shaybc/snapir/source/runtime/component_review/reviewer.py): configured-unit behavior review.
- [component_review/gate.py](C:/GitHub/shaybc/snapir/source/runtime/component_review/gate.py): bundle/contract approval and feedback dispatch.
- [operation_assembly/runner.py](C:/GitHub/shaybc/snapir/source/runtime/operation_assembly/runner.py): dispatch new flow assembly, retain old runs.
- [operation_review/evidence.py](C:/GitHub/shaybc/snapir/source/runtime/operation_review/evidence.py): native service and requirement evidence.
- [operation_review/reviewer.py](C:/GitHub/shaybc/snapir/source/runtime/operation_review/reviewer.py): explicit flow and behavior checks.
- [operation_review/gate.py](C:/GitHub/shaybc/snapir/source/runtime/operation_review/gate.py): revised fingerprints and correction routing.
- [service_generation/runner.py](C:/GitHub/shaybc/snapir/source/runtime/service_generation/runner.py): package accepted native service sources.
- [service_generation/project_output.py](C:/GitHub/shaybc/snapir/source/runtime/service_generation/project_output.py): planned endpoint/type checks.
- [service_generation/corrections.py](C:/GitHub/shaybc/snapir/source/runtime/service_generation/corrections.py): target bundle/service correction tasks.
- [finalization/runner.py](C:/GitHub/shaybc/snapir/source/runtime/finalization/runner.py): include bundle manifests and new validation evidence where required.
- [workflow_stages.py](C:/GitHub/shaybc/snapir/source/runtime/workflow_stages.py): map new report/checkpoint names to existing stages.
- [workflow_progress.py](C:/GitHub/shaybc/snapir/source/cli/workflow_progress.py): unit-aware progress and honest stop reasons.
- [README.md](C:/GitHub/shaybc/snapir/README.md) and [running_migrations.md](C:/GitHub/shaybc/snapir/docs/running_migrations.md): updated developer flow and compatibility.
- [internet_transfer.yaml](C:/GitHub/shaybc/snapir/configs/internet_transfer.yaml): explicit pilot strategy after implementation is authorized.

Modify legacy managed_projects/shared-library planning modules only if a small
shared build helper must be exposed; prefer existing build-context APIs and new
bundle ownership modules instead of broad refactoring.

### Create focused models (proposed paths)

- [behavior_unit.py](C:/GitHub/shaybc/snapir/source/models/behavior_unit.py)
- [operation_data_contract.py](C:/GitHub/shaybc/snapir/source/models/operation_data_contract.py)
- [native_unit_bundle.py](C:/GitHub/shaybc/snapir/source/models/native_unit_bundle.py)
- [native_unit_validation.py](C:/GitHub/shaybc/snapir/source/models/native_unit_validation.py)
- [native_ownership_plan.py](C:/GitHub/shaybc/snapir/source/models/native_ownership_plan.py)

### Create input collection and state modules (proposed paths)

- [behavior_unit_builder.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/behavior_unit_builder.py)
- [behavior_unit_usage.py](C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/behavior_unit_usage.py): compatible complete-format/op-step consumer counts and threshold assignments.
- [behavior_units.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/behavior_units.py)
- [native_bundles.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/native_bundles.py)
- [conversion_strategy.py](C:/GitHub/shaybc/snapir/source/runtime/conversion_strategy.py)

### Create conversion runtime package (proposed paths)

- [runner.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/runner.py): orchestration only.
- [contracts.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/contracts.py): extraction/reconciliation.
- [request_context.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/request_context.py): bounded evidence inputs.
- [scheduler.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/scheduler.py): configured-unit task ordering.
- [generation.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/generation.py): model calls and bounded corrections.
- [bundle_output.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/bundle_output.py): candidate paths/staging/acceptance.
- [validation.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/validation.py): schema/interface/build/behavior checks.
- [ownership.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/ownership.py): native local/shared decisions.
- [service_flow.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/service_flow.py): direct operation integration.

### Create prompt modules (proposed paths)

- [contract_extraction.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/contract_extraction.py)
- [format_mapping.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/format_mapping.py)
- [configured_step.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/configured_step.py)
- [service_flow.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/service_flow.py)

Each uses central Composer evidence and schema contracts. Do not duplicate manual
text. Request unformat and response format can share a direction-aware template
while retaining explicit distinct semantics.

### Create meaningful tests (proposed paths)

- [test_behavior_unit_builder.py](C:/GitHub/shaybc/snapir/source/tests/test_behavior_unit_builder.py)
- [test_operation_data_contract.py](C:/GitHub/shaybc/snapir/source/tests/test_operation_data_contract.py)
- [test_format_mapping.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_format_mapping.py)
- [test_configured_step_conversion.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_configured_step_conversion.py)
- [test_native_bundle_output.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_native_bundle_output.py)
- [test_behavior_unit_sharing.py](C:/GitHub/shaybc/snapir/source/tests/test_behavior_unit_sharing.py): complete-unit placement, minimum/broad threshold boundaries, distinct consumer counts, incompatible configurations and direction, and no independent nested-tag assignments.
- [test_behavior_unit_resume.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_behavior_unit_resume.py)
- [test_native_service_flow.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_native_service_flow.py)

Update existing wizard, progress, gates and packaging tests only for changed
contracts. Keep legacy strategy regressions to prevent accidental migration.

## 13. Delivery increments

1. **Strategy/models/state:** additive schemas and old-run compatibility. No model calls.
2. **Unit collection/contracts:** accurate evidence bundles and reviewed connection contracts.
3. **One request format:** Jackson bundle and demonstrated input transformations.
4. **Response formats:** success/error mapping and serialization tests.
5. **One configured step:** native business unit and collaborator contracts.
6. **Remaining steps/integration:** routing, outcomes and error-body flow.
7. **Ownership/reviews/Resume:** accepted bundle manifests, gates and invalidation.
8. **Packaging/pilot completion:** Spring endpoint, build and acceptance evidence.
9. **Broader rollout:** reuse across operations, new-config default and documentation.

Each increment starts with an exact-file edit plan and ends with scoped validation.
Do not begin application changes until the human has refined and approved the
design. The first production-flow proof is a complete request-format bundle, not
an attempted conversion of the whole bank demo.

## 14. Explicit exclusions and refinement points

No changes to mapper compilation/runtime selection, repository settings policy,
live deployment, global Java environment, or user runs are implied. No mass file
deletion, option-one artifact migration, or architecture cleanup is part of this plan.

Before implementation, refine contracts, deterministic-versus-model format work,
evidence budgets, helper sharing, acceptance fixtures and unit ownership review.
These can simplify the plan without changing the three-part goal.

Only this implementation-plan document was created for the current request. The
design document, application source, configs and run state are unchanged.
