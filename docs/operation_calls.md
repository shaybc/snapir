# Calls between Composer operations

An `opStep` with implementation `com.ibm.il.dse.cc.cut.CCComplexOpStep`
invokes the operation named in `opExecuteName`. The step ID is arbitrary.
Composer Mapper retains these attributes in step Markdown; the target is a
parameter string rather than an operation hyperlink.

## Implementation status

Call discovery, dependency-wave calculation, Excel export and initial native HTTP
adapter generation exist. The complete workflow specified below is the agreed
design and is not yet fully implemented. The current runner still performs work
across selected operations before packaging; its contract storage is run-scoped.
Neither those stage barriers nor a planned API record satisfies this design's
requirement to finish a dependency service before starting its callers.

The delivery stages and expected code surface are recorded in the
[staged implementation plan](plans/operation_conversion_workflow_implementation_plan.md).

## Discovery

Vault import follows operation Steps links (standard Markdown or Obsidian),
matches the implementation class and resolves the target in the caller's channel.
It stores the graph in `operation_call_graphs` and native XML HTTP contracts in
`operation_service_contracts`. Neither conversion nor scheduling reads Excel.
Repeated call sites retain evidence, while operation counts count unique edges.
Current discovery resolves names in the caller's channel. The scope check below
must identify calls outside the selected operation/channel set from explicit source
evidence or trusted registry identity; it must not guess another channel's target.

Every channel has XML as its implicit base, with local definitions taking precedence. In shared schema-three vaults, Mapper follows only referenced inherited operations and emits each source definition once. `SME/IDBGetUserDataOp` calling XML-defined `POB1Op` links to `channels/XML/operations/POB1Op/operation.md`, with the consuming-channel connection recorded separately. A local SME operation override changes the selected source; SME resource overrides and `onlyFor` change contextual dependencies without copying XML notes.

Both Excel generators consume the manifest's `operation_contexts` records, including resolved call targets. Reachable channel-specific contexts remain separate graph identities for correct waves and cycles but share source notes. They do not require physical inherited views, search unrelated channels or invent target resolution. Legacy and schema-two discovery remain supported. Regenerate a fresh vault to adopt schema three; converter support remains unimplemented and rejects this new schema explicitly.

## 1. Validate the entire job scope

Run these dependency checks inside intake, after discovery and shared-registry
lookup. Intake's final user-facing result is the conversion plan, or actionable
blockers when planning cannot proceed. Preflight is not a separate runtime phase.

Before pilot selection, plan approval or code generation, follow every direct and
indirect CCComplex operation call reachable from the requested operations. This
applies to a whole channel or an explicit list, not just to a pilot. Intake must
retain enough evidence to find targets outside the selected scope; channel and
include/exclude filters must not silently hide required operations.

Each called operation must satisfy one of these conditions:

- It is included in this job, with the evidence required for conversion.
- It has a successfully converted, published API record in the shared registry
  database. Records from previous jobs must be discoverable, not restricted to
  the current run.

For an existing converted dependency, show the user which service and published
contract will be used, and bind the job to that contract. Trust the successfully
converted record; do not repeat the target's conversion validation for each
caller. A draft, planned interface, assembled-only operation or failed conversion
does not count as a reusable completed service.
Treat a trusted published service as a satisfied boundary; do not reopen its
internal conversion dependency tree for each new caller. Traverse the remaining
operations that still require conversion to discover their indirect prerequisites.

Otherwise block before conversion. List every missing operation, its known
channel identity and the call path that requires it, then ask the user to include
it in the job. Do not silently enlarge the selected scope. Missing source evidence,
dynamic targets and ambiguous identities also block with actionable details.
After the user supplies the missing scope/evidence, repeat the scope check.

There is no ignore option, null-return substitute or generated placeholder for a
missing operation dependency. Test fixtures are a separate testing concern; they
do not satisfy the production conversion scope.

Detect cycles in the required conversion graph during this check. If found, block,
display the complete cycle and its call-site evidence, and ask the user to resolve
the dependency or correct its mapping. Recalculate the plan after resolution.
Do not invent an order or automatically convert a cycle as one group.

## 2. Present the order and waves for approval

Once scope validation passes, calculate dependency-first conversion waves and an
explicit execution order. A caller follows every dependency being converted in
the job; previously completed external services are reused. Shared Java classes
and formats alone are not operation-call edges.

