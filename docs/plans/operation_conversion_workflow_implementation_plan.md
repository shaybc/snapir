# Operation Conversion Workflow — Staged Implementation Plan

Status: Stages 1–4 implemented. Stage 5 verification tooling and offline checks
are implemented; complete live bank verification remains blocked by the bounded
run's time limit. The sequential wrapper invokes the existing converter with
intake checks, an approved plan and shared service registration. It does not
duplicate or replace the existing conversion workflow.

Design references: [operation-call design](../operation_calls.md),
[native converter design](../../option_two_design.md#operation-dependencies-and-approved-sequential-conversion)
and [native implementation record](../../option_two_implementation_plan.md).

## Agreed conversion-run flow

1. Select the operations/channels and the application's shared registry.
2. Intake discovers the required evidence, resolves direct and indirect CCComplex
   calls, checks dependencies and cycles, then produces the complete conversion
   plan. Missing dependencies or cycles block with details for user resolution.
3. Present intake's plan for approval before invoking the thin wrapper. This is
   one plan-approval point for the conversion run, not another gate repeated for
   every operation. Store its configured approval policy and accepted evidence.
4. The thin wrapper selects the next operation in the accepted order and invokes
   the existing conversion workflow, including packaging, tests and its existing
   four configurable gates. Wait for completion before selecting another operation.
5. Publish the successfully converted operation's callable API in the shared
   registry and save its completion in the run database before advancing.
6. On failure or pending approval, pause at that operation. Resume retains
   completed work and continues the same accepted plan.

Intake's output is a readable plan showing the selected scope, waves, operation
order, prerequisites, reused services and any blockers. Detailed Markdown and
logs remain supporting evidence. A pilot, if used, respects the same dependencies.

The run-plan approval precedes the wrapper and is distinct from the four gates
inside the existing conversion workflow. Keep those four gates and their numbers,
human/automatic/skip settings and technical checks unchanged. Reuse the existing
approval machinery for the run-plan approval; do not invent a second approval
engine. Default plan approval to human review, with a separately saved policy
using the same settings conventions. Automatic/skipped human approval never
bypasses missing dependencies, cycles or failed technical checks.

## Scope boundaries

- Reuse existing conversion, generation, assembly, packaging, operation tests,
  reviews, bounded corrections and established validation requirements.
- Add only the wrapper, registry, intake/planning changes and integration points
  needed to invoke the existing workflow for the current operation.
- Use one database per run and one shared registry database per source application.
  API-use snapshots are records inside the run database, not a third database.
- Trust completed published service contracts. Do not revalidate or reconvert a
  target for every caller, or reopen its internal conversion dependency tree.
- Block when a required operation is neither included nor published. No ignored
  dependencies, production placeholders, null substitutes or Composer fallback.
- Keep initial XML support. Record other API formats only when supported; JSON
  conversion and mock/runtime-test configuration are outside this change.
- Preserve legacy behavior, existing saved work, ownership rules, Excel generation
  and bank demo definitions. Do not silently reset or upgrade old run checkpoints.

## Development stages

These are implementation increments for the developer. They are not extra stages
or human gates executed inside every conversion run.

### Stage 1 — Shared registry and run-local records

Implement a small registry module and a typed published-service contract. Save
the source application identity and shared database location in configuration,
outside individual run directories. Keep registry access separate from the
existing run connection and its task/progress storage.

The registry maps source application/channel/operation to the successfully
converted service and API revision. Include service/artifact identity, method and
route, request/response structures and parameters, errors/outcomes, supported
media types, environment-specific address configuration and completion evidence.
Save the API definition; an optional Swagger/OpenAPI link is additional metadata.
Draft and planned interfaces stay in run state, not the completed-service registry.

Record each reused API's identity, revision, call contract and selected address
configuration in the existing run database. Later Resume uses those records;
archiving an old run must not remove its published service from the shared registry.
Do not automatically promote older run-local statuses to published completion.

Acceptance: focused storage tests demonstrate publication after completion,
lookup from a different run, application/channel isolation, and stable API-use
records without creating a third database or revalidating the target.

Stage 1 implementation record:

- Added typed completed-service contracts, completion evidence, environment
  addresses and run-local API-use snapshots. Publication requires all completion
  flags; storage validates the supplied evidence and does not execute conversion.
- Added shared SQLite publication and lookup APIs. Published revisions are
  immutable and exact repeated publication is idempotent. Existing planned or
  assembled run records are not imported as completed services.
- Added `service_registry_path` to saved profiles, reusing `source_workspace_id`
  for application identity. Native profiles default to an application-specific
  database under `work/service_registry`, independent of the run output folder.
  Explicit relative paths resolve against the profile. Loading configuration
  does not create the database. Legacy profiles without registry settings retain
  their existing behavior.
- Added immutable API-use records to the existing run connection. These retain
  the selected contract revision and address for resume; no third database is
  opened. Shared and run database roles cannot be mixed by these storage APIs.
- Focused offline tests cover completion requirements, revision preservation,
  cross-run reuse, application/channel isolation and configuration resolution.
  Automatic publication and orchestration integration remain for later stages.

### Stage 2 — Dependency preflight inside intake

Invoke a focused preflight helper from the existing intake process after source
discovery and registry lookup. Preflight is part of intake, not a separate
runtime phase between intake and conversion.

Reuse Markdown call discovery and graph calculations. Retain enough source
inventory to resolve required targets beyond channel/include/exclude filters;
the conversion selection must not silently hide dependency evidence. Resolve
identities from evidence, never by guessing another channel's operation.

Traverse dependencies of operations still requiring conversion. An included
operation needs its required conversion evidence. A published service satisfies
the dependency boundary and supplies its trusted API contract. Otherwise block,
list the missing operation and call path, and ask the user to include or resolve
it. Detect cycles, display their complete path and evidence, and request user
resolution before planning proceeds. Do not expand scope silently.

Acceptance: intake fixtures cover direct/indirect and out-of-scope dependencies,
reused published APIs, unresolved targets and cycle blocking. Failed preflight
does not invoke code generation or allow approval to bypass the blocker.

Stage 2 implementation record:

- Native intake retains the full Mapper channel inventory while keeping the
  selected conversion operations unchanged. Legacy channel filtering is unchanged.
- Preflight traverses mapped direct and indirect calls, requires omitted
  dependencies to be included or published in the shared registry, and retains
  complete call evidence and actual cycle paths. It does not guess cross-channel
  identities, expand scope, or traverse the internals of reused published services.
- Missing target notes retain their exact target identity for registry lookup;
  unresolved or conflicting evidence still blocks. Included operations also need
  their referenced mapped format evidence.
- Save the result in the existing run database and readable Markdown/JSON reports
  under intake reports. Missing dependencies or cycles pause intake for operator
  resolution before planning preparation. Planning rejects recorded blockers
  before model invocation; existing runs without preflight records retain their
  previous behavior and are not silently upgraded.
- API contracts/revisions are reported as reusable; selecting and pinning an
  environment address belongs to the later approved planning integration.
- Offline tests cover direct/indirect missing paths, exact channel resolution,
  trusted API boundaries, missing notes/formats, cycle paths, long chains,
  persistence, planning rejection and the intake runner's blocking transition.
  No new approval gate, generation, publication or sequential wrapper was added.

### Stage 3 — Intake plan output and approval handoff

After preflight passes, calculate dependency-first waves and a stable explicit
operation order using existing graph tools. Reuse the current planner and report
infrastructure; enforce dependency constraints in deterministic plan validation.
Complexity, sharing, batching or pilot selection cannot place a caller before an
operation it requires. Waves describe dependencies, not parallel execution or a
claim that conversion effort is globally optimal.

Make the plan the primary user-facing intake result. Show scope, order, waves,
prerequisites and reused API identities. Persist the full plan and its dependency
evidence in the run database. Present the run-plan approval before entering the
thin wrapper, using the saved approval policy and existing decision machinery.

Bind acceptance to the displayed plan content, including scope, graph and reused
API revisions. A material change returns to intake checks and plan approval.
Keep the four existing per-operation gate settings separate; do not renumber or
replace them with this approval. Adapt the existing review/approve commands only
where necessary to identify the run-plan approval distinctly.

Acceptance: no operation begins before plan acceptance; human mode pauses,
automatic/skip policy records the corresponding decision, and changed plan
evidence requires renewed acceptance. Dependency failures always block.

Stage 3 implementation record:

- Native intake now uses the existing planner to produce the conversion plan,
  enforces a stable dependency-first order across and within batches, and saves
  readable Markdown plus complete JSON evidence as the primary intake result.
- A separately saved `plan_approval_policy` defaults to human review and supports
  the existing automatic/skip conventions. The existing approval engine stores
  the plan decision separately; conversion gates 1–4 retain their numbers and
  policies. CLI approval/rejection accepts `--gate plan` and menu discovery finds
  pending plan reviews.
- Approval binds the full plan, scope, graph, source-note evidence, published API
  contracts/revisions and approval policy. Changed evidence blocks resume and
  requires refreshed intake and renewed approval. Recorded dependency blockers
  cannot be overridden by approval.
- Resume handles the plan checkpoint without entering the old batch conversion
  path. Stage 4 supplies the sequential execution handoff. Existing runs without
  the new plan records keep their existing behavior.
- Focused offline tests cover order/waves, human/automatic/skip approval,
  rejection, changed evidence, CLI decisions, trusted APIs and safe resume.
  Two preexisting verbose CLI traceback tests fail identically using the saved
  pre-change CLI; those diagnostic paths were not altered.

### Stage 4 — Thin wrapper around the existing conversion workflow

Persist the current operation, its existing workflow phase and completion state
in the run database. Dispatch native runs through a thin wrapper which selects
one operation from the accepted plan and invokes the existing converter with an
operation-scoped execution view. Preserve the full accepted run plan; do not
create nested conversion runs or replace it with a new single-operation plan.

Make narrow entry-point/evidence changes where existing runners process all
selected operations. Reuse their generation, assembly, service packaging,
validation and finalization implementations. Supply trusted API-use records to
CCComplex client generation and preserve the target's request, response, error
and routing contracts. Avoid re-running target conversion validation on lookup.

Run the existing four gates for the current operation with their saved policies.
Scope reports and decisions to the operation and gate so a previous operation's
approval cannot approve a different one. Pending/rejected approval or a failed
existing conversion step pauses the wrapper. Existing correction limits remain;
do not add a new runtime verification loop or approval mechanism.

Only after the current operation's complete workflow succeeds, publish its full
service record, then persist its registry reference and completion checkpoint
before advancing. An interrupted registry/checkpoint write must be recoverable
without publishing a partial contract or reconverting an already completed
service. Mark the conversion run complete only when all selected operations are
complete, not when one operation's finalization returns successfully.

Acceptance: a controlled execution trace for A -> B -> C proves that C completes
its workflow, tests, gates and publication before any B conversion begins, and B
completes before A begins. Failure or a pending gate stops progression. Resume
retains completed operations, relevant approvals and accepted shared artifacts.

Stage 4 implementation record:

- Added a thin sequential coordinator and durable per-operation progress inside
  the existing run database. It invokes the existing native workflow using a
  one-operation execution view; the full accepted plan and run identity remain
  unchanged. Completed operations are skipped on resume. The executing plan's
  evidence is bound to progress; revised executing scope/evidence requires a
  revised run rather than silently resetting completed work.
- The existing four gates retain their policies and numbers. Approval hashes
  include the current operation, and operation reports live in separate folders
  under `operation_workflows`. CLI gate decisions use that current report folder.
  Status shows operation counts/current phase; Resume dispatches the wrapper.
- Narrow packaging/finalization integration scopes checkpoint comparisons to the
  current operation and records workflow completion without completing the whole
  run. Existing correction, testing and validation policies remain unchanged.
  Compatible shared artifacts retain their existing accepted reuse path.
- Publication requires completed packaging, validation/delivery evidence, intact
  package files and all four approved gates. Prepare publication in run state,
  publish idempotently to the shared registry, pin its API, then mark the operation
  complete before starting a caller. Interrupted publication resumes without
  reconversion and rejects changed prepared artifacts.
- CCComplex generation uses pinned published request/reply/error/address
  contracts. It checks the caller's binding without revisiting the callee's
  conversion source or tests. Unsupported target media types still block.
  Later registry revisions do not silently change an already selected API revision;
  selecting a new revision through refreshed intake requires renewed approval.
- Controlled offline traces verify C -> B -> A completion/publication order,
  stop/resume, gate isolation, crash recovery and CLI routing. Existing packaging
  and finalization fixtures exercise operation-scoped integration. No live model
  conversion, deployment or live HTTP-chain verification was performed here.

Stages 3–4 validation result: 140 focused tests passed (four older verbose
CLI-diagnostic cases excluded from that combined check). Separate broader CLI
checks reproduced eight existing interactive/documentation failures against the
saved pre-change CLI; the earlier two verbose gate-diagnostic failures were also
reproduced against that baseline. These unrelated failures were not repaired.
Live bank-demo conversion and cross-run integration verification remain Stage 5.

### Stage 5 — Development-time verification

Test stages 1–4 with deterministic fixtures and the existing converter test
infrastructure before live conversion experiments. These tests verify the new
storage and coordination code during development; they are not an added stage
inside a conversion run and do not change operation-test policy.

Cover missing dependencies/cycles, approved order, gate settings and scoped
decisions, publication readiness, failure interruption/recovery, Resume, and two
different runs reusing a published service. Run focused regressions for the
existing entry points and legacy dispatch affected by integration changes.

After those checks pass, use the existing three-operation bank example for a
limited sequential verification and a separate-run API-reuse check. Report which
operations completed and the exact remaining blocker. Existing generator or
business-conversion failures must not turn this task into unrelated debugging.
Do not add a requirement to launch every service or enumerate every possible
chain in a large conversion run.

Stage 5 verification record:

- Added a real-bank Mapper/intake integration test using two independent run
  databases and one shared fixture registry. Explicitly controlled converter
  fixtures verify leaf completion/publication before the later run's callers,
  exact API revision reuse, actual CCComplex call resolution and both direct
  targets of the overview operation. These are not claimed as real services.
- The combined focused suite passed 141 tests (four preexisting diagnostic cases
  excluded). The added verification-timeout checkpoint test also passed, proving
  accepted work survives pausing an interrupted verification run. The real-bank
  integration test was rerun successfully after its JDK availability guard.
- Added `work/stage-five-validation/verify_bank_demo.py`, an isolated live-run
  supervisor with an eight-minute cap, captured CLI output, explicit demo-only
  deployment values, automatic test-profile approval policies and one transport
  attempt. Existing conversion correction limits remain in place. Original
  profiles and runtime conversion code were not changed.
- Live run `chain-be7749`: real intake and model-driven planning passed. Only
  `GetClientLinksOp` began. Two of its seven native units passed compilation,
  executable tests and review. The cap stopped conversion during dependency
  verification of unit 3 (`TechnicalError`); accepted units and the approved
  plan were retained, and the stopped run was marked paused at
  `conversion_pending`.
- Completed dependency-verification steps consumed 130.7 and 144.7 seconds.
  Neither `ValidateClientLinksOp` nor `GetClientOverviewOp` started. No operation
  completed, no service was published, no live HTTP-chain check ran, and the
  separate live API-reuse run was not started. No dummy validation or unrelated
  generator/build repairs were used. No second live attempt was made.
- Evidence: [verification summary](../../work/stage-five-validation/verification.md),
  [live report](../../work/stage-five-validation/live-20261019-173555-be7749/report.md)
  and its machine result/logs. Completing the real bank conversion and separate
  live reuse check remains outstanding; verification is not marked fully passed.

## Expected files to change:

The following paths are the expected implementation surface. New paths are
proposed, not files created by this documentation task. Keep responsibilities
small and confirm each increment's exact edit scope before implementation.

### New focused modules

- [converted_service_contract.py](../../source/models/converted_service_contract.py): published API record.
- [registry.py](../../source/tools/converted_service_registry_tools/registry.py): shared registry storage, lookup and publication.
- [preflight.py](../../source/tools/operation_call_tools/preflight.py): dependency-scope checks invoked by intake.
- [operation_coordinator.py](../../source/runtime/operation_coordinator.py): thin sequential wrapper only.
- [operation_progress.py](../../source/tools/state_store_tools/operation_progress.py): operation checkpoints and API-use records in the run database.

### Existing integration points

- [pipeline_configuration.py](../../source/models/pipeline_configuration.py): registry/application settings and saved run-plan approval policy.
- [pipeline_runner.py](../../source/runtime/pipeline_runner.py): intake discovery, preflight and final plan output.
- [discovery.py](../../source/tools/operation_call_tools/discovery.py): only the call-evidence extension required for out-of-scope targets.
- [planning.py](../../source/runtime/planning.py) and [plan_validator.py](../../source/agents/migration_planning/plan_validator.py): reuse planning with enforced dependency order.
- [conversion_strategy.py](../../source/runtime/conversion_strategy.py) and [checkpoints.py](../../source/runtime/checkpoints.py): dispatch and Resume through the wrapper.
- [runner.py](../../source/runtime/behavior_conversion/runner.py): current-operation entry-point integration, preserving conversion implementations.
- [service-generation runner](../../source/runtime/service_generation/runner.py), [operation evidence](../../source/runtime/operation_review/evidence.py) and [finalization runner](../../source/runtime/finalization/runner.py): scope the existing stages and evidence to the current operation.
- [operation_call_closure.py](../../source/tools/conversion_tools/operation_call_closure.py), [operation_calls.py](../../source/runtime/behavior_conversion/operation_calls.py) and [run contract storage](../../source/tools/state_store_tools/operation_calls.py): bind published API-use records without repeated target validation.
- [human_gates.py](../../source/runtime/human_gates.py), [gate_decisions.py](../../source/cli/gate_decisions.py) and [workspace_paths.py](../../source/runtime/workspace_paths.py): distinguish run-plan approval from the existing operation gates and scope review evidence correctly.

### Focused tests

- [test_service_registry.py](../../source/tests/test_service_registry.py) (new): two-run publication and lookup.
- [test_operation_preflight.py](../../source/tests/test_operation_preflight.py) (new): intake dependency and cycle blockers.
- [test_operation_coordinator.py](../../source/tests/runtime/test_operation_coordinator.py) (new): ordering, gates, interruption and Resume.
- Extend existing [planning](../../source/tests/runtime/test_planning_execution.py), [conversion](../../source/tests/runtime/test_behavior_conversion.py) and [service-generation tests](../../source/tests/runtime/test_service_generation.py) only for changed integration behavior.

## Delivery discipline

Complete and report each development stage before starting the next. Preserve
unrelated local changes. No general refactoring, new conversion pipeline, gate
renumbering, broad model-driven test campaign, automatic deployment or deletion
of Composer operations belongs to this implementation.
