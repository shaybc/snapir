# Component-First Composer Conversion Implementation Plan

Status: CF1–CF7 implemented. CF8's fresh-run tooling is implemented and its live bank-demo acceptance run is in progress; CF8 acceptance is not yet established.

## Short action list

1. Keep each configured OP step separate.
2. Build a dependency graph for format implementations, decorators and utilities.
3. Convert small dependencies before their callers.
4. Give each converted component a stable native interface.
5. Reuse components only when their source, configuration contract and dependencies match.
6. Build configured steps and complete formats using those converted dependencies.
7. Split an oversized format along safe child-format boundaries.
8. Compile and verify the complete assembled unit against its original boundary.
9. Persist component progress so retries do not regenerate unchanged dependencies.
10. Prove the flow on a fresh bank-demo conversion before broader rollout.

## 1. Goal and current behavior

Convert from the bottom up instead of repeatedly asking the model to convert a large
format and all of its supporting implementations in one request. Request partitioning
and final behavioral verification are separate responsibilities.

The current scoped builder already creates one `configured_step` per step occurrence,
plus complete `request_unformat` and `response_format` units. We must preserve that
OP-step separation, rather than introduce another mechanism that bundles several steps.
The missing capability is a dependency graph and conversion lifecycle underneath those
units, especially for reusable formatter implementations, decorators and utilities.

Currently the runner orders complete units primarily by direction and ownership. It
does not first convert their shared low-level implementations. Its dependency payload
can also include previously accepted units that happen to share consumers, rather than
only the dependencies required by the current component. The new path must select
dependencies from explicit graph edges.

The character budget remains 900000 by default. A larger budget helps, but does not
replace component planning. Every actual request must pass the existing full-size check,
including instructions, schema, checklist, original source, examples and dependency APIs.
The new size logs remain the measurement source.

## 2. Two identities: conversion components and verification units

### Conversion component

A bounded piece of native implementation generated independently. Examples:

- A utility used by a formatter or step.
- The behavior implemented by a basic format class, such as `CCString` or `CCDate`.
- A decorator and the supporting methods it requires.
- One configured OP step and its native dependencies.
- A configured child-format subtree when a complete format remains oversized.
- The final format composition code.

An XML tag is a configuration reference to an implementing class. The planner must use
the resolved class/source identity from the scoped closure, not assume a class solely
from a tag name. `fmtDef` remains a definition wrapper; it is not another formatter
implementation to translate.

### Verification unit

The existing complete configured `execute`, `unformat` or `format` boundary. Its original
configuration, source identities, parser checklist and operation occurrence remain intact.

A component can become `component_validated` after its required checks. That status is
progress and permits controlled reuse; it is not the existing unit `accepted` status.
The whole unit becomes accepted only after its complete technical ladder passes.

Do not add utilities or primitive components to the existing 83-unit bank denominator
as if they were extra configured operations. Report component progress separately.

## 3. Build the dependency plan deterministically

Start from each current configured unit and its already-qualified closure. Reuse the
recorded Java dependency graph, parser reachability, superclass/initialization evidence,
format children, decorator ordering and resolved `refFmt` definitions.

Construct graph nodes for the required implementation responsibilities and edges from
each caller to its prerequisites. Classify nodes as utility, primitive format,
decorator, configured step, configured subtree or composition. Type categories organize
the work; real dependency edges determine execution order. A decorator that depends on
a formatter must not be scheduled ahead of that formatter merely because of its category.

Include constructors, static/instance initialization, defaults and inherited behavior.
Distinguish convert-required source from explicit retained libraries and framework types
handled at the original harness boundary. Do not translate every framework base class
into a generic native Composer runtime. Preserve its relevant behavior in concrete
native components without recreating `Context`, `Tag` or dynamic XML execution.

Topologically order the graph. Keep strongly connected dependencies together as one
conversion group when separating them would require unstable circular interfaces.
Resolve XML reference cycles through the existing rules; do not reinterpret a cycle as
permission to duplicate or omit behavior.

Preserve uncertain dependency candidates. An unresolved target remains visible in the
plan; do not silently discard it to make a request smaller. A genuinely unavailable
source or execution adapter remains a reported capability gap.

The plan records node identities, dependency edges, original unit membership, source
selectors/hashes, configuration bindings, proposed conversion groups, request weights,
and why a boundary is considered safe. Do not claim that dependency discovery proves
behavioral equivalence.

## 4. Define native contracts before consumers use a component

For each component, generate or establish its public native interface before converting
its consumers. The contract describes actual parameter/result types, initialization
and runtime configuration inputs, observable effects, exceptions and dependencies.

The model may choose suitable native Java names and DTO layouts. Existing deterministic
checks validate the declarations, type resolution, supported invocation recipes and
prohibited framework/runtime recreation. Freeze a contract revision once consumers use
it. An incompatible correction invalidates those consumers; the model cannot silently
change an already-consumed interface.

Shared components should accept genuinely variable configuration explicitly. If a
translation specializes behavior to a configuration, its reuse identity must include
that configuration. The planner must not assume all instances of the same Java class
are interchangeable.

Do not impose class-specific business rules on the AI. For example, the behavior of
`CCDate` or a nil decorator comes from supplied source and configuration, not from the
planner inventing date patterns or XML output policies.

## 5. Generate small dependencies first

Each request contains:

1. The component's original declarations and relevant initialization/configuration.
2. Required superclass/helper source not yet represented by a validated dependency.
3. The parser-checklist items assigned to this component.
4. Exact interfaces and artifact revisions of its required converted dependencies.
5. Relevant converted dependency source where composition requires implementation
   details, without resending every unrelated file from the dependency artifact.
6. Necessary Composer-manual guidance, native-code instructions, schema and test policy.

Keep original complete evidence on the trusted side for final verification. Do not use
an AI summary to replace source needed to implement the component. Optional summaries
can explain relationships, but cannot remove checklist obligations or decide acceptance.

For a primitive implementation with both format and unformat behavior, explicitly
declare whether the component provides both directions or a direction-specific API.
Do not require the request-unformat consumer to execute every formatting-only helper.
Shared methods remain dependencies of every direction that uses them. Tests and receipts
must state which component entry points were actually checked.

Reuse the current JSON/schema checks, native-package guards, managed Maven build,
executed tests, retry limits and concrete correction feedback. If a component has a
supported original/native comparison boundary, compare it as well. Where that boundary
is not independently executable, record that limitation; passing compilation alone
does not establish its behavior. Final unit comparison remains mandatory.

## 6. Convert one configured OP step

An ordinary step request contains exactly its own:

- OP-step XML attributes and occurrence identity.
- Exit codes and configured transitions, including return-format switches.
- Implementing class and required original initialization/helper evidence.
- Direct native dependency contracts and relevant converted code.

No sibling OP-step implementations belong in that request merely because they are in
the same operation. Each repeated step occurrence keeps its own parameters and role.

The generated step returns the evidenced result or exit code. Operation composition
owns selection of the next occurrence. The step request still receives routing metadata
so it can preserve its outcome contract, but must not independently generate sibling
steps or the operation's execution loop.

Complex calls receive the resolved called-operation contract/client and necessary
dependencies. External HTTP/JDBC/resource calls retain their connection contracts and
controlled side effects; do not replace them with fixed successful return values.
Preserve effective caller-channel behavior, XML fallback and local overrides.

## 7. Compose configured formats from converted components

Build a configured format using already converted primitive formats, decorators and
utilities. Supply original parent structure, field names, order, references,
configuration/defaults, collection semantics and required native dependencies.

The native result remains a business-oriented format implementation or typed mapper.
It must not become a generic engine that reads Composer XML at runtime.

Do not conflate instance setup with reusable class conversion. Different configured
fields may call the same validated primitive implementation while retaining different
parameters. Parent-derived namespace, context, locale or other behavior must be passed
explicitly or included in the configured identity.

Keep the current rules for exact format-ID lookup, last-wins keyed definitions,
indexed collections retaining ordered repeats, decorator order, XML-channel fallback
and local overrides. This feature changes how implementation work is divided, not
Composer semantics.

## 8. Split a format further only when necessary

Measure the complete composition request after attaching its real dependencies. If it
fits, generate it as one composition task. If it does not, choose boundaries among
configured child formats or XML subtrees, bottom up.

A subtree split is safe only when its contract preserves parent-dependent behavior:
context access/writes, XML namespace/prefix ownership, sibling order, collection order,
decorators, error propagation and evaluation/callback order. A child is not automatically
independent merely because it is a nested XML tag.

For example, a root response with `Header`, `Accounts` and `Error` children may become
three configured child components plus a small root composition component. Extract a
typed class for each only where that boundary is justified; do not impose that split
on small formats that already fit.

Keep shared state or tightly coupled callbacks in a common component, or express the
interaction through an explicit native contract. Do not precompute a value if doing so
changes source evaluation order or side effects.

Retain stable source selectors and original parent/occurrence paths on extracted
subtrees. No arbitrary text/line splitting and no silent truncation are allowed.
Bound the partition attempts and require every subdivision to make measurable progress.
An indivisible oversized dependency group remains explicitly incomplete. General
method-level partitioning of an oversized cyclic group is deferred until a real example
requires a separate design; this initial plan does not pretend to solve it automatically.

## 9. Preserve the checklist across parts

Keep the complete original-unit checklist as the trusted master inventory. Create an
ownership/index record linking each item to the component(s) responsible for it.
Shared helper items can be referenced by several consumers; their implementation is
owned by one validated component revision, rather than duplicated into each prompt.

Part requests receive their assigned items and required supporting source. The local
ledger retains the complete inventory, so the final composition request need not resend
all component source and all checklist entries just to prove nothing was forgotten.

Before acceptance, resolve component mapping references into the assembled source tree.
Every item must have a valid implementation citation or an existing supported exclusion.
A component-validation receipt is not a blanket exclusion for its source items.
Mappings may point to dependency files where those files really implement the behavior.
Missing items, stale component revisions or nonexistent citations block acceptance.