Show the full job scope, waves, operation order, direct prerequisites and reused
services. A pilot, if used, must respect this same dependency order; complexity,
batch size and component sharing cannot place a caller before its prerequisites.
Waves describe dependency layers, not concurrent execution or an estimate of the
minimum conversion effort.

Present intake's final plan for approval once for the conversion run, before the
thin wrapper invokes conversion. Reuse the existing approval machinery with a
separately saved run-plan policy, defaulting to human review. Automatic or skipped
human approval follows that setting. This approval is separate from the four
gates inside each operation's existing workflow; do not renumber those gates.
Persist the accepted scope, graph, order, waves, API references and plan-approval
evidence for Resume. Material scope/dependency changes require a revised plan
and renewed acceptance. Dependency blockers cannot be skipped.

## 3. Complete one microservice before its callers

For A calling B calling C, complete C, then B, then A. Each operation goes through
the existing conversion lifecycle to completion: convert its required formats,
steps and supporting code, assemble the native flow, generate and package its
service, run the existing required tests/validation and reviews, then publish its
API contract and completion checkpoint. Only then start the next operation's
conversion. Generating all callers' units first and packaging after the whole
batch passes does not meet this rule.

Implement this as a thin sequential wrapper around the existing conversion
workflow. It selects the next approved operation, supplies its resolved service
contracts, invokes the existing workflow to completion, records/publishes the
result, then advances. Reuse the current conversion, assembly, packaging, tests,
review and correction implementations. Make only the integration changes needed
to invoke them for the current operation; do not duplicate or invent a second
conversion pipeline.

All four existing gates belong to each operation's conversion invocation. Keep
their numbers and current human, automatic or skip settings. They follow the
separate run-plan approval after intake. Each operation's reports reference the
accepted plan and identify its operation scope. Approval evidence identifies
the operation and gate, so approval of one operation cannot approve another.
All-human settings can require four decisions per operation, in addition to the
single run-plan approval. Automatic or skipped human approval never bypasses
failed technical checks, missing dependencies or cycles. A pending or rejected
gate pauses the current operation; the thin wrapper does not advance.

Configured CCComplex steps become HTTP clients using the completed target's
published contract. They do not copy the Composer dispatcher or inline the target
business logic. Map caller values into the target request, and map its response,
errors, return outcomes and timeouts back into the caller's established flow.
Unknown mappings block acceptance through unresolved questions.

The acceptance boundary remains the converted microservice: its input, output
and error behavior, including its required service calls. Reuse the existing
operation-testing process; do not introduce a separate job-wide test that starts
every service or enumerates every call chain. Mock and runtime-test configuration
are separate follow-up work, not changed by this design update. Existing bounded
generation corrections and validation policies remain in place.
The wrapper's development-time tests are described in the staged implementation
plan; they are not an added verification stage inside a conversion run.

If an operation fails, stop at its checkpoint, report the blocker and retain
completed operations. Do not start dependent callers or mark the failed operation
complete. Resume continues the approved plan using completed services and saved
work; it does not revalidate each completed target merely because another caller
uses it. Keep Composer retirement separate from native implementation.

## Storage ownership: run database and shared registry

Use exactly two database roles: one database per conversion run and one persistent
shared registry database for the source application being migrated. Keep the
shared registry outside individual run directories. All channels and business
modules of that application use the same registry across runs.

| Database | Owns |
|---|---|
| Per-run database | Selected scope, dependency graph, approved plan, progress, attempts, validation evidence, drafts and completion checkpoints; records of the published API contracts used by this run |
| Shared registry database | Successfully converted operation-to-microservice mappings and the complete published information needed to call each service |

Identify registry entries by source application, channel and operation, with the
published API revision. Store the microservice/artifact identity, request/response
contract, errors, route and address configuration together with the publication
evidence. Keep environment-specific URL/port values or configuration references
associated with the appropriate environment. A Swagger/OpenAPI link may accompany
the saved API definition; a link alone does not replace the stored call contract.
Planned interfaces and incomplete conversions stay in run state, not in the
registry's successfully converted entries.

Each new run consults the same shared registry during dependency preflight. For
every reused service, record its registry identity, exact published contract
revision, contract data used and selected address configuration inside that run's
existing database. This is the API-use snapshot: it is a record, not a third
database or a copy of all prior runs. Resume uses the recorded contract rather
than silently switching to a different revision. Normal lookup trusts the
published record without repeating the target's conversion validation.