## 10. Verify the assembled unit and operation

Compile the complete unit with exact component artifact versions and run its tests.
Run the existing original/native comparison at the whole configured unit's entry point
using the same inputs, runtime settings and controlled external responses.

Compare output XML/values, context writes/removals, exceptions and external-call
observations. Preserve significant prefixes, namespace bindings, ordering and
missing/empty/nil distinctions. Keep source-path coverage and unresolved paths visible.
Partial component tests and passing samples do not prove exhaustive equivalence.

The unit's declared entry API remains separate from infrastructure-component APIs.
Do not add every public method of a reusable formatter to the unit's required executed
entry APIs; formatting and unformatting can have different reachable paths. Component
checks describe their own supported contracts; whole-unit checks retain their current
entry-point scope.

Bind final acceptance to original source/configuration, component contracts and artifact
hashes, full assembled code/tests and retained comparison evidence. Packaging must check
the transitive component manifests as well as the unit's own files. Component mutation
reports remain advisory. Operation assembly continues using accepted configured units
and the existing occurrence-based routing and called-operation ordering.

## 11. Reuse, correction and resume

Use separate state categories for component plans, contracts, generation attempts,
validated component results, composition attempts and final unit acceptance. Reuse
existing state-store primitives; do not relabel `component_validated` as unit acceptance.

A reusable component identity includes resolved original source and hierarchy hashes,
covered direction/entry contracts, relevant configuration specialization, native API
revision, required dependency revisions, target platform and conversion-policy version.
Effective runtime channel/configuration remains an input or part of specialization.

The same class name from different source definitions must not collide. Share a
configuration-neutral component across uses only when its contract explicitly covers
those variations. Do not globally share a configured occurrence just because its label
or implementation class matches another occurrence.

Retry the failing component with exact compiler/test/checklist/boundary feedback.
Reuse unchanged prerequisite results. When a component contract or implementation
changes, invalidate dependent composition/results transitively and preserve unaffected
siblings. Never reuse old unit acceptance solely because its outer source file did
not change.

Provider quota, invalid response JSON, request overflow, implementation mismatch and
unavailable harness capability remain distinct causes. No automatic budget increase,
policy relaxation or stubbed external success is introduced by this design.

## 12. Implementation milestones

CF1–CF7 are implemented: dependency plans, revision-bound state, basic components, individual configured steps, complete format composition, bounded subtree extraction and whole-unit acceptance/resume. The next implementation is **CF8**.

| Milestone | Scoped code work | Exit check |
| --- | --- | --- |
| CF1 — Dependency plan | New component-plan models and deterministic graph/order builder; attach a separate plan to scoped preparation without changing generation. | Fresh bank preparation preserves the same configured-unit IDs/routes; graph includes required helpers/superclasses/decorators and handles cycles deterministically. |
| CF2 — Contracts and state | Component contract/result models, state records and source/configuration-aware reuse keys. | Different source/configuration/contracts cannot reuse a component accidentally; unchanged components can resume without another model call. |
| CF3 — Basic implementations | Bounded generation of utilities, primitive formats and decorators using original code and direct prerequisites. | Real Maven/JUnit checks for representative `CCString`, `CCDate`, mandatory/null conversion and runtime-dependent nil behavior; limitations remain explicit. |
| CF4 — Independent steps | Connect one existing configured-step unit to validated component prerequisites; handle complex/external call contracts separately. | Requests contain no unrelated sibling step code; repeated occurrences retain configuration and exit codes; missing dependencies block their consumers. |
| CF5 — Format composition | Generate complete request/response formats using validated primitive/decorator contracts and relevant converted code. | Request and response formats compile, invoke their actual component implementations and compare successfully at the original configured boundary. |
| CF6 — Oversized subtrees | Add measured, bounded child-format partitioning with stable subtree contracts and parent-derived inputs. | A deliberately low test budget forces multiple parts without losing checklist items or wire behavior; indivisible groups stop explicitly. |
| CF7 — Whole-unit acceptance and resume | Resolve multipart mappings, verify transitive manifests and wire the existing technical ladder/packaging to the assembled unit. | Changed dependency artifacts invalidate acceptance; correction reuses unaffected parts; no partially converted unit can enter operation assembly. |
| CF8 — Fresh end-to-end acceptance | Run actual bank Mapper/conversion through units and operations, collect pilot/size/reuse reports and update documentation. | Report actual accepted/failed/incomplete units and operations, model calls, request weights and reused components; do not call preparation or fixture success end-to-end acceptance. |

Introduce the new path behind an explicit conversion mode while CF1–CF6 are developed.
Preserve the existing mode and its historical receipts. Change the default for new runs
only after CF7–CF8 establish that the new path works; do not silently reinterpret
existing saved runs as component-first runs.

## 13. Expected files to change:

This is the anticipated implementation surface, not permission to rewrite every listed
file. Each milestone should name and change only its required area.

### New focused modules

- [planned_conversion_component.py](C:/GitHub/shaybc/snapir/source/models/planned_conversion_component.py) — component identity, kind, original membership and dependencies; the existing legacy `conversion_component.py` is unchanged.
- [component_conversion_group.py](C:/GitHub/shaybc/snapir/source/models/component_conversion_group.py) — deterministic coordinated cycle groups and prerequisite waves.
- [component_conversion_plan.py](C:/GitHub/shaybc/snapir/source/models/component_conversion_plan.py) — graph, ordered conversion groups and partition reasons.
- [native_component_contract.py](C:/GitHub/shaybc/snapir/source/models/native_component_contract.py) — native component API/configuration/effect contract.
- [native_component_result.py](C:/GitHub/shaybc/snapir/source/models/native_component_result.py) — revision-bound validated result and its explicit verification status.
- [component_graph.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/component_graph.py) — deterministic dependency discovery/grouping over existing evidence.
- [component_java_graph.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/component_java_graph.py) — source-qualified Java prerequisites and conservative candidate handling.
- [component_order.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/component_order.py) — reuse existing iterative SCC ordering for component groups.
- [component_partition.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/component_partition.py) — safe measured format-subtree partitions.
- [component_generation.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/component_generation.py) — thin dependency-first component generation coordinator using current generation/build guards.
- [component_requests.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/component_requests.py) — bounded original-code/dependency payloads.
- [component_composition.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/component_composition.py) — configured format/step composition inputs and assembly checks.
- [component_mappings.py](C:/GitHub/shaybc/snapir/source/tools/behavior_verification/component_mappings.py) — resolve per-part citations against the complete original checklist.
- [conversion_components.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/conversion_components.py) — component state and transitive revision invalidation using existing DB facilities.

### Existing integration points

- [units.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/scoped_workflow/units.py) — retain current units and associate their component plans.
- [unit_evidence.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/scoped_workflow/unit_evidence.py) — reuse existing qualified dependency traversal; add only missing component metadata.
- [payloads.py](C:/GitHub/shaybc/snapir/source/runtime/scoped_native/payloads.py) — carry component plans without changing operation/occurrence bindings.
- [runner.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/runner.py) — invoke the new coordinator in the explicit mode; keep routing/operation ordering intact.
- [verification_units.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/verification_units.py) — generate parts before the final existing verification ladder.
- [verification_request.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/verification_request.py) — component-scoped original evidence and checklist references.
- [verification_ladder.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/verification_ladder.py) — compare the assembled unit with exact component artifacts.
- [verification_state.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/verification_state.py) — bind unit acceptance to transitive component receipts.
- [results.py](C:/GitHub/shaybc/snapir/source/runtime/scoped_native/results.py) — packaging/reuse checks for composed results.
- [fingerprints.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/scoped_reuse/fingerprints.py) — version the new mode and relevant component policy.
- [pipeline_configuration.py](C:/GitHub/shaybc/snapir/source/models/pipeline_configuration.py) — explicit mode selection; preserve existing budgets and policies.
- [configured_step.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/configured_step.py) and [format_mapping.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/format_mapping.py) — component/composition instructions without hardcoded formatter semantics.

The existing Java parser, harness, managed Maven tools and state-store schema helpers
should be reused. Extend them only where a milestone demonstrates a specific missing
capability; no parser/harness rewrite is planned.

### Tests and documentation

- [test_component_graph.py](C:/GitHub/shaybc/snapir/source/tests/test_component_graph.py) — source/configuration identity, ordering, cycles and uncertain edges.
- [test_component_generation.py](C:/GitHub/shaybc/snapir/source/tests/test_component_generation.py) — isolated component contracts, retries and bounded payloads.
- [test_component_composition.py](C:/GitHub/shaybc/snapir/source/tests/test_component_composition.py) — real builds, safe subtree assembly and checksum coverage.
- [test_component_resume.py](C:/GitHub/shaybc/snapir/source/tests/test_component_resume.py) — reuse and transitive invalidation.
- [test_bank_component_conversion.py](C:/GitHub/shaybc/snapir/source/tests/test_bank_component_conversion.py) — bank request/response/step integration using the existing boundary comparator.
- [test_bank_seeded_defects.py](C:/GitHub/shaybc/snapir/source/tests/test_bank_seeded_defects.py) — retain and, where needed, apply existing mandatory/null/padding/nil mutations through composed code.
- [test_verification_pipeline.py](C:/GitHub/shaybc/snapir/source/tests/test_verification_pipeline.py) — final acceptance remains technical and whole-unit.
- [Snapir Behavior Verification Design Plan.md](C:/GitHub/shaybc/snapir/docs/plans/Snapir%20Behavior%20Verification%20Design%20Plan.md) — document composition beneath the existing verification model after implementation.
- [wsbcc_developer_manual_v2.md](C:/GitHub/shaybc/snapir/docs/comp-manual/wsbcc_developer_manual_v2.md) — add only required configuration/ownership clarifications, without changing documented runtime semantics.

## 14. Required regression scenarios

1. Two configured steps with the same implementation but different attributes remain distinct.
2. A simple step never receives unrelated step or operation-wide Java sources.
3. A complex call resolves its qualified target and uses its actual contract.
4. Same-named Java classes with different source hashes do not share native results.
5. One configuration-neutral primitive is reused safely across different field parameters.
6. Format and unformat consumers share helpers without forcing irrelevant methods into each consumer's checks.
7. Runtime-dependent decorator branches preserve channel/application settings.
8. Indexed duplicates/order, keyed replacement and format reference scoping remain unchanged.
9. Namespace/prefix and missing/empty/nil mutations still fail the original/native comparison.
10. A deliberately oversized composite is split and assembled with all checklist items accounted for.
11. A changed child artifact invalidates its parent acceptance, but unchanged siblings are reused.
12. Incomplete parts cannot produce accepted units or operations.
13. Strongly connected dependencies stay together; an oversized indivisible group is reported accurately.
14. Source content is never replaced by an authoritative AI summary or silently truncated to fit.
15. The old conversion mode and existing source-qualified operation identities remain compatible.

## 15. Scope boundaries

This plan does not change Composer Mapper output/schema, Excel generation, Composer
lookup/routing rules, service connection behavior, gate authorization, model quotas,
test-strength policy or deployment behavior. It does not promise exhaustive equivalence
from a finite test corpus. No source changes, conversion restart, commit or push are
performed as part of writing this plan.

## CF1 implementation result — 2026-10-27

Scoped preparation now includes a separate `component_plan` for fresh and cached
operations. Original configured-unit IDs/fingerprints, occurrence configuration,
routes, format collection semantics and native engine inputs remain unchanged.
The plan is metadata only: it enables neither generation nor acceptance and produces
no additional Mapper notes/files. Component contracts, native generation and reuse
are still later milestones.

Java prerequisites come from existing qualified `required_classes` evidence, retaining
superclass/helper dependencies and explicit external policies. Implementation identities
bind source evidence and transitive resolution choices; configured roots retain their
own unit/configuration identity. Exact duplicate origins are deduplicated, while
competing origins preserve all candidates and their prerequisites. Unresolved evidence
blocks proposed prerequisite waves without changing the existing generation gate.
Default step bindings use the same consuming-channel mapping as closure analysis.

The existing iterative SCC algorithm groups cyclic Java dependencies. Format-reference
cycles remain explicitly incomplete instead of being reinterpreted as ready. Method-level
reachability is not recomputed by CF1, and role labels describe configured usage rather
than claiming a new Java inheritance analysis. Original source stays in existing unit
evidence; the graph records references and source character counts, not a complete
generation-request size or a promise that a component fits the budget.

Validation: 51 tests passed, including graph/cycle/source-override/uncertainty checks,
cached-versus-control preparation and native input equality, all existing scoped
workflow/reuse regressions, and a fresh real bank Mapper/intake/preparation flow.
The bank plan has the same 83 units (53 steps and 30 format directions), 366 planning
nodes and no planning issues: 58 Java implementation nodes, 218 configured format
nodes, 7 called-operation contract nodes and the 83 unit roots. These nodes do not
represent new configured verification units or accepted code. The report is saved at
`outputs/cf1-bank-component-plan-20261027.json`; test results are in
`outputs/cf1-final-20261027.log`. No AI conversion or live-run restart was performed.


## CF2 implementation result — 2026-10-27

Component contracts and results now have separate models and additive SQLite records.
Fresh and cached preparation register the current component plan without changing
configured-unit IDs, generation requests, routes or acceptance gates. Contracts are
proposed interfaces, not verified behavior. Cyclic groups register all member contracts
and results together.

Reuse binds the qualified source/configuration plan, native contract, dependency
revisions, Java target and conversion policy. Immutable records retain previous
revisions. Changed prerequisites invalidate their consumers while unrelated components
remain reusable. Missing or changed original Java sources, artifacts, validation reports,
API declarations or recorded metadata reject reuse. Artifact paths must stay within the
output root. Registration respects the caller's outer transaction.

The result status is only `component_validated`, with `validation_scope=build_and_tests`
and `behavioral_equivalence=not_established`. Saving and reusing a result require a trusted
validation callback as well as source/artifact/report checks; metadata alone is insufficient.
Existing configured-unit boundary checks and operation acceptance remain required.
External dependencies and called-operation contracts retain policy-bound prerequisite
identities rather than becoming generated native implementations. Fresh preparation and
existing checkpoint validation remain responsible for current XML/configuration evidence.

Changed implementation files:

- `source/models/native_component_contract.py` and `native_component_result.py`: explicit interface and progress contracts.
- `source/tools/conversion_tools/component_identity.py`: checked plans and reuse identities.
- `source/tools/behavior_verification/component_artifacts.py`: source, path, hash, native API and validation-report checks.
- `source/tools/state_store_tools/component_records.py` and `conversion_components.py`: immutable revisions, atomic groups and transitive invalidation/reuse.
- `source/tools/conversion_tools/scoped_workflow/preparation.py`: passive plan registration.
- `source/tests/test_component_state.py`: state/reuse checks, including a real JVM compile/test fixture; the CF1 cached-control fixture now supplies its valid plan fingerprint.

Component generation, model requests, generation attempts, whole-unit behavior comparison
and operation assembly are unchanged. CF3 will connect generation to these contracts;
CF2 does not claim a live bank-demo conversion or behavioral acceptance.

Validation: the combined component/preparation/reuse regression run passed 64 tests
(`outputs/cf2-integration-20261027.log`). After the final reuse-time invalidation guard,
all 14 focused state checks passed (`outputs/cf2-state-guard-20261027.log`), including
the real JVM fixture. The remaining state fixtures use explicitly synthetic build
evidence to exercise cache integrity and do not establish runtime equivalence.


## CF3 implementation result — 2026-10-27

The explicit `scoped_native_mode: component_first_v1` mode now dispatches through
existing scoped preparation, plan approval and Gate 1 to basic component generation.
The default prepare mode and `behavior_units_v1` flow are unchanged. The CF3 runner
converts only source-qualified Java groups classified as utilities, format leaves or
decorators. Groups containing step implementations or wrappers remain deferred to
CF4/CF5. Strongly connected groups remain indivisible, and missing prerequisites block
their consumers without accepting configured units.

Requests retain complete original group source and parser checklist items from the
component's own consuming units, with source-backed method entry points. Conflicting
parser provenance rejects the request; uncertain paths remain uncertain. Required
native prerequisites supply only direct owned production source, frozen interfaces,
artifact revisions and dependency pins. Transitive production source is supplied to
the build, not indiscriminately attached to the prompt. No AI fact extraction or
source summaries are used. The existing encoder measures instructions, embedded manual
context, schema, source, examples and corrections against the configured character
budget before each model request. An oversized indivisible group is incomplete;
subtree partitioning remains CF6.

The response schema describes component contracts, native Java/tests, dependency pins,
coverage and exact production-source citations for assigned parser items. Contracts
must declare their supplied source entry points and parameterized configuration/runtime
inputs; they cannot specialize a shared primitive to one example's channel or values.
Citations prove presence, not semantic equivalence. Shared native-code, escaping,
compiler/test correction and Java-target instructions are reused. No per-tag business
rules were added to generation.

The canonical managed bundle builder resolves dependencies, compiles and executes tests.
Successful candidates retain original source identities, native source, prerequisite
source, POM, compiled output, Surefire reports, ownership and coverage metadata. CF2
records the contract/result revisions only after fresh disposable Maven/test validation.
Reuse checks source/checkpoint freshness and rebuilds a disposable copy without changing
the retained artifact bytes. Current parser obligations, entry points, analysis-tool hash
and generation policy must also match the retained receipt. Changed or invalid candidates cannot create whole-unit or
operation acceptance.

`component-generation.json` reports component progress separately from the original
configured-unit denominator. The persisted phase stops at
`conversion_components_ready_for_composition` or `conversion_components_incomplete`;
it does not proceed to unit or operation assembly. Unexpected fatal errors retain a
partial report and the `conversion_components_failed` phase.

Changed files and responsibilities:

- `source/models/native_component_bundle.py`: a separate component response schema.
- `source/agents/behavior_conversion/component_generation.py`: generic source-driven component instructions.
- `source/runtime/component_conversion/scope.py`: explicit mode and fresh source/checkpoint guards.
- `source/runtime/component_conversion/requests.py`: exact source/checklist and prerequisite selection, full request budget checks.
- `source/runtime/component_conversion/validation.py`: isolated canonical builds, retained manifests and component state publication.
- `source/runtime/component_conversion/runner.py`: dependency-first basic groups and separate progress reports.
- `source/models/pipeline_configuration.py`: opt-in component mode.
- `source/runtime/scoped_native/runner.py`: dispatch after existing plan/Gate 1 approval.
- `source/runtime/behavior_conversion/generation.py`: scoped component authorization and exact-fingerprint candidate reuse within the existing durable correction loop.
- `source/runtime/workflow_stages.py`: place the new component report in its existing workflow stage.
- `source/tests/test_component_generation.py`: parser/request isolation, bounded requests, guards, negative candidates, actual scoped checkpoints and real Maven/JUnit fixtures.

Limitations remain explicit: independent component invocation adapters and original/native
component comparisons are not implemented by CF3. Full supplied source remains the
behavior authority, but component build/test progress does not prove every original
path correct. Final configured-unit parser checks and original/native output comparison
remain mandatory. Fixture success is not a live AI conversion or full bank-demo acceptance.

Validation: all 15 CF3 checks passed (`outputs/cf3-verified-20261027.log`), including
actual bank Mapper/preparation source-selection checks for `CCString`, `CCDate`,
`CCMandatory`, `CCNullToZero` and `NilDecorator`. The real offline Maven/JUnit candidate
fixture exercises string/date parameters, mandatory/null conversion and nil runtime
conditions, repairs an intentional compiler error and reuses unchanged output without
another model call. It is a deterministic candidate fixture, not live AI acceptance or
an original/native component comparison. Real scoped-vault checks retain human plan
approval and reject stale original sources. All 80 existing component-state/graph,
preparation/reuse, scoped-native safety and request-size regression checks passed
(`outputs/cf3-regression-20261027.log`).