After an operation completes its required lifecycle, publish its complete record
to the shared registry and record that publication and completion checkpoint in
the run database before advancing. Later jobs can then reuse the service without
merging or searching old run databases. Archiving a run must not remove its
published service from the shared registry.

## Trusted API publication

Publish a successfully converted service record only after its complete existing
conversion and required validation/approval lifecycle passes. Store its source
application, operation and channel identity, service artifact and API revision,
HTTP method and route,
request/response structures and parameters, supported media types, error/outcome
mapping, and deployment address configuration (including URL/port when known).
Save the completion evidence and publish the complete reusable registry record.
Persist its reference and the completion checkpoint in the run database before
advancing; both writes must support recovery after interruption. Planned
interfaces may be stored separately in run state, but cannot release callers for
conversion or satisfy scope validation.

The current native contract uses POST `/operations/{channel}/{operation}`,
application/xml and mapped request, reply and error formats. JSON structures belong
in the record when JSON is actually supported; this change does not add JSON
conversion. The target host is supplied through `base_url_property` as deployment
configuration, not a hardcoded generated address. Successful conversion does not
itself claim production deployment or guarantee runtime availability.

The current `operation_service_contracts` states are `planned`, `assembled` and
`validated`. Their current implementation must not be presented as proof that this
full publication lifecycle is already implemented. The revised workflow needs
the separate shared registry database described above, alongside run-local
graph/task state and API-use snapshots in each existing run database.
Readiness changes alone are not API changes and must not regenerate callers.
Actual contract changes continue to use the existing invalidation/review rules;
normal reuse does not repeat conversion validation of a published dependency.

The class-by-class legacy strategy currently blocks these calls; use
`behavior_units` for native HTTP replacement. It must never claim that converting
the dispatcher alone completes the invoked operation's business behavior.

## Searchable implementation plan

Run from the repository root after generating the Mapper vault:

```powershell
python source/export_operation_migration.py --vault path/to/vault --output migration-plan.xlsx
```

The default workbook contains Migration Plan (waves, direct prerequisites, cycle
groups and issues) and Operations (unique direct caller/callee counts). Optional
`--include-relationships` adds call-site evidence. Problems get an Issues sheet;
affected operations and their transitive callers receive no wave. Project managers
can add their own progress columns. A cycle's wave describes its group, not an
order among its members. Waves and call counts are not estimates of effort.
An operation needs its own prerequisites, not every operation in all earlier waves.
Cycle groups have stable IDs; filtering either main sheet by an ID shows its members.

The command requires Python with this project's dependencies, Node.js and
`@oai/artifact-tool`. It discovers the bundled Codex Node runtime when available;
otherwise it uses Node on PATH. For another installation supply `--node` and
`--artifact-modules` (the directory containing the `@oai` package folder).
The command reads Markdown only and does not modify the vault or converter database.

Keep the Composer implementations until their remaining callers and incoming
traffic have moved. Implementation order and Composer retirement are separate.

## Changed code areas

- `tools/operation_call_tools/discovery.py` reads the Markdown call evidence;
  `ordering.py` calculates waves and cycle groups; `excel_report.mjs` writes Excel.
- `export_operation_migration.py` is the single report command.
- `tools/state_store_tools/operation_calls.py` owns graph and HTTP-contract persistence.
- `tools/composer_mapper_tools/vault_importer.py` saves discovered calls during import.
- `agents/migration_planning/agent.py` and `runtime/planning.py` supply dependency waves to planning.
- `tools/conversion_tools/operation_call_closure.py` resolves target contracts;
  `closure_builder_tool.py` attaches them to `models/conversion_models/conversion.py`.
- `models/behavior_unit.py` and `tools/conversion_tools/behavior_unit_builder.py` carry
  call evidence into configured-unit conversion and its reuse identity.
- `runtime/behavior_conversion/operation_calls.py` owns client, endpoint and freshness
  checks. Its runner, generation, compatibility and evidence modules pass those
  requirements through existing conversion, testing and review gates.
- `runtime/service_generation/runner.py` orders generated services and validates
  their public route and configured target hosts.
- `tests/test_operation_calls.py` covers discovery, persistence, waves, converter
  safeguards and the real bank-demo Mapper/Java integration.

The bank demo adds ValidateClientLinks.xml, GetClientOverview.xml and a demo
CCComplexOpStep.java, registers the two operations in INTERNET/dse.ini and documents
the chain in its README. Existing operation XML files and retirement behavior are unchanged.