## CF4 implementation result — 2026-10-27

The opt-in `component_first_v1` scoped runner now includes individual configured steps
after the existing plan approval and Gate 1. The direct CF3 `convert_basic_components`
API retains its basic-only default; the scoped dispatcher explicitly enables steps.
Default prepare behavior and the `behavior_units_v1` pipeline remain unchanged.

Reusable step implementing classes first convert as parameterized Java components using
the same source-qualified graph, original source, parser obligations, native prerequisites,
Maven/test checks and revision-bound receipts as CF3. Each configured step occurrence
then receives its own component request and specialized contract. The occurrence wrapper
uses the validated implementation API; it does not replace its business logic or receive
unrelated sibling step source. Shared implementation metadata does not merge occurrence
configuration or change existing unit IDs.

Each occurrence request retains its original unit/fingerprint, operation/source/occurrence
identities, own XML attributes, integer exits/routes and return-body switches, plus its
resolved implementing-class source. Its helper and implementing-class native prerequisites
are required to be `component_validated` first. Only direct owned production source/APIs
enter the prompt; transitive source goes to the build. Missing or changed prerequisites
block their consumers. Source evidence and parser items remain complete for their assigned
owner; no AI source summary or AI fact extraction was introduced.

Native configured steps declare a public `int execute(...)` contract and specialize only
their own configuration. Shared step implementations remain parameterized. Declaration
checks reuse the existing method-contract parser, including comment/annotation handling.
Routing and return-format switching remain responsibilities of later operation composition;
steps return the original outcome without executing the next occurrence. Qualified default
OP-step implementing classes are passed from the existing component plan to parser analysis,
without another class search or a change to channel lookup semantics.

Complex-call records remain bound to the exact occurrence and qualified callee. Requests
require the saved method/path/base-URL-property/fingerprint and use existing native-operation
client instructions and transport validation. Calls cannot remain Composer dispatch or a
constant successful stub. External resource records retain existing connector/driver pins,
resource ownership and error/timeout guidance. Current target-contract and connection-source
freshness checks run before generation, reuse and publication. Target source backed by XML
and consuming-channel overrides are preserved by the existing qualified preparation data.
These checks do not establish that an external service is deployed or behaviorally equivalent.

Configured-step receipts retain their exact occurrence data as well as parser and artifact
proof. Reuse checks that occurrence again, revalidates current resources and rebuilds a
disposable candidate. A component receipt continues to mean build/test progress only:
CF4 does not create unit/operation acceptance or enable operation assembly. The original
configured-unit denominator and the whole-unit comparison requirement are unchanged.

Changed files and responsibilities:

- `source/agents/behavior_conversion/step_component.py`: instructions separating shared implementation behavior from configured execution and routing ownership.
- `source/runtime/component_conversion/steps.py`: eligible step groups, qualified source/default bindings, occurrence evidence and existing external-call safeguards.
- `source/runtime/component_conversion/requests.py`: reuse the canonical bounded builder for implementing-class and configured-occurrence requests.
- `source/runtime/component_conversion/scope.py`: authorize these step groups and reject changed unit/configuration/call/source identities.
- `source/runtime/component_conversion/validation.py`: specialized occurrence contracts, integer method declarations and retained occurrence receipts.
- `source/runtime/component_conversion/runner.py`: dependency-first step scheduling, prerequisite reuse and occurrence-aware cached-result checks.
- `source/runtime/scoped_native/runner.py`: enable step scheduling after the existing approval gates.
- `source/tests/test_component_steps.py`: repeated names/configuration/routes, missing prerequisites, default mappings, call-contract freshness and real Maven/JUnit component fixtures.

Format wrapper/composition generation remains CF5; subtree partitioning remains CF6.
Whole-unit parser mapping, original/native boundary comparison and final operation acceptance
remain CF7/CF8. No live bank-demo conversion, commit, push or deployment is part of CF4.

Validation: 93 component/preparation/reuse, scoped-native safety, request-size and CF3
regression checks passed (`outputs/cf4-regression-20261027.log`). The real offline
Maven/JUnit fixture built the helper, shared step implementation and two same-label
configured occurrences, observed distinct configured integer results, and then reused
all four components without model calls (`outputs/cf4-step-maven-serial-20261027.log`).
It created no accepted configured units or operations. This is a deterministic native
candidate fixture, not live AI conversion or original/native boundary acceptance.
An initial parallel run correctly invalidated reuse when another test rebuilt the
parser binary; the isolated serial run passed without weakening that freshness check.
The new step fixture now pins its own parser copy to prevent that test interference.
All 11 final focused safety checks passed with that isolated fixture
(`outputs/cf4-final-safety-20261027.log`), covering repeated occurrence configuration,
default implementing-class mappings, missing prerequisites, current call contracts,
native transport rejection and comment/annotation-safe integer method declarations.


## CF5 implementation result — 2026-10-27

The opt-in component-first scoped path now schedules format-wrapper implementations
and complete configured request/response formats after their native prerequisites.
The direct basic-component API retains its basic-only default; the dispatcher explicitly
enables format composition. The existing prepare and behavior-unit modes are unchanged.

Existing ordered `format_node` planning groups are bound as `configuration_bound`
evidence, not sent individually to the model or counted as generated native components.
Their immutable receipts bind the current plan/target and exact contract/result revisions
of their dependencies. Native changes invalidate consuming configuration and composition
receipts. Missing native prerequisites, unresolved references and cyclic configuration
cannot acquire a usable configuration receipt. The original graph and configured-unit
IDs/denominator remain unchanged; no new Mapper entities or files are created.

A complete-format request contains the selected original unit, direction, source XML,
ordered effective tree, scoped references and configuration/defaults, along with the
qualified root implementation and exact native prerequisite contracts/source. Only
configuration edges are flattened to find the composition's immediate implementing
classes/decorators. Java helper edges remain transitive build dependencies. Source bodies
and native APIs are not replaced by AI summaries. A changed source/configuration cannot
reuse an old parser boundary. Complete requests and corrections retain the existing size
checks; a format that cannot fit is incomplete until CF6 partitioning is implemented.

The separate `NativeFormatComponentBundle` adds whole-unit checklist answers and a
declarative native verification binding without changing the CF3/CF4 response schema.
Format contracts are specialized to their configured direction. The generator receives
current verification policy/authorizations and instructions to preserve source-driven
collection behavior, field/reference/decorator order, namespaces/prefixes, runtime inputs,
state writes and exceptions. There are no new per-tag behavior catalogs or business rules.

The assembled native source tree is checked with the existing `UnitVerificationSession`:
original parser mapping/exclusion rules and safe public API recipes run before compilation;
managed Maven compilation and executed tests run next; generated controlled inputs/settings
then execute the original classes and the actual composed native API in isolated JVMs.
Existing output/state/exception, executed-path and declared-unit-API checks remain active.
Failed/incomplete comparison prevents component publication. The native format entry API
is distinct from reusable infrastructure APIs, so a response need not execute its shared
implementation's request-only public methods.

Comparison/static/harness evidence is retained inside the hashed component artifact.
The receipt records its exact configured format and declarative recipes. Reuse rechecks
current parser/structure/policy evidence, rebuilds a disposable copy and reruns comparison
against current original sources. Configuration receipts remain structural evidence;
`component_validated` remains component progress. Observed matches do not establish
exhaustive equivalence, final unit acceptance or operation acceptance.

Changed files and responsibilities:

- `source/models/native_format_component_bundle.py`: format-only response metadata for the trusted checker.
- `source/agents/behavior_conversion/format_component.py`: source-driven format/wrapper instructions.
- `source/runtime/component_conversion/formats.py`: configured direction/tree identity, qualified body binding and native prerequisite selection.
- `source/runtime/component_conversion/format_verification.py`: reuse the existing whole-format technical ladder and retain comparison artifacts.
- `source/tools/state_store_tools/component_configuration.py`: immutable ordered-configuration receipts and dependency freshness.
- `source/tools/state_store_tools/conversion_components.py`: validate configuration evidence in transitive component checks without treating it as native code.
- `source/runtime/component_conversion/requests.py`: format schema, original-boundary revisions, complete configuration and bounded native prerequisites.
- `source/runtime/component_conversion/scope.py`: explicit format capability and source/structure/direction guards.
- `source/runtime/component_conversion/validation.py`: assembled parser/build/comparison checks, retained evidence and current-source reuse validation.
- `source/runtime/component_conversion/runner.py`: wrapper/configuration/composition scheduling and dependency flattening.
- `source/runtime/scoped_native/runner.py`: enable CF5 after existing plan/Gate 1 authorization.
- `source/tests/test_component_formats.py`: configuration state, direction/source guards, real JVM comparisons, prefix mutation and Maven/JUnit composition/reuse fixtures.

Limits: unsupported input/observer shapes still report verification incomplete under
the existing boundary-adapter rules; this milestone does not invent collection inputs
or bypass missing execution capabilities. Oversized splitting is CF6. Multipart unit
acceptance and operation packaging remain CF7, and fresh live bank acceptance remains
CF8. No converter restart, commit, push or deployment is included in this milestone.


CF5 validation: all 104 existing component/preparation/reuse, scoped-native, request-size,
CF3 and CF4 regression checks passed (`outputs/cf5-regression-20261027.log`). All nine
final focused format checks passed (`outputs/cf5-final-focused-20261027.log`), including
isolated-JVM request/response matches, observed calls to actual native format prerequisites,
a rejected literal XML-prefix mutation, preserved request context writes, stale parser/tree
rejection and configuration dependency-revision checks. The real offline Maven/JUnit test
also passed (`outputs/cf5-format-maven-20261027.log`): four native components built, both
configured directions passed the existing technical ladder, and all four were reused on
the warm run without model calls. This is deterministic candidate-fixture evidence,
not a live AI bank-demo conversion or final configured-unit/operation acceptance.


## CF6 implementation result — 2026-10-27

The opt-in component-first runner now measures a complete format request with its actual
schema, manual context, versioned requirements and generation instructions. Formats that
fit continue through the unchanged CF5 composition/verification path. An oversized request
can use exact configured child subtrees, converted bottom up, followed by a smaller root
composition request. No Java method/text splitting or AI source summaries are introduced.

Each extracted occurrence keeps its child-index path, full configuration hash, direction
and ancestor attributes/decorators. Repeated names remain distinct ordered occurrences.
Parents receive frozen child interfaces, result revisions and exact validated production
citations at the original child positions. Original native prerequisites remain build
dependencies; their interfaces replace duplicated source text only in partition prompts.
Complete original Java source, original entry points, the full parser checklist and
referenced definitions remain supplied. The trusted checker retains the original complete
format XML/tree, unit ID and boundary throughout. A part is instructed to expose actual
typed parent inputs/collaborators in its contract and preserve evaluation, state-write,
namespace/prefix, collection, decorator, exception and callback order. Such declarations
are not treated as proof of independent behavioral equivalence.

Every part goes through the existing source/API/package/dependency/test-platform guards
and isolated Maven compilation/executed tests. It must retain its parser citations and
cannot overwrite frozen prerequisite files. The existing durable generation/correction
loop saves model results per source/configuration-bound part identity. Artifact receipts
bind the full request, candidate, prerequisite source bytes, file hashes and build evidence;
their checksums are persisted separately in state. Reuse verifies the receipt/file hashes
and repeats a fresh canonical build/test using current dependency pins. Changing source,
configuration, instructions, target, a child contract/result or prerequisite bytes cannot
silently reuse an old part. A small fix in the shared generation loop skips inapplicable
compatibility metadata for exact-fingerprint component-cache hits.

The root candidate is checked against the original full-format request, with the assembled
production sources of its parts. The existing whole-unit parser/binding validation and
original/native comparison remain mandatory before root component publication. A failed
root comparison leaves parts reusable but cannot publish the root or accept a unit or
operation. Root artifact manifests include the assembled part sources; CF7 still owns
final multipart unit acceptance and operation packaging.

The configured root owns its extracted production sources as well as its entry mapper,
so later native consumers receive those files through the existing owned-source manifest.
Shared primitive/decorator/helper ownership is unchanged.

Subdivision is bounded to 128 visited occurrences and depth 32. Every recursive cut must
reduce the structural subtree size. Leaf/source/checklist overflow, atomic references,
oversized parent contracts after extraction and unsupported whole-boundary execution
remain explicit incomplete results. Referenced definitions are retained completely rather
than split across an uncertain reference boundary. The original Java/checklist evidence is
deliberately indivisible in this milestone; this can leave some large requests incomplete.
Corrections still pass the same full request-size guard and cannot silently truncate code.

`components/format-parts/<group>/partition-report.json` records ordered part progress,
configuration/contract/result revisions and the final compared/incomplete outcome. Part
progress does not change the configured-unit denominator or any acceptance gates. Default
prepare behavior, `behavior_units_v1`, Composer Mapper, Excel generators, step routing,
operation assembly and unrelated local work are unchanged. No live bank conversion,
commit, push or deployment is included.

Changed files and responsibilities:

- `source/tools/conversion_tools/component_partition.py`: pure ordered occurrence selectors, parent context and exact child replacement references.
- `source/runtime/component_conversion/partition_requests.py`: bounded source-preserving subtree projections and full schema/instruction size checks.
- `source/runtime/component_conversion/partition_runner.py`: bounded bottom-up extraction, durable part generation and complete root verification orchestration.
- `source/runtime/component_conversion/partition_validation.py`: canonical part builds/tests, immutable revision-bound receipts and fresh cache validation.
- `source/runtime/component_conversion/scope.py`: authorize only an exact trusted subtree projection while rechecking the unchanged original task/source/checkpoints.
- `source/runtime/component_conversion/runner.py`: select CF6 only for oversized complete-format requests and report subtree progress separately.
- `source/runtime/component_conversion/validation.py`: include extracted format production files in the root's owned-source manifest for downstream consumers.
- `source/runtime/behavior_conversion/generation.py`: avoid writing nonexistent compatibility metadata on component-cache hits.
- `source/tests/test_component_partitions.py`: measured splitting, ordering/checklist/source preservation, bounded failures, scope guards, real Maven reuse and whole-format comparison/mutation checks.
- This implementation plan: record CF6 behavior, limits, changed files and validation evidence; identify CF7 as next.

Validation: the combined CF6/component/format/state/graph/reuse/scoped-native/request-size
run passed 104 checks, with three deliberately deselected older component Maven fixtures
(`outputs/cf6-regression-20261027.log`). This includes actual Maven/JUnit part generation,
durable reuse without another model call, fresh rebuilds, an assembled original/native
comparison that observes the extracted API, rejection of a literal-prefix mutation inside
that part, contract/checklist guards and artifact tampering. The measured 50000-character
scheduling fixture forces nine parts and retains every original configured occurrence,
source byte and parser item; it uses deterministic scheduling doubles, separately from
the real JVM wire-behavior fixture. After the final owned-source export change, all 31
focused part/state/format checks passed (`outputs/cf6-final-checks-20261027.log`), including
downstream export of part files without claiming shared prerequisites. Syntax and scoped
diff checks also passed. These checks do not establish live AI bank-demo conversion,
exhaustive behavioral equivalence or final configured-unit/operation acceptance.


## CF7 implementation result — 2026-10-27

The explicit `component_first_v1` scoped mode now continues beyond component generation.
After the existing plan approval and Gate 1, complete validated roots feed the existing
configured-unit loop. Only technically accepted complete units can reach Gate 2 and the
existing occurrence-based operation assembly, Gate 3, service generation and finalization.
An incomplete component batch stops before that handoff. Default prepare behavior and
`behavior_units_v1` retain their existing generators, projects and gate policies.

The new provider reads the exact root source/test tree and frozen entry API from checked
component artifacts. It verifies transitive heads, immutable records, original source
bytes and retained source/build/report hashes. It resolves the original master checklist
against real current citations from the relevant component reports. Complete format
answers retain their already-checked original boundary identities and supported exclusions.
Missing master items or stale/nonexistent locations remain incomplete; component validity
is never a blanket exclusion. Unit-only configured requirements are forwarded to root
component generation, rather than invented as coverage during promotion.

Formats reuse their retained native entry recipes. Configured steps can request only a
`ComponentUnitBinding`: declarative input/output/context/settings wiring for the already
built frozen API, with optional type metadata. This response cannot contain Java sources,
new methods, expected outputs or executable harness adapters. The request supplies the
owned native code, exact public API declarations and configuration, not AI-written facts.
Qualified default step implementations come from the existing component plan; no new
class search or channel resolution is introduced.

The existing `UnitVerificationSession` remains the final authority: current parser mapping
and binding checks, canonical Maven compilation and executed tests, isolated original/native
comparison, observed mappings and source-path/API coverage all run before unit acceptance.
The component provider cannot record final verification itself; the existing scoped unit
wrapper requires completed session evidence and persists the usual unit-verification receipt.
Component progress and the configured-unit denominator remain separate. Warm promotion
reuses immutable generated code/bindings but reruns the whole-unit checks.

Acceptance additionally records a `unit_components` receipt binding the unit candidate hash
to its exact transitive component heads and source/configuration results. CF6 roots retain
their individual part-artifact receipt identities. Packaging and operation assembly recheck
these artifacts, their immutable state records and manifests, as well as the unit's ordinary
static/build/comparison evidence. Missing component receipts cannot promote a component-first
operation. Older format progress receipts without partition metadata are rebuilt/upgraded
before final promotion; their earlier component status alone does not establish acceptance.

Component invalidation demotes only dependent accepted units to verification-incomplete;
unaffected sibling receipts and prerequisite artifacts remain available. A concrete whole-unit
verification failure can send its exact item/input/output feedback to the configured root's
existing bounded component generator. That root is invalidated and retried with unchanged
prerequisites reused. Corrections are bounded by the configured attempt limit. Missing harness
capabilities remain incomplete immediately, rather than causing an unlimited correction loop.
No source truncation, automatic request-budget increase, test relaxation or external success
stub is introduced. A root-only correction that cannot resolve the defect remains blocked;
this milestone does not add an unrestricted cross-component semantic debugger.

The scoped execution report now includes actual persisted unit outcome counts, pending units
and operation counts whose unit receipts still validate. Passing preparation or component
fixtures does not mark the bank demo accepted. A fresh live bank Mapper/converter run remains
CF8 and has not been started by this milestone. Nothing is committed, pushed or deployed here.

Changed files and reasons:

- `source/models/component_unit_binding.py`: metadata-only native entry response schema.
- `source/runtime/component_conversion/unit_artifacts.py`: transitive artifact/part checks and candidate-bound final component receipts.
- `source/runtime/component_conversion/unit_binding.py`: deterministic complete-checklist resolution and bounded native entry metadata.
- `source/runtime/component_conversion/unit_provider.py`: whole-unit candidates from frozen components, current-source guards and bounded root correction.
- `source/runtime/component_conversion/requests.py`: forward configured unit-specific requirements to component code generation.
- `source/runtime/component_conversion/runner.py`: current feedback/requirement/partition-cache guards and exact unit-failure feedback delivery.
- `source/runtime/component_conversion/validation.py`: retain requirement, feedback and partition references; verify part receipts during reuse.
- `source/runtime/component_conversion/partition_runner.py`: bind composed roots to their actual part-artifact receipts.
- `source/tools/state_store_tools/component_records.py`: invalidate only dependent final unit acceptance alongside component heads.
- `source/runtime/behavior_conversion/runner.py`: optional component provider in the existing unit loop; checked units before operation assembly.
- `source/runtime/behavior_conversion/revisions.py`: forward the existing optional generator to scoped technical verification.
- `source/runtime/behavior_conversion/verification_units.py`: run supplied assembled candidates inside the unchanged technical ladder.
- `source/runtime/behavior_conversion/verification_request.py`: preserve qualified default-step bindings in original boundary analysis.
- `source/runtime/behavior_conversion/verification_state.py`: enforce transitive component receipts before component-first packaging.
- `source/runtime/scoped_native/runner.py`: enable the opt-in handoff and report real persisted outcomes.
- `source/runtime/scoped_native/scope.py`: authorize component-mode native execution and metadata tasks within existing scoped checkpoints.
- `source/tests/test_component_acceptance.py`: integrity, completeness, requirement, scope, invalidation, correction, handoff and real JVM unit acceptance/reuse checks.
- This plan: document CF7 behavior and limitations, validation evidence and CF8 as next.

Validation so far: the real offline Maven/JUnit acceptance fixture passed together with
six initial CF7 checks (`outputs/cf7-acceptance-20261027.log`, seven passes). It builds a
source-backed format from three native components, performs whole-unit static/build/original
comparison, persists technical acceptance, repeats it without another model call and rejects
changed component receipts. Its scoped checkpoint/result ledger is an explicit fixture double;
the real scoped checkpoint and handoff guards are exercised separately. It is not live AI
bank-demo acceptance. The subsequent combined focused run passed 59 checks
(`outputs/cf7-final-focused-20261027.log`).

The broader run passed 162 checks and encountered one pre-existing obsolete fact-review
fixture: `source/tests/runtime/test_behavior_comparison.py::test_grounded_findings_feed_generation_correction_with_original_evidence`.
It supplies a `scoped-fixture` payload with no `unit_id`, and fails in original parser setup
with `KeyError: unit_id`, before any component handoff. Removing the CF7 forwarding changes
in memory reproduces exactly the same failure (`outputs/cf7-pre-change-check-20261027.log`).
That unrelated old AI-fact fixture has not been modified or used to relax validation.

Final validation: all 14 CF7 guards passed (`outputs/cf7-final-guards-20261027.log`),
covering complete citation resolution, source/receipt integrity, subtree artifacts,
unit-only requirement delivery, dependent-only acceptance invalidation, exact root
correction feedback, bounded retries, immediate capability-gap stops, metadata task
authorization and the guarded scoped handoff. The final report/handoff check also passed
(`outputs/cf7-handoff-final-20261027.log`): handoff marks verification in progress and
reports unaccepted units as pending. Completion is reported only with accepted units,
validated operation artifacts and a completed persisted run. Syntax and scoped whitespace
checks passed. The Mapper, Excel generators, unrelated code and the default generation
mode were not changed. CF8's fresh live bank-demo end-to-end run remains outstanding.


## CF8 execution tooling and live run — 2026-10-27

The bank-demo-only runner now performs a fresh actual Mapper intake and scoped conversion
in `component_first_v1`, using a new isolated database, vault, generated tree and service
registry. It retains the 900000-character budget, four transport and generation attempt
limits, the user's automatic gate authorization and all technical checks. Git actions
are disabled. No cluster deployment or image publication is performed; absent technical
or deployment evidence still blocks the existing final gate.

Measurement distinguishes component progress, recorded task attempts, executor interactions,
executor transport attempts and request-size checks. It retains full application-JSON and
instruction character/byte measurements (decimal KB/MB/GB), including oversized probes
never sent. These checks are not request counts, provider-envelope sizes or token counts.
The metadata-only event files exclude prompts and credential values.

A live observer publishes progress every 15 seconds. Terminal measurement checks unit
static/build/comparison and transitive component receipts, plus approved operation artifact
manifests. Persisted flags, component counts and preparation cannot establish acceptance.
Read-only measurement cannot restart a run or alter its decisions. Existing pilot selection
and measurement are retained, with a per-category cap of 1000 to include all available bank
units; that cap is not an enterprise sample-size claim. Unchanged warm reuse is attempted
only after full cold acceptance. Failures and incomplete evidence remain explicit.

Changed files and responsibilities:

- `source/tools/behavior_verification/component_pilot_run.py`: isolated fresh execution, live observer, model metrics and conditional warm reuse.
- `source/tools/behavior_verification/component_pilot.py`: source-free metric capture and evidence-checked live/terminal reports.
- `source/tests/test_component_pilot.py`: prevent false acceptance from component progress, stale flags and missing evidence; check oversized weights and metadata-only logging.
- `bank-demo/README.md`: reproducible command and report interpretation.
- This plan: distinguish implemented tooling from actual live acceptance.

Validation: all four metric/report tests passed (`outputs/cf8-metrics-tests-20261027.log`).
The Mapper rebuilt successfully (`outputs/cf8-mapper-build-20261027.log`). A fresh real run
started under `outputs/bank-demo-component-first-20261027`, with ID `bank-demo-component-first`.
Mapping and import completed; 10/10 contexts prepared, with 83 configured units and 83
identified original boundaries. At this checkpoint no units or operations are accepted.
The live acceptance report and CF8 measurement contain subsequent actual outcomes. CF8
must not be marked accepted until those outcomes and reuse checks establish it.


CF8 live-run correction: component requests now supply the exact expected contract fields
and allowed source evidence identities, separately from component/checklist identities.
Generation instructions require these fields; validation remains strict and now reports
expected values. This addresses the demonstrated metadata-delivery failure without
relaxing native-package, executable-test or source-traceability checks.

Additional changed files: `source/runtime/component_conversion/requests.py` supplies the
contract metadata; `source/runtime/component_conversion/validation.py` explains rejected
values; `source/agents/behavior_conversion/component_generation.py` and
`source/agents/behavior_conversion/format_component.py` explain the contract delivery;
`source/tests/test_component_generation.py` covers exact identities and rejection.
The combined focused suite passed 49 checks (4 deselected), including report/process
safety. Evidence: `outputs/cf8-contract-fix-tests-20261027.log`.

The same isolated fresh run resumed with its database and attempt history preserved.
At the subsequent checkpoint, the process remained active with 0/83 accepted units and
0/10 accepted operations. Component test-coverage failures remained explicit; these are
not accepted output. Automated monitoring is active. CF8 acceptance and warm reuse remain
pending. No unrelated implementation, Mapper, Excel generator or enterprise source was
changed for this milestone. Nothing was committed or pushed.

## Planned correction: typed boundaries and shared types — 2026-10-29

Require typed inputs and outputs during initial generation, rather than generating
generic maps first and asking a later pass to replace them. The converter supplies
the relevant XML, resolved format references and implementing/dependent sources;
users do not supply request or response DTOs. Determine field names, Java value types,
nesting and collection structure from that evidence. Preserve runtime-dependent
behavior rather than guessing types or behavior from tag names alone.

1. **Request format generation:** require typed parsing results, validate the actual
   public API and comparison binding, then accept the generated classes only after
   the applicable build, tests and original-versus-native checks pass.
2. **Response format generation:** supply its own XML/source evidence and the accepted
   request types and APIs. Require typed field/runtime inputs and the boundary's
   required serialized output (for example, an XML String). Reuse compatible existing
   types and format implementations; create response-specific types where needed.
3. **Operation-step generation:** supply its implementing sources and the accepted
   request/response types and APIs. Require typed inputs and typed state/results
   exposing the actual reads, writes and outcome; preserve integer outcomes where
   required. Reuse accepted types instead of recreating Context as a generic map.
4. **Integration validation and correction:** check that all three boundaries connect
   through compatible APIs and reuse accepted types where appropriate. Give a repair
   pass concrete API, binding or behavior differences. Rebuild, run tests and compare
   original/native outputs after corrections; type reuse alone is not acceptance.

Value types and format behavior are separate. Username and family-name fields may
both be String without separate wrapper classes. If a configured family-name format
adds parsing or formatting behavior, connect that field to its converted format
implementation while retaining String as the value type. Reuse must preserve each
field's configured behavior and the identity of its resolved implementation.

Invalid generated APIs or bindings (including an unsupported generic-map boundary)
must receive bounded correction feedback with the supported contract. Genuine harness
limitations, such as unobservable presence or partial writes, remain explicit and do
not trigger behavior corrections. All technical acceptance checks remain required.
These four steps are planned work; this section does not claim implementation or
acceptance of the response formatter, operation step or complete operation.

### Typed-boundary implementation checkpoint — 2026-10-29

The shared generation path now attaches `typed-boundary-v1` guidance with configured
field paths/attributes, resolved definitions and the accepted native APIs available for
reuse. XML and full implementing sources remain the authority for type and behavior
selection; users do not supply DTOs. Request, response and step examples describe API
shapes only. Value types remain separate from configured format/decorator behavior.

Configured component requests receive the same policy. Declared generic Map/Object/
JsonNode APIs and raw collections are rejected before build with bounded correction
feedback. Typed collections and ordinary equals(Object) overrides remain supported.
Existing method-contract checks and compilation still verify actual declarations and
accepted API integration. Unit ordering makes response types available before steps
within the existing ownership and operation dependency constraints.

The isolated thin-path runner supplies later boundaries with native API/source and
dependency pins only after the earlier boundary passes its build, tests and comparison.
It rejects copied/overwritten prerequisite files and compiles reused sources together.
Unsupported generated binding recipes are retryable candidate failures; genuine
comparison limitations retain Verification incomplete. No live conversion was launched
for this implementation checkpoint, and no full-operation acceptance is claimed.

Validation: the final focused generation/comparison suite passed 81 tests, including real
JVM comparisons and all 22 typed-policy tests. A broader component run also exposed older source-selection fixture failures
(6 failures and 14 setup errors); representative failures reproduce with the new policy
disabled. Those unrelated fixtures were not changed. Logs:
`outputs/typed-boundaries-tests-20261029.log` and
`outputs/typed-boundaries-baseline-diagnostic-20261029.log`.

Files changed for this checkpoint:

- `source/runtime/behavior_conversion/typed_boundaries.py`: shared evidence descriptors, API examples and typed-contract validation.
- `source/runtime/behavior_conversion/generation.py`: attach the policy and validate initial, corrected and cached bundles.
- `source/runtime/behavior_conversion/runner.py`: make response types available before configured steps within existing ordering constraints.
- `source/runtime/component_conversion/requests.py`: supply the shared policy to configured component generation.
- `source/runtime/component_conversion/validation.py`: check component typed APIs before build.
- `source/tools/behavior_verification/thin_path_request.py`: supply verified prior APIs, sources and pinned dependencies.
- `source/tools/behavior_verification/thin_path_run.py`: retain reusable types only after successful boundary validation.
- `source/tools/behavior_verification/thin_path_validation.py`: build with reused sources, prevent overwrites and retry invalid generated bindings.
- `source/tests/test_typed_boundaries.py`: check evidence/reuse delivery, typed collections, API rejection and automatic corrections.
- This plan: implementation status and validation limits.

Mapper, Excel generators, operation selection and unrelated code were not modified.
Technical build, comparison and final acceptance requirements remain in force.

## Whole-unit side-road conversion — 2026-10-30

This replaces the proposed class-by-class dependency recovery. On an exhausted normal
candidate retaining a prohibited IBM dependency, the opt-in side road converts the
whole selected unit into an IBM-free baseline, verifies it, then simplifies that
baseline and verifies it again. It does not recursively create helper-class jobs.

The baseline may temporarily retain original-like internal support structure. Native
packages, typed public boundaries, source evidence, safe paths, dependency checks,
executed tests and original/native comparison remain required. IBM imports/references
in main or test code remain prohibited. Simplification restores the ordinary architecture
guard and preserves the verified public APIs and boundary binding. Only its successful
result passes back through normal parent validation. A baseline alone is never final
parent acceptance or full-operation acceptance.

Stage attempts are persisted in `side_road_conversions`, separately from the parent's
normal correction budget. Defaults are four baseline and four simplification attempts.
Reservation happens before each model call and survives interruption/restart. Changed
correction text does not reset these counters. No recursive side road is permitted.
Verified baseline JSON and validation receipts remain stored if simplification fails;
reuse requires a fresh build/test/comparison, not merely a persisted accepted flag.
A failed freshness/revalidation check marks the retained artifact unverified.

`side_road_conversion` defaults to false. The shared trigger requires a trusted isolated
validation adapter; it never falls back to ordinary publishing validation for baseline
candidates. The first adapter is deliberately the thin-path experiment. Production
scoped conversion is not enabled for this relaxation without an isolated adapter that
preserves all its existing scope and acceptance gates.

Changed files and responsibilities:

- `source/runtime/behavior_conversion/generation.py`: opt-in trigger after the specific terminal IBM-dependency failure; normal generation remains strict.
- `source/runtime/behavior_conversion/side_road_conversion.py`: orchestrate both stages through the existing generator and retain only verified baselines.
- `source/runtime/behavior_conversion/side_road_policy.py`: typed forbidden-dependency diagnostic and temporary, context-local baseline architecture policy.
- `source/agents/behavior_conversion/side_road_instructions.py`: separate translation and simplification instructions without conflicting architecture demands.
- `source/tools/state_store_tools/side_road_state.py`: durable stage budgets, baseline artifacts, status and receipts; existing Resume budgets remain unchanged.
- `source/runtime/behavior_conversion/bundle_output.py`: classify retained IBM dependencies and allow temporary support structure only during baseline validation.
- `source/models/pipeline_configuration.py`: opt-in flag and bounded per-stage attempts.
- `source/tools/behavior_verification/thin_path_run.py`: explicit response-only selection and side-road experiment flags.
- `source/tools/behavior_verification/thin_path_validation.py`: isolated stage folders with actual build, JUnit and original/native comparison.
- `source/tests/test_side_road_conversion.py`: stage isolation, independent budgets, fallback retention, strict simplification, API preservation, incomplete receipts and disabled-policy checks.

The initial combined regression run passed 87 tests, including existing real-JVM
comparisons. All 10 side-road flow/policy tests passed; their synthetic receipts test
orchestration only and do not establish live equivalence. A fresh response-only live
trial started at `outputs/bank-response-side-road-20261030`, selecting only
`INTERNET/GetClientLinksOp` / `StandardErrorRSFmt`. Its process/status, attempts and
comparison reports determine the live result. The previous successful request and
OP-step artifacts were not changed. No commit, push or deployment was performed.

Final implementation regression: 91 tests passed, including the 10 side-road tests.
The response-only trial then terminated blocked: normal conversion used four attempts,
followed by four baseline attempts and zero simplification attempts. Baseline responses
retained IBM dependencies or exposed an unsupported generic Map boundary; the first
also omitted the required coverage identity. No candidate reached compilation, JUnit
or original/native comparison, and no verified baseline was stored. The counter limits
and guards worked, but live behavioral acceptance was not established. Monitoring was
removed after inspecting the terminal attempt history. The next experimental correction
should supply an explicit supported boundary/binding contract rather than relaxing the
IBM-free or typed-boundary requirements.

## Focused staged conversion — 2026-10-30

An opt-in `staged_unit_conversion` path now separates implementation generation, parsed
metadata, compilation, binding resolution, test generation and final boundary comparison.
The first qualified adapter remains the isolated thin-path runner. Default production
conversion and its scoped acceptance gates are not switched over before live validation.

1. The implementation response contains production Java files and unresolved questions
   only. Its prompt excludes tests, coverage tables, dependency coordinates and binding
   recipes. It still supplies the complete selected XML and supporting Java evidence.
2. The application-owned JavaParser inspector extracts native public types, methods,
   constructors, DTO members and imports, plus literal original context keys and static
   settings method signatures. Comments and strings cannot invent public declarations.
3. Imports select existing pinned dependency candidates. New unresolved artifacts use a
   dependency-only request. A package-prefix inventory match is provisional, not proof
   of direct JAR ownership: the existing verifier and compiler must establish availability.
   Versions/scopes cannot override known pins. No new coordinates are inferred from a
   package name alone.
4. Production code compiles in an isolated compile-only project before tests are requested.
   Compile receipts are not test/comparison acceptance. Accepted prerequisite sources and
   pins are preserved and cannot be overwritten.
5. Exact normalized field/context names and parsed API types produce bindings where
   unambiguous. Ambiguity uses a mapping-only request, constrained by actual parsed
   constructors, setters, getters and settings APIs. Property keys are actual setter
   names. The settings schema requires exactly `class` and `method`; original control
   keys and native methods are checked independently. Missing observability remains a
   limitation, not a fabricated successful comparison.
6. A separate tests-only response receives original evidence, frozen production code,
   parsed APIs and the approved testing platform. It may return test files and links to
   exact requirements; it cannot edit production code. Real JUnit and original/native
   comparisons still run before the assembled bundle can be retained as complete.
7. Concrete output differences return to implementation repair, without repeatedly asking
   the test generator to repair production behavior. Test-only failures remain test
   corrections. Independent persisted budgets limit implementation, mapping, dependency
   and test requests. Candidate fingerprint changes do not reset per-unit/source budgets.
8. Baseline and simplification side-road stages invoke this same flow. Side-road counters
   count implementation requests separately from binding/test calls. Baseline public
   APIs remain frozen during simplification; an unsimplified baseline is never final
   acceptance.

New files:

- `source/models/native_implementation.py`: production-files-only response schema.
- `source/models/native_test_bundle.py`: tests-only response schema.
- `source/models/native_mapping_selection.py`: mapping-only response schema.
- `source/models/native_dependency_proposal.py`: unresolved dependency proposal schema.
- `source/models/native_settings_binding.py`: exact settings target schema, retaining dictionary runtime compatibility.
- `source/agents/behavior_conversion/staged_instructions.py`: separate role instructions.
- `source/runtime/behavior_conversion/staged_conversion.py`: bounded stage orchestration and focused corrections.
- `source/runtime/behavior_conversion/native_metadata.py`: parser output and pinned dependency candidates.
- `source/runtime/behavior_conversion/native_binding_builder.py`: automatic and validated explicit mappings.
- `source/tools/state_store_tools/staged_conversion_state.py`: stage counters, attempts and source-bound artifacts.
- `source/behavior-verification-java/src/main/java/il/co/dcd/verification/NativeApiInspection.java`: non-executing JavaParser inspection.
- `source/tests/test_staged_conversion.py`: parser, stage ownership, strict bindings, frozen production, budget and side-road tests.

Existing files changed:

- `source/runtime/behavior_conversion/generation.py`: opt-in staged routing and immediate production-feedback handoff.
- `source/models/pipeline_configuration.py`: staged mode defaults to false.
- `source/models/native_verification_binding.py`: explicit settings-target schema.
- `source/runtime/behavior_conversion/side_road_conversion.py`: reuse the same staged generator and independent role budgets.
- `source/tools/behavior_verification/thin_path_validation.py`: isolated compile-only adapter.
- `source/tools/behavior_verification/thin_path_run.py`: explicit staged/timeout overrides and effective configuration metadata.
- This plan: scope and validation evidence. Existing bundled instructions/API-display helpers were not rewritten;
  the staged path uses dedicated narrow instructions and JavaParser metadata instead.

Validation: the Java tool rebuilt successfully using the selected JDK. The focused
regression suite passed 102 tests, including all 10 staged-flow tests and existing real
JVM comparisons. Mock technical receipts in orchestration tests do not prove live
equivalence. A fresh response-only trial started at
`outputs/bank-response-staged-flash37-20261030`, selecting only `StandardErrorRSFmt`,
with `gemini/gemini-3.7-flash` and an explicit 300-second API timeout. Live build/test/
comparison evidence determines its result. The successful earlier request and OP-step
artifacts, Mapper, Excel generators, operation selection and final gates remain unchanged.
Nothing was committed, pushed or deployed.

### Full converter staging checkpoint — 2026-10-31

- Staging is now the default for the Composer behavior-unit/component-first converter, including saved runs resumed with the real model. Explicit task categories distinguish production, DTO structure, metadata and route-test jobs; response schema alone no longer decides the role.
- Components, configured steps, format components/partitions, configured units and service assembly generate production first. JavaParser derives the actual APIs; pinned dependency resolution and a real compile run before a separate metadata request and tests-only generation. DTO contracts generate structure before Java; route scenarios generate tests only.
- `stage_tasks.py`, `stage_scope.py`, `conversion_tasks.py`, `stage_compilation.py`, `staged_adapters.py` and `staged_pipeline.py` provide the shared execution path. `staged_metadata.py` and the staged prompt module keep code out of metadata responses. Existing component, partition, unit and incremental-operation validators remain responsible for final acceptance.
- Child requests retain their original parent checkpoint/scope authorization. Scoped result ledgers and exact accepted parent-request receipts are retained, including warm route-test reuse. These receipts do not invent model attempts or prove acceptance by themselves.
- Each role retains its durable bounded budget. Correction feedback does not change its identity or reset counters. Passing tests may be reused after production correction only after fresh technical and behavior validation. Actual output differences return to implementation correction; comparison limitations and environment failures do not become model code bugs.
- Complete source evidence remains available; staging does not replace source with AI summaries. An oversized contract request reports its partitioning requirement. Existing dependency/component order and format partitioning remain in effect.
- The 19 new staging integration tests passed, including real Maven production compilation, JUnit, staged service assembly with separate route scenarios and warm reruns without new AI calls. Mock orchestration checks are not equivalence evidence. Live single-operation acceptance still requires the full runner's final reports.
- The focused regression run adds 66 passing checks for isolated staging, side-road recovery, behavior-unit conversion and incremental operation assembly: 85 checks passed in total. The existing single-operation run at `outputs/single-operation-full-current-20261031-052006` is being resumed with shared staging enabled; its seven configured units and one operation remain subject to final acceptance, not prior component/test success.
- Mapper, Excel generators, bank-demo XML/Java, operation selection, logging policy, model, timeout, request budget, retry limits and technical acceptance gates are unchanged by this integration. Existing explicitly unstaged legacy test fixtures remain supported. No commit, push or deployment is part of this change.

### Selected-interface validation correction — 2026-10-31

Typed-interface validation now selects the formatter/step entry using its actual binding,
including its exact overload and static membership. It checks the constructors, setters,
value getters and projection/presence getter chains used by that binding. Other public
helpers, including `fromMap`/`toMap` and unused overloads, are not typed-boundary obligations.
Their safety, source-contract, compilation and behavioral checks remain unchanged.

`typed_boundary_selection.py` owns this selection; `typed_boundaries.py` applies the
existing type policy only to selected signatures when a binding is available. The
pre-binding staged check likewise considers possible entry methods only. It requests
implementation correction if no supported typed entry exists. Errors found after
binding selection persist focused feedback and return to the same bounded implementation
loop, rather than terminating before tests or resetting attempt budgets.

Changed files: `source/runtime/behavior_conversion/typed_boundary_selection.py` (new),
`source/runtime/behavior_conversion/typed_boundaries.py`,
`source/runtime/behavior_conversion/staged_conversion.py`,
`source/tests/test_typed_boundaries.py`, `source/tests/test_staged_conversion.py`, and
this plan. No public API, model, timeout, retry limit or unrelated implementation changed.

Validation: 108 focused regression tests passed. The previously compiled live candidate
and its saved binding pass the new check in a read-only replay, without changing its
Java or historical database. That check alone is not behavior acceptance. A fresh
response-only run started under `outputs/bank-response-selected-boundary-20261031`
with Flash 3.7 and an explicit 300-second API timeout; actual build/JUnit/comparison
results remain the acceptance evidence.


### Selected-direction test correction checkpoint — 2026-10-31

- Staged test requests identify the selected formatter method, argument types and runtime controls. Reverse-direction and round-trip coverage is not required merely because unused methods exist.
- `staged_instructions.py` and `staged_conversion.py` supply that scope without changing production sources or assertions.
- `NativeApiInspection.java`, `NativeTestCalls.java`, `native_metadata.py` and `native_test_scope.py` detect direct reverse calls on explicitly typed selected-formatter receivers. This is a narrow AST scope guard, not complete call-graph analysis; unresolved receivers remain subject to build and behavior validation.
- `thin_path_validation.py` preserves compiler/JUnit candidate correction errors instead of misclassifying them as infrastructure failures. Actual environment failures still stop. Existing correction budgets and original/native comparison requirements are unchanged.
- Tests must preserve original expectations; an unresolved frozen production defect must be reported rather than hidden by weakened assertions. Historical reverse-direction failures remain recorded and do not establish equivalence.
- Regression checks in `test_staged_conversion.py` and `test_thin_path_experiment.py` cover scope, comments/string literals, unrelated helpers, bounded JUnit retry and environment-stop behavior. Focused suite: 112 passed; Java verification tool rebuilt successfully.
- No live conversion rerun or acceptance claim is part of this checkpoint. No commit or push performed.


### Passing-test reuse checkpoint — 2026-10-31

- `staged_conversion_state.py` retains an independent `passing_tests` artifact only with a successful build, passing JUnit and a positive executed-test count. It records test hashes, original revision/source/configuration hashes, selected API/binding, production hash and validation receipt. This is not acceptance. Integrity and current evidence/policy eligibility are checked before reuse.
- `staged_conversion.py` records these tests even when subsequent original/native comparison fails. Corrected production tries them before any new test-generation request; it reruns scope, dependency, bundle/testing-policy, compile, JUnit and behavior checks. A previous receipt never validates new code. Stale sources or policy do not supply eligible tests.
- Selected-API changes or test failures seed bounded repair with retained source and actual diagnostics; original expectations cannot be weakened automatically. Proven boundary mismatches return to implementation correction. Infrastructure/comparison limitations still stop. Exhausted budgets allow no-model revalidation, but never extra AI calls or counter resets.
- `test_staged_conversion.py` covers exhausted test-generation budgets, stale/integrity checks, changed API repair, repeated assertion failures, infrastructure failure and final-acceptance separation. All 146 focused/regression checks passed, including the real JVM logging checks from the previous milestone.
- A fresh no-model replay started at `outputs/bank-response-retained-tests-replay-20261031-050332/run`: saved corrected response implementation attempt 3 and previously passing tests attempt 4, with source hashes and provenance in the parent folder. Existing replay tooling reruns technical/comparison checks; this live replay is not a model-generation run or proof of full-operation acceptance. Original run databases, receipts and retry counters remain unchanged. Monitoring is active; result pending.
- Changed source files are limited to the staged converter, staged state storage and focused tests; this plan records the implementation. Logging policy, retry limits, generation instructions, original Java/XML and unrelated code remain unchanged. Nothing committed or pushed.

### Nested-test and inherited-entry validation correction — 2026-10-31

- `junit_reports.py` reads actual testcase execution inside nested/display-named suites, associates it with its owning report/class and avoids counting duplicate reports or aggregate counters twice. Skipped-only, failed, missing and zero-test evidence still cannot pass `validation.py`.
- `NativeApiInspection.java`, `native_metadata.py` and `native_inheritance.py` resolve public native ancestry from supplied source, including generic parent arguments, overrides and interface methods. Methods retain declaring-type provenance. Constructors, private/protected methods and interface static methods are not inherited APIs; inaccessible ancestors are not exported as owned APIs.
- `method_contracts.py`, `bundle_output.py`, `staged_adapters.py` and component `validation.py` use the resolved inventory when checking inherited signatures against frozen prerequisite sources. API ownership still belongs to the generated type; prerequisite files cannot be claimed or overwritten.
- Component `steps.py` distinguishes missing metadata for an existing inherited entry from an actual missing implementation. `staged_pipeline.py` catches a missing integer step entry immediately after production compilation and corrects Java within its existing budget, before metadata/tests. Later owner-specific interface defects also return to implementation correction. Metadata instructions explicitly identify inherited entry methods and their declaring parents.
- The prerequisite-receipt investigation found no storage defect: the affected CCXML dependencies had registered contracts but no validated result because their test validation failed. `conversion_components.py` and existing prerequisite acceptance requirements remain unchanged.
- Read-only historical candidate replay is under `outputs/staged-validation-replay-20261031`. Unmodified saved CCXML production and test attempt 4 compile and pass all 24 JUnit tests with the corrected report reader. The three saved configured error-step implementations compile and pass one deterministic inherited-entry invocation test each. Those new smoke tests are not original/native comparisons. No AI calls, historical state changes, attempt resets or full-operation acceptance are claimed by this replay.
- Regression checks cover nested/duplicate/display-named suites, failures/skips/zero tests, generic/native ancestry, non-public ancestor visibility, overrides, signature mismatches, inherited step metadata and implementation correction ownership. Mapper, Excel, bank-demo source, logging policy, model, timeout, request budget and technical gates remain unchanged. No commit/push is part of this checkpoint.
- Validation: 127 focused regression checks passed across the report/inheritance/staged-path tests and existing method-contract, behavior-conversion, isolated-staging and side-road suites. The same full operation run is resumed from `conversion_components_incomplete` with existing history/counters retained. Rebuilt parser provenance is rechecked by the runner; prior replay success is not reused as final unit/operation acceptance.

### Metadata checklist Alternative 2 — 2026-10-31

- Implemented on `codex/metadata-2`: deterministic provenance/APIs, separate semantic metadata, method-grouped mapping batches, exact evidence expansion, aggregate errors, partial retention and durable shared budgets. Full and isolated staged paths assemble existing final schemas and retain all technical/behavioral gates.
- See [Metadata Checklist, Eping, Alternative 2](../Metadata%20Checklist,%20Eping,%20Alternative%202.md) for actual changed files and limitations. Local checks passed: 87 broader regression tests, 21 latest focused tests and a separate real Maven/JUnit batched-component fixture; counts overlap.
- A read-only 168-item replay completed 13 fixture mapping requests, including one targeted repair, with no provider calls or historical state changes. This establishes traceability mechanics only, not equivalence or operation acceptance.
- **Do not resume the conversion run.** The user explicitly deferred the live trial after implementation. No new process, monitoring automation, commit or push was started for this checkpoint. Mapper, Excel, original bank-demo sources and unrelated code remain unchanged.
