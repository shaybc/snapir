# Snapir Behavior Verification Design Plan

Oct 27, 2026 · @shay

Replace the AI-written behavior facts with a checklist that a Java parser builds from the original methods, and accept a unit only when deterministic checks and a boundary comparison against the legacy code pass. The AI keeps generating the code; it no longer decides what the obligations are or whether they were met.

Scope: format, unformat and operation-step units produced by the scoped native pipeline (`scoped_native_mode = behavior_units_v1`). Composer Mapper stays unchanged. Production log replay is optional and later; nothing in the unit gate depends on logs.

## Problem

The last run (`bank-demo-c9-unit-evidence-20261026`) stopped on unit 1 of 83, `GetAccountDetailsRQFmt`, with `Candidate must map every behavior fact to its implementation`.

- **The facts were not scoped to the unit.** The AI extracted 15 facts, one per public method of every supplied class. For a `request_unformat` unit, 6 were format-direction methods that do not apply, and the 4 `initializeFrom` facts were setup the prompt forbade recreating.
- **The gate could not be passed.** `validate_implementations` requires all 15 facts to be mapped, while the generation prompt forbids recreating `initializeFrom` and `addDecoration`.
- **The mapping is self-reported.** The code implemented 3 more of the 5 unformat-side facts but the AI mapped only 2, the two helpers that were near-copies of the source.
- **Retries had no signal.** The correction feedback did not name the missing fact IDs; three corrections returned the same 2 mappings.
- **Details inside a method are not checked.** A changed `xsi:nil` prefix, a different literal or a dropped branch passes every current gate if the AI's own review misses it.

At production scale (hundreds of formats, thousands of operation steps, all different) both extraction and review stay AI judgments with no ground truth. A per-class manual catalog is not feasible either.

## Target design

Flow (diagram in the online doc):

1. Composer Mapper (unchanged): configuration and classes
2. Reachable slice: conservative, from the entry point and setup
3. Parser checklist: literals, branches, calls, writes
4. AI generation: code plus an answer per checklist item
5. Static checks: mapping, exclusions, literals, XML shape
6. Build and tests: compile, tests, import guard
7. Boundary comparison: legacy vs generated, outputs and effects
8. Accepted unit, or Verification incomplete

Any failing check retries generation with the failing item IDs and inputs.

Only code decides the obligations (steps 1-3) and the checks (steps 5-7); the AI is used only to generate the code. A unit that the harness cannot run ends as Verification incomplete, never as accepted. Any failure goes back to generation with the exact items and inputs that failed.

## Components

Composer Mapper is unchanged; its output (configuration, classes and dependencies per operation) is read-only input. All new analysis lives in the converter, as a converter-side Java analysis tool (JavaParser with symbol resolution) called by the scoped native pipeline. Generation and the optional triage review are the only AI steps.

### 1. Unit boundary

The converter derives each unit's boundary from Mapper output: the framework entry point for the unit kind, and everything observable at that point.

| Unit kind | Legacy entry point | Inputs | Observable results |
| --- | --- | --- | --- |
| request_unformat | `unformat(String xml, Context)` | request XML, context values read | context values written, exceptions |
| response_format | `format(Context)` | context values read | response XML, exceptions |
| operation step | the step's execute method | input fields, context values read | context changes, exit/routing value, exceptions, external calls |

The entry-point table is per framework interface, not per class, so it stays small. The generated code may split, merge or inline methods freely; only the boundary is compared.

### 2. Reachable slice (conservative)

From the entry point and the unit's initialization path, follow calls through the configured classes, their parents and helpers (call graph plus class hierarchy). Where a call target cannot be resolved exactly (interface or overridden method, reflection, class names from configuration), include every candidate implementation and mark the edge uncertain.

Over-inclusion is safe: an item outside the unit's behavior is excluded later with a supported reason (component 5). Runtime tracing in the harness may add methods the static analysis missed, but never removes any: a trace only shows the paths the chosen inputs exercised.

### 3. Initialization behavior

Setup is part of the unit's behavior, not only its XML attributes. The slice includes constructors, field and static initializers, parent setup and `initializeFrom`, and the checklist covers:

- defaults when an attribute is missing (for example `pattern` defaulting to `yyyyMMdd`)
- derived values (parsed lengths, first character of `padChar`, case-insensitive flags)
- validation and exceptions raised during setup

The harness runs the real initialization with a `Tag` stub built from the unit's XML, so the comparison sees the effective values. The generated code may hold them as constants or configuration; it does not recreate `initializeFrom`.

### 4. Parser checklist

The analysis tool walks the slice and emits items with stable IDs and a certain/uncertain path flag:

- **Literals and constants:** strings, numbers, characters and referenced static constants.
- **Branches:** every `if`, `switch` case, ternary, loop guard and `catch`, with its condition text.
- **External calls:** database, service, file, settings and logging calls, with their arguments.
- **Writes:** output values, attributes, elements and context fields written or removed.
- **Exceptions:** thrown, caught, wrapped or swallowed.
- **Initialization effects:** from component 3.

The list is long but cheap, and nobody reviews it by hand.

### 5. Generation contract

The AI receives the slice source, the configuration and the checklist. For each item it returns one of:

- `implemented`: file and exact excerpt, anywhere in the code; one excerpt may cover several items.
- `not_applicable`: one reason from a fixed list that code can check, such as other-direction code, a branch fixed off by this unit's configuration, an uncertain call target that this configuration cannot select, or framework plumbing on an approved list.
- `unresolved`: a question for a person.

A `not_applicable` without a supported reason fails, even when sample outputs match. The only other way through is an explicit exception approved by a person and stored with the unit.

### 6. Check ladder

1. **Schema and mapping:** every checklist ID is answered; every excerpt exists in the generated files.
2. **Exclusions:** every `not_applicable` has a supported reason or an approved exception.
3. **Supporting static checks:** literal check and structural XML check (names, nesting, order, attributes, namespaces). These are signals, not proof: a missing literal becomes a warning plus targeted comparison inputs for its path, since equivalent code may build it differently; a present literal verifies nothing.
4. **Build and tests:** compile, unit tests, forbidden-import guard (existing).
5. **Boundary comparison:** component 7. Required for acceptance.

Each unit ends in one of three states:

| State | Meaning |
| --- | --- |
| Accepted | Steps 1–5 pass, including the comparison |
| Verification incomplete | The harness cannot run the unit, or `unresolved` items remain; never accepted on static checks alone |
| Failed | Any step fails after the retry budget |

Correction feedback always lists the failing item IDs and the failing inputs.

### 7. Boundary comparison

Run the legacy entry point and the generated public method on the same inputs and compare every observable result:

- **Outputs:** returned values and XML after normalization of attribute order and explicitly insignificant formatting only. Preserve significant text whitespace, element order, namespace URIs and prefixes, and missing/empty/nil distinctions; normalization must not hide a behavior difference.
- **Context changes:** keys written or removed and their values.
- **Failures:** whether an exception occurs, its type, and the resulting state.
- **External business calls:** target, arguments, count and order remain strict. Responses recorded once are replayed to both sides; one adapter per external kind (stored procedure, HTTP service) maps legacy calls to the generated collaborators. Recognized logging events are compared separately under the policy below.

#### Logging comparison policy (implemented 2026-10-31)

Both implementations receive the same test input and runtime controls. For each case, compare the number of recognized log events at each severity. Missing or extra events and changed severity block acceptance. This count-by-severity comparison does not require pairing events by message text or order.

Message wording, input values embedded in messages, IBM/native class names (including names inside message text), logger identity, logging-method overloads, attached exception type/message and event ordering differences remain visible diagnostics, but do not block conversion. No class-name rewriting or deliberate recreation of legacy exceptions is required. This is a reduced logging check: matching counts and severities does not prove equivalent message content or that each warning describes the same condition.

Retain both complete raw event sequences in the report. Label blocking logging differences separately from non-blocking diagnostic differences, and record the comparison-policy version. Only recognized harness logging events receive this policy; unknown events and database, service, file and other business calls retain existing strict checks. Exceptions escaping the selected unit remain subject to the existing failure comparison.

Correction feedback requests only the missing/extra event count or changed severity for the concrete input. It must not ask the AI to reproduce IBM logger names, message wording or JVM exception details merely to satisfy comparison. Diagnostic-only differences do not consume correction attempts. Existing XML/prefix, returned-value, context, routing, build and coverage checks remain unchanged.

Implementation steps:

1. Add a focused logging-event comparison helper and call it from the shared boundary comparator. Keep raw observations unchanged.
2. Record the logging policy in comparison reports and preserve diagnostic-only differences outside the blocking differences supplied to correction.
3. Add regression tests before rerunning the response-format boundary. Equivalent severity/count with changed wording, embedded IBM/native names, exception details, logging overloads or order must pass the logging gate and retain diagnostics. Missing/extra logs or changed severity must fail. Changed embedded input values must remain reported even though they do not block under this policy. XML prefixes, business-call targets/arguments/order and escaped exceptions must retain their existing checks.
4. Rerun StandardErrorRSFmt only and report build, JUnit, comparison and diagnostic outcomes separately; do not infer whole-operation acceptance.

Expected implementation files: `source/tools/behavior_verification/boundary_logging.py` (new helper), `boundary_comparison.py` (shared comparison), `thin_path_comparison.py` and `boundary_comparison_report.py` (policy/diagnostic reporting), and focused comparison regression tests. Wire diagnostic reporting through the existing report producers without changing generation prompts, retry limits or original sources. This section supersedes earlier exact logging-argument/order comparison requirements; historical implementation checkpoints below remain records of prior behavior.

The legacy side is a plain JVM harness that loads the original classes with stubs for `Context`, `Tag` and framework settings, with no WebSphere or Composer server.

Both sides receive the same controlled clock, random seed, initial settings and external responses. Reset mutable state between cases and record these controls with each failing input so the case can be reproduced. A dependency that cannot be controlled or replayed leaves verification incomplete rather than producing an unreliable comparison.

Inputs are generated automatically: values from branch conditions and literals (null, empty, boundaries, each enum value), configuration-driven values per field, and random inputs (EvoSuite or Randoop style). Production log values are added when available but are never required.

Record the exercised legacy branches, observed paths and checklist IDs, along with unexercised branches and unresolved paths. Input count alone is not coverage evidence. Acceptance records must show the achieved coverage and remaining gaps; passing comparisons do not establish equivalence for untested paths.

Every difference names the input, the result that differs, and the checklist items on its path.

### 8. Test strength report

PIT mutation testing on the generated code measures how strong the generated tests are. It does not prove equivalence and is not an acceptance gate; a weak score asks for more tests.

### 9. Optional AI triage review

A second model with a fresh context sees the checklist and the generated code and flags likely gaps. It is used to prioritize human review, never to accept or reject.

### 10. Production log replay (optional, later)

When logs with full request and response bodies are available, replay them against assembled operations with equivalence rules. Their absence does not block the unit gate or the initial implementation.

## What to remove or change

The AI fact pipeline is removed as a gate; generation, build, test and assembly stay.

| Current part | Location | Action | Reason |
| --- | --- | --- | --- |
| AI fact extraction (`EXTRACT`, `RECONCILE`, `extract_behavior`, `attach_behavior_specification`) | `runtime/behavior_conversion/behavior_extraction.py`, `agents/behavior_conversion/behavior_extraction.py` | Remove | Replaced by the parser checklist; unscoped and unverifiable |
| Fact citation checks (`validate_specification`) | `behavior_fact_validation.py` | Remove | Checks citations of AI facts that no longer exist |
| `validate_implementations` (all facts must be mapped) | `behavior_fact_validation.py`, called from `generation.py` | Replace | Becomes the checklist mapping check with `not_applicable` and missing-ID feedback |
| AI behavior comparison as approval (`compare_behavior`, `COMPARE`, `validate_comparison`) | `behavior_comparison.py`, `review.py` | Demote | Optional triage only; acceptance comes from the boundary comparison |
| Review-driven revision loop | `revisions.py` | Change | Loop on check-ladder failures (item IDs, failing inputs) instead of AI review findings |
| "Implement every behavior_specification fact" instruction | `revisions.py`, unit prompts in `agents/behavior_conversion/` | Replace | Instruction to answer every checklist item |
| `behavior_specification`, `behavior_evidence` payload fields | generation and review payloads | Replace | `slice_sources`, `checklist`, `boundary` |
| Per-unit source selection by class | scoped closure (`tools/conversion_tools/scoped_closure`) | Narrow | Send the reachable slice for the unit's direction, not whole classes |
| `behavior_context_chars` = 300000 sizing | run profile | Revisit | Slices are smaller; fewer split parts |
| Generic correction feedback text | `correction_payload.py`, `corrections.py` | Change | Always name failing checklist IDs and inputs |
| Unit acceptance (`scoped_acceptance`) | `runtime/scoped_acceptance.py` | Change | Accept on check ladder + boundary comparison results |
| Golden tests against a live WSBCC host (`GOLDEN_TESTS_ROOT`, `LEGACY_SERVICE_BASE_URL`) | `docs/architecture_v3.md` constants | Optional, later | Becomes optional operation log replay; never blocks the unit gate |

Kept as is: Composer Mapper (read-only input to the new converter analysis), wave ordering of operations, Java toolchain and build, forbidden-import guard, testing contract, operation assembly.

## Implementation plan

Build the deterministic parts first and prove them on the unit that failed before touching the pipeline.

1. **Converter analysis tool and boundaries.** Add the converter-side Java analysis tool; derive per-kind entry points and boundaries from Mapper output.
   - Exit: all 83 bank-demo units have a recorded boundary; no Composer Mapper code changed.
2. **Conservative slice with initialization.** Call graph plus class hierarchy from the entry point and the initialization path; uncertain edges keep every candidate.
   - Exit: for `GetAccountDetailsRQFmt`, every method the harness traces is in the slice, the setup of each configured formatter and decorator is included, and each uncertain edge lists its candidates.
3. **Parser checklist.** Literals, branches, external calls, writes, exceptions, initialization effects, with stable IDs and path certainty.
   - Exit: the checklist for a response format using `NilDecorator` contains `xsi:nil`, both settings conditions, the null/empty check and the caught exception; the `CCDate` setup items include the `yyyyMMdd` default.
4. **Legacy harness and boundary comparison.** Stubs for `Context`, `Tag` and settings; recorded external calls; generated inputs; comparison of outputs, context changes, exceptions and external calls.
   - Exit: `GetAccountDetailsRQFmt` is compared on 50+ generated inputs with a per-field report, reproducible clock/seed/settings/external-response controls, and exercised/unexercised branch and path coverage. The input count alone does not satisfy this exit check; a unit the harness cannot load or whose dependencies cannot be controlled ends as Verification incomplete. XML normalization is tested to preserve significant text whitespace, prefixes and missing/empty/nil differences.
5. **Exclusion and supporting static checks.** Mapping, exclusion reasons, literal and XML structure checks.
   - Exit: an unsupported `not_applicable` is rejected even when sample outputs match; a missing literal produces a warning and targeted inputs, not a pass or a fail by itself.
6. **Seeded-defect suite.** Plant defects in correct generated code and confirm the comparison catches each one.
   - Mandatory validation removed: empty `ClientId` no longer raises the legacy failure.
   - Null-to-zero removed: empty `MaxTransactions` no longer becomes 0.
   - Conditional nil output changed: nil always or never added, a settings condition ignored, or the prefix changed to `wtc:nil`.
   - Padding removed from the wrong side.
   - Exit: every seeded defect is reported with its failing input.
7. **Pipeline switch.** New generation contract, check ladder in place of `validate_implementations`, revision loop on ladder failures, AI comparison demoted to triage.
   - Exit: a fresh bank-demo run ends every unit as Accepted, Failed or Verification incomplete; the old fact gate is removed.
8. **Test strength report.** PIT on accepted units.
   - Exit: a report per unit, labeled as test strength, not equivalence.
9. **Production pilot.** A sample of real formats and operation steps of different shapes (for example 20 of each); log replay only where logs exist.
   - Exit: acceptance rate, Verification incomplete rate and its causes, and literal-warning rate are measured.

## Implementation status — 2026-10-27

Phase 1 is implemented as converter-side boundary discovery. The separately built
`source/behavior-verification-java` tool uses JavaParser 3.28.2 and its symbol solver
to identify exact public instance entry methods, including inherited implementations,
from isolated snapshots of the unit's supplied Java evidence. It records declaring
classes, signatures, original source identities/hashes, file paths and line ranges.
It parses source without executing original classes or their static initializers.
The analysis tool runs on the converter's supported Java 21 and Java 25 profiles.

Build the tool before running analysis:

```powershell
mvn -q -f source/behavior-verification-java/pom.xml package
```

Scoped preparation writes `behavior_verification_boundaries.json` beside
`scoped_workflow_preparation.json`. It includes the boundary inputs/result channels,
configured setup class roots and configuration/source fingerprints. Missing tools,
unavailable source methods, parse failures and ambiguous method selection are recorded
as incomplete analysis. The original preparation and native acceptance gates are unchanged.

A fresh bank-demo Mapper/intake/preparation run identified all 83 configured entry
points across 10 operation contexts. Phase 1 established boundary discovery only.

Phase 2 adds a conservative, source-bound call graph for each entry and configured
setup. Nodes include constructors, inherited initialization, XML/property setter
candidates, tree/decorator registration, field defaults, explicit field initializers
and initializer blocks. Method calls, method references, generic overrides and
implicit cleanup/iteration/string-conversion calls retain compatible supplied bodies.
Opaque library callbacks and reflection keep candidates and explicitly record that
the supplied evidence may not bound every runtime target. Recursive calls terminate
through visited node identities; no original workspace classes are loaded by analysis.

Each node and source call site retains its original identity, hash, excerpt and line
range. The Python reader rejects invalid provenance and dangling graph references.
`path_certainty` describes a statically resolved route, not proof of execution.
Unresolved or unbounded edges remain `verification_incomplete`, even with zero known
candidates; analysis never silently excludes them or treats them as verified.

Phase 2 tests include actual JVM traces of disposable original sources and the bank
request setup/unformat path. These check that observed methods are retained; they
do not establish complete path coverage or native/legacy output equivalence.
All 24 observed bank-request methods are retained, including configured initialization,
decorator registration, mandatory checks, padding removal and null-to-zero handling.
All 83 bank-demo units across 10 operations have populated graphs: 41 are statically
analyzed and 42 explicitly retain incomplete/unbounded resolution. The report lists
2,267 uncertain edges, including 76 unbounded edges; these counts are not failures
of native conversion or a behavioral acceptance result.
Validation passed: 43 boundary/reachability/workflow tests plus all 3 bank-demo
source/integration tests. The fresh integration test remaps the demo and checks every
unit graph before running the original request trace; it makes no AI model calls.
The bank-wide report retains `runtime_tracing_status: not_run` because the report
itself is produced by static analysis, separately from those test traces.

Phase 3 adds a parser-produced checklist to each boundary in the same report. Focused
Java helpers enumerate literals (raw source plus decoded string/character/text-block
values), static field references, branch/loop/short-circuit/switch guards, calls and
ordered arguments, assignments and return/yield values, exception syntax and setup
effects. Default field values are identified as Java initialization rules, not
invented literal text. Original source hashes, ranges, excerpts and code-node IDs
bind every item; IDs are stable for the same source revision and are independently
checked by the Python reader. Path certainty is copied from the validated graph.

This is a syntactic inventory, not inferred business facts. Static fields are not
evaluated, and missing library values remain unevaluated. Call effects are retained
as potential writes/exceptions with their arguments; their observable significance
is explicitly unclassified. There is no per-tag or per-class behavior catalog.
An `extracted` checklist does not resolve an incomplete graph or establish coverage:
its separate `reachability_status` preserves that limitation. Missing or invalid
checklists are reported as incomplete without changing existing acceptance behavior.

At the completion of phase 3, the boundary-comparison harness, mutation tests and pipeline switch
remained later milestones. Verification remains `not_run`, and the existing AI fact and native
acceptance gates remain unchanged. Phase 3 does not yet supply the new checklist to
generation or replace the AI fact gate; that is the planned pipeline switch.

Phase 3 validation: 60 checklist/boundary/reachability/workflow/bank-demo tests
passed, followed by a final 14-test checklist rerun after tightening literal transport.
Coverage includes stable/revision-bound IDs, tampered provenance, escaped and text-block
strings, UTF-16 code units, signed numbers, enum references, guarded switch cases,
short-circuiting, initialization defaults, ordered/repeated arguments, cleanup and
exception syntax. A fresh Mapper/intake/preparation test extracts checklists for all
83 units, and confirms that response-side NilDecorator items include literal `xsi:nil`,
both settings conditions, the null/empty check and the caught exception. The request
checklist includes CCDate's `yyyyMMdd` initializer. No model calls or behavioral
acceptance are part of these checks.
The refreshed saved bank-demo analysis contains 23,373 items across all 83 checklists,
with zero checklist extraction failures. The 42 incomplete call graphs remain
explicitly incomplete; checklist extraction does not erase their unresolved paths.

### Phase 4 — isolated legacy harness and boundary comparison

`tools/behavior_verification/boundary_verification.py:verify_boundary` is a standalone
comparison entry point. It takes the prepared unit, its validated boundary/checklist,
explicit legacy/native API bindings, controlled cases and a new evidence directory.
It does not generate code or alter any conversion acceptance gate.

The Java tool compiles disposable UTF-8 snapshots, preserving both the original-file
hash and the normalized analysis-text hash. Original implementing classes run in a
plain JVM. The existing bank-demo Context, Tag and settings classes already supply
the required small framework implementations; the harness reuses them rather than
inventing replacement formatter/decorator behavior. Other frameworks can provide
explicit API adapters. Missing classes, unsupported initialization/property conversions,
uncontrolled effects and unsupported observable types end as Verification incomplete.

The default framework adapter constructs the configured format tree, initializes its
components from Tag attributes, registers children/decorators by their public API
types, and invokes unformat/format; configured steps use their public context setter
and execute method. Native boundary implementations or API bridges are explicit,
source-hashed artifacts. Settings method/class bindings and canonical external-target
bindings may differ between the two sides without comparing their internal structure.
No formatter/decorator business behavior is selected from a tag-name catalog.

Each side of every case runs in a fresh JVM with assertions enabled, UTC and ROOT
locale. Supported source-level clock/random hooks cover Date construction,
System.currentTimeMillis, Math.random, default Random construction, java.time no-arg
now methods and the SimpleDateFormat two-digit-year window. Known unsupported sources,
including unbound I/O and unsupported reflection/random sources, are rejected. External
calls use explicitly bound canonical targets and ordered replay responses; no live
database/service is called to discover an expected answer. Unsupported object-returning
dependencies require a dedicated adapter; an absent replay or unused response cannot pass.
Settings, seed, clock and replay data are stored with each case. Timeouts stop the unit
as incomplete and list the cases that were not executed.

Instrumentation applies controls to the recorded legacy slice and the framework/settings
methods the harness itself invokes. Unused other-direction methods do not become new
execution obligations. Probes record actual branch outcomes, loop guards (including
iterable/array foreach), entered methods and ordered branch paths. Unobserved outcomes,
unentered instrumented methods, unprobed nodes and unresolved graph edges remain visible.
An entered method does not establish execution of every checklist item within it.

The report compares returned values, final context, ordered framework writes/removals,
exception type plus post-failure state, and ordered external targets/arguments/counts.
Numeric protocol representations retain decimal scale, and strings remain distinct
from numbers; the harness does not silently approve a numeric normalization rule.
Exception messages are captured but are not an equality gate.
XML attribute order is normalized, including for fragments; prefixes, namespace URIs,
element order and missing/empty/nil distinctions remain significant. Text whitespace
is preserved unless an explicit element-only path is approved. Non-XML string results
compare exactly. This comparator is separate from the older operation-trace comparator,
whose whitespace/prefix behavior is intentionally unchanged.

`boundary-comparison.json` records per-field match/difference status, both observations,
reproducible inputs/controls, related checklist IDs, coverage gaps and original/compiled
artifact hashes. Status is `matched_observed_cases`, `differences_found` or
`verification_incomplete`; it is never an Accepted-unit record. Neither passing sampled
cases nor the test fixtures establish exhaustive equivalence or live AI conversion acceptance.

Automatic request cases come from configuration fields, pattern defaults, parser literals,
missing/empty/boundary values and seeded combinations. Flat response/step context cases
also use literal context keys from the recorded framework read/remove calls, optional
declared defaults, missing/null distinctions and seeded combinations. Structured collection
inputs need an explicit case adapter; the generator does not invent their shape. All
boundary kinds can also use explicit typed cases. The bank request
test compares the actual original GetAccountDetailsRQFmt against an independent native
test fixture, clearly labeled as such. Phases 5 and 6 below add exclusions/static checks
and the seeded-defect suite; pipeline integration and production pilot remain later milestones.

Phase 4 validation passed: the 77-test regression run, followed by focused checks after
the final transport/comparison changes (19 tests). Coverage includes typed scalar replay,
settings/API bindings, state reset, context writes/removals, timeouts, actual differing
return values with checklist-linked feedback, loop/switch probes, logging with severity
and exception arguments, and strict XML/fragment comparison. An executed response fixture
flags the deliberate `xsi:nil` to `wtc:nil` change; this does not claim that a live converted
NilDecorator has passed all runtime branches.

The preserved bank report is
`outputs/bank-demo-boundary-comparison-20261027/boundary-comparison.json`.
All 79 original/native-fixture cases match. Of 30 branch sites, 29 are observed; 14
sites retain unexercised outcomes, and one call-graph edge remains unresolved. The
report includes those gaps, per-field results, reproducible case jobs, source snapshots,
compiled classes and a copy of the exact harness JAR. This is the phase-4 harness exit
check, not full bank-demo conversion acceptance. No live AI conversion was restarted.

### Phase 5 — checklist answers, exclusions and supporting signals

`tools/behavior_verification/static_checks.py:validate_unit_static` is a standalone
checker for a prepared unit, its parser boundary/checklist, candidate Java files and
`UnitChecklistAnswers`. It does not change generation requests, the old AI-fact gates
or unit acceptance. Pipeline integration remains phase 7.

Every checklist ID must have exactly one answer. An implemented answer cites an exact
excerpt in current main Java code; helper files, nested types and reuse of an excerpt
are allowed. JavaParser verifies code-token overlap. Comments, imports, package
declarations and tests cannot provide implementation evidence. File paths and declared
package/type names must match. These checks establish traceability, not equivalence.

Automatic exclusions are deliberately conservative:

- Literal Boolean guards can prove a lexical branch or short-circuited operand dead.
- Configured initialization may use a separately supplied, source-hash-pinned Tag
  contract for a pure lookup over stable configured attributes. No contracts are enabled
  by default. The Tag cannot escape, be aliased or mutated; every configured occurrence
  must agree, and additional callers prevent this proof. Mutable locals, context values,
  missing configuration evidence and merely unobserved branches are not proof.
- Exact fresh receivers such as `new A().method()` may remove impossible virtual
  alternatives. Aliased receivers retain their alternatives. A non-selected candidate,
  or an opposite-direction framework method, must have no remaining active call path
  from any entry/setup root. An active unbounded call prevents that exclusion.
- The default plumbing policy covers only implicit-constructor markers, configured-setup
  markers and throws-declaration metadata. Body instructions, literals, field defaults,
  validation and actual exception behavior remain separate obligations.

An unsupported exclusion is rejected even if every supplied sample matches. Explicit
exceptions require a separately supplied `ChecklistExclusionAuthorization`, bound to
the item, unit, source manifest, configuration and entire candidate revision. A generation
reply cannot supply approval metadata or checker policy. Authorization receipts and the
policy/tool hashes are persisted; tests use synthetic approvals only. Unresolved answers
remain Verification incomplete and are not automatically escalated into a user prompt.

The literal inventory uses actual Java literals and supported constant expressions;
comments and test strings do not count. A missing literal creates a warning and a
comparison request with source/item references and reproducible observed-owner or
generated candidate inputs. Candidate inputs are explicitly not path-coverage proof;
the request retains that coverage gap. Literal presence, including unused literals,
never proves behavior. A trusted paired report may also show a literal constructed
dynamically in an observed output, without proving other paths.

Paired XML outputs reuse the strict phase-4 comparator: names, nesting, child order,
attributes, namespace URIs, literal prefixes and significant text remain observable.
Differences create signals with the exact failing case; attribute order alone does not.
Without paired XML output the structure check is explicitly not observed. Static names
alone cannot establish a dynamically constructed XML shape. Reports must match current
unit/source/configuration and all native compiled-source hashes; separate harness bridge
sources must be explicitly supplied. Passing samples never authorize exclusions.

`unit-static-checks.json` is saved via a temporary file and records item decisions,
proof/approval receipts, revision hashes, warnings and comparison requests. It
uses a shared case catalog so many warnings do not duplicate the same input bodies.
Java UTF-16 code units are preserved as JSON escapes. The report's status
is `mapping_valid`, `mapping_invalid` or `verification_incomplete`; behavioral acceptance
is always `not_decided`. Mapper, conversion order, operation assembly and existing
acceptance gates remain unchanged. No live conversion is restarted by these checks.

Phase 5 validation passed across two runs: 65 completed regression checks plus 54 final
checks, including all 39 new static-check tests and fresh bank preparation. Coverage
includes unsupported exclusions despite matching samples, configured Tag proofs and
their rejection cases, exact/aliased receivers, unbounded calls, metadata-only plumbing,
revision-bound approvals, comment/test citations, missing/assembled literals, UTF-16
report persistence, and strict XML prefix/order/namespace/text distinctions. The first
full run reported all 83 bank boundaries incomplete; the unchanged preparation test
passed on rerun. The original failure cause was not retained, so it is not attributed
to a specific defect. Existing analysis class bytecode matches the saved phase-4 tool;
no existing analysis timeout or technical validation was changed to make the rerun pass.

### Phase 6 — seeded bank-demo defects

`source/tests/test_bank_seeded_defects.py` runs a fresh Mapper/intake/preparation flow
and selects the actual `GetAccountDetailsRQFmt` request unit and `StandardErrorRSFmt`
response unit. Original implementing classes, decorators, framework sources and runtime
settings execute through the unchanged phase-4 boundary harness. Original sources are
never mutated. This suite makes no AI calls or external service/database calls.

Independent native test fixtures must match first: eight request cases and seventeen
response cases. The response corpus crosses channel enabled/disabled and application
allowed/excluded with null, empty, whitespace and escaped nonempty descriptions; it
also checks unconfigured settings. Both sides get identical settings through explicit
API bindings and a fresh JVM per side/case. The request cases include valid input,
missing/empty mandatory fields, missing/empty/all-zero maximum values, and account
numbers with significant trailing zeroes.

The suite plants ten single-site, compilable changes in copies of the native fixtures:

- Remove the mandatory ClientId check.
- Remove null/empty-to-zero conversion.
- Strip account padding from the wrong side.
- Always add nil, or never add nil.
- Ignore the channel condition, or ignore the application exclusion.
- Drop the empty-value nil branch, or drop the null-value nil branch.
- Change both the namespace binding and attribute prefix from `xsi` to `wtc`, retaining
  the same namespace URI and well-formed XML.

Each mutation runs the same corpus as its passing control and must produce
`differences_found`, including its designated witness input and observable field.
Compilation failure, missing sources, an incomplete execution or an unexecuted case
does not count as detecting a defect. Differences must retain source-checklist IDs;
the tests also verify the persisted input/controls and differences in each JSON report.
Exact source-edit anchors prevent fixture changes from silently disabling a mutation.

`seeded-defects-summary.json` links controls and mutation reports with witness inputs,
observable differences and mutated-source hashes. Detailed reports retain both outputs,
context/effects, coverage gaps, source/class hashes and reproducible JVM jobs. This is
test-suite strength evidence, not live AI conversion acceptance or exhaustive equivalence.
The nil decorator's exception/logging paths and all possible runtime inputs are not
claimed covered by this corpus. Pipeline switching remains phase 7; PIT remains phase 8.

Phase 6 validation: the full seeded suite passed 12 tests, detecting all ten defects;
the final catalog and existing boundary-comparator checks passed 11 tests. Both correct
controls matched all 25 cases. The ten mutants were compared on 143 additional paired
cases (168 paired cases overall), with no incomplete execution counted as a detection.
Reports are preserved under
`outputs/milestone6-bank-seeded-defects-20261027/bank-seeded-defects0/`.
No production code, Mapper behavior, acceptance gate or original bank source was changed.

### Phase 7 — pipeline switch

Scoped unit generation now receives the parser checklist, exact reachable source
excerpts and configuration, instead of AI-written behavior facts. Source references
avoid duplicating the same method body for every checklist item. Every item still
retains its stable ID, source location and parser properties.

The acceptance ladder runs checklist validation, the existing managed Maven build
and executed tests, then original/native boundary comparison before publishing files.
The model supplies typed invocation metadata for its declared public API; the trusted
harness constructs inputs and observes actual results and context writes. It cannot
supply executable comparison bridges or expected outputs. Declared unit API methods
must actually execute during comparison. Controlled settings use source-discovered
configuration APIs and cover their enabled/disabled combinations.

Concrete candidate failures return checklist IDs and failing inputs/observations to
the existing retry loop. Unsupported boundaries, unresolved paths, missing branch
coverage and error-only samples remain Verification incomplete. They do not consume
repeated model attempts. Failed and incomplete units are persisted separately and
block operation assembly; processing continues so every selected unit gets an outcome.

AI behavior review is disabled by default for scoped units. The optional
`behavior_triage_enabled` setting makes it advisory: disagreement cannot override
passing technical checks. Trusted exclusion policy and revision-bound authorizations
remain separate from model-generated metadata.

Acceptance receipts bind the source/configuration, generated files, static report,
paired execution report, retained harness JAR and dependency hashes, plus passing build
and executed-test evidence. Packaging rejects missing, changed or historical
fact-only receipts. Existing Mapper behavior, conversion ordering and operation
assembly logic are unchanged. Other generation paths keep their existing checks.

Validation distinguishes a real passing scoped conversion with Maven/JUnit and warm
resume from the whole-bank offline audit. The audit deliberately supplies unresolved
candidates to verify terminal classification for all 83 units; it is not a successful
live AI conversion and does not establish bank-demo acceptance. The prior seeded
defect corpus remains the evidence that the comparator catches the ten known defects.
PIT integration remains phase 8.

Phase 7 validation: 50 focused static/harness/pipeline checks passed, followed by
nine final pipeline and scoped-conversion checks with passing managed Maven/JUnit,
assembly and warm resume. The final fresh-bank audit passed with all 83 units
terminal: zero Accepted, seven Failed (the deliberate candidates omit native HTTP
transport), and 76 Verification incomplete (49 unresolved checklists, 17 parser
capability gaps and ten request-budget limits). There were no pending units and no
unverified assembly. This explicitly negative audit made 56 candidate requests;
parser/budget failures did not need repeated candidate generation. Its readable
outcomes are saved in `outputs/milestone7-bank-verification-outcomes.json`.

### Phase 8 — advisory test-strength measurement

Every technically accepted scoped unit now gets a separate `unit_test_strength`
snapshot and `test-strength/test-strength.json` under its retained verification
attempt. This is test strength, not equivalence or an additional acceptance gate.
PIT runs only after the existing technical acceptance receipt has been recorded.
Its score, tool errors, missing artifacts, timeouts and report-write failures cannot
undo that receipt or trigger code-generation retries.

Before publication removes the staged project, the converter snapshots its POM and
sources/tests. Only that isolated POM gets the pinned PIT Maven plugin (1.30.1) and
JUnit 5 adapter (1.2.3). Mutation targets are this unit's main files and their nested
classes; selected tests are its submitted test files. Other accepted source remains
available for compilation without being added to the mutation targets. The published
project's POM and source bytes are untouched. Execution uses the run's JDK, Maven
settings and local repository; timeout cleanup terminates the measurement process tree.

`unit_mutation_testing` defaults to `enabled: true`, `timeout_seconds: 180` and
`recommended_score: 80`. The recommended score is advisory, not a PIT fail threshold.
Disabled measurements are explicitly recorded. XML/HTML PIT reports and redacted
Maven diagnostics are retained, alongside hashes of the measured inputs, isolated POM
and raw XML report, exact targets and source/configuration/candidate identities.

The summary counts Killed, Survived and No coverage separately. Its score is
`Killed / (Killed + Survived + No coverage)`. Timeouts, nonviable mutants and other
execution errors remain separate and make the measurement incomplete; they never count
as killed. No mutations means no score, not 100%. Recommendations identify surviving
or uncovered methods/lines and request stronger tests. These reports make no claim
that passing tests or high mutation scores establish full behavioral equivalence.

Phase 8 validation passed 18 focused/integration checks plus one real timeout-cleanup
check. Actual PIT execution measured four mutants: the weak suite killed two and
left two alive (50%); stronger assertions killed all four (100%). Both technically
accepted units in the scoped Maven/JUnit integration saved completed reports with
three killed and three uncovered mutations each (50%), without blocking operation
assembly or warm resume. Error, missing/malformed report, exception, disabled and
timeout cases retained advisory outcomes; a pipeline measurement failure left unit
acceptance intact. The tests verify that the original POM remains byte-identical.
These are controlled integration results, not a successful live bank-demo conversion.
Logs: `outputs/milestone8-integration.log` and the retained measurement reports under
`outputs/milestone8-integration-20261027/`.

### Phase 9 — pilot selection and measurement tooling; production run pending

`tools.behavior_verification.pilot` selects a source-bound sample from existing scoped
preparation and boundary reports. The default is 20 format-direction units and 20
configured steps. Selection round-robins deterministic shape groups: implementation,
direction, branch shapes/size, configured setup classes and external-call presence.
Incomplete analysis remains eligible; easy units are not selected by filtering out
known limitations. The manifest records exact source/configuration fingerprints,
operation contexts, available counts and any sample shortfalls. Its hash fixes the
measurement denominator. This is varied sampling, not a claim of statistical
representativeness or exhaustive coverage.

Convert the manifest's operation list through the existing converter and unchanged
gate policies. Its normal dependency ordering may convert additional units; pilot
metrics include only sampled IDs. The reporting command reads the selected run's
database in read-only mode. Accepted outcomes must pass the existing retained-evidence
receipt checker. Missing outcomes remain Pending; changed/missing source identities,
historical fact-only receipts and damaged acceptance evidence remain Unverified
evidence. They never enter the acceptance numerator. Failed units now retain their
original source/configuration identities and incomplete static checks retain their
report location so their outcomes can be measured honestly.

Acceptance, failure and Verification incomplete percentages use all selected units.
Incomplete causes retain their technical stage and details. Literal-warning percentage
uses only units whose persisted static report covers the source-bound literal inventory
(including supported exclusions); its numerator and denominator are reported together
with the unmeasured count. Missing/partial static checks are not assumed warning-free.
Reports include per-kind counts and explicitly state that optional production-log
replay has not run. No complete approved request/response logs are assumed available.

Example, with `PYTHONPATH=source`, using paths from the same prepared source/profile:

```powershell
python -B -m tools.behavior_verification.pilot select --preparation preparation.json --boundaries boundaries.json --dataset-type production --per-group 20 --output pilot-sample.json
python -B -m tools.behavior_verification.pilot report --sample pilot-sample.json --database state/migration.db --run-id RUN_ID --run-output PROFILE_OUTPUT_ROOT --output pilot-measurement.json
```

Use `--dataset-type bank_demo` for demo validation. A demo or fixture report can never
declare `production_pilot_completed`. The local validation creates a fresh bank Mapper
output, intake and preparation, then selects 40 units; it does not relabel preparation
as conversion. Production execution and its measured rates remain pending an approved
production workspace/vault. This milestone's tooling does not restart a live conversion,
change Mapper output, change conversion/assembly logic or relax any technical gate.

Phase 9 tooling validation passed 13 integration checks and five final metric checks.
A fresh bank Mapper/intake/preparation run exposed 30 format-direction units and 53
steps. The deterministic sample selected 20 of each across ten operations, with no
shortfall. Its report correctly shows 40 Pending and zero accepted: this validates
inventory/reporting, not live AI conversion. Additional tests exercise actual accepted
boundary receipts, damaged receipt rejection, persisted source identities on failed
scoped units, incomplete causes, stale configuration, missing/partial static evidence,
fixed denominators, deterministic selection and a read-only CLI database connection.
The demo sample and report are in `outputs/milestone9-pilot-bank-demo/`; test results
are in `outputs/milestone9-final-tests.log`. No production pilot rates are claimed.

## Risks and open questions

### Request sizing and the 900K default

The default `behavior_context_chars` is now 900000. The completed bank run's saved
profile is updated for its next resume and its fresh-run launcher uses the same limit;
the original 300000 profile is preserved as `profile.before-request-budget-900k.json`.
Historical run outcomes still describe the original 300K attempt. Explicit lower
limits in other profiles remain honored. No conversion is restarted by this update.

Each budget check logs the complete application JSON plus instructions, including
schema, source excerpts/files, examples, checklist, accepted APIs and documentation.
The log records character count, estimated UTF-8 bytes and decimal KB/MB/GB, the
configured character limit, and `fits_budget` or `too_large`. Top-level component
weights, JSON envelope overhead and embedded text/file counts identify what takes
space without logging their contents. Sizes are recorded again after correction
compaction. A rejected request's error now retains its exact character/byte count,
even when rejection occurs before an attempt can be saved. These are application
payload estimates, not provider transport-envelope sizes or token counts; the
character budget, not byte size, controls this local decision.

Splitting remains available on the older analysis/evidence-summary path. Scoped
parser/checklist generation preserves the complete unit and does not invoke that
AI-summary splitting path. This update adds visibility and raises the limit; it
does not claim to add multipart scoped generation or remove any evidence/checks.

Validation: 44 focused/regression checks passed. One older assembly-correction test
with an explicit 180K budget fails at 180814 characters; the same failure was
confirmed with the previous encoder, so that unrelated fixture remains unchanged.
The size tests cover Unicode byte/character differences, all component overhead,
exact budget boundaries, compaction decisions and content-free diagnostics.

### Follow-up — correctable native argument bindings

The first live bank run exposed candidate argument bindings such as `java.util.Map`
and `java.sql.Connection` being classified as Verification incomplete before any
correction attempt. These types were chosen by the generated native API, not required
by the trusted original boundary. Unsupported generated argument types and excessive
recipe nesting now produce retryable binding failures with the supported type set
and instructions to update code, API contract and metadata together. The configured
attempt limit still applies, and all prohibited types remain prohibited. Genuine
missing harness capabilities retain Verification incomplete; neither acceptance nor
the request budget is weakened. This change applies to the next process/resume, not
the already-loaded validator in the active batch.

Follow-up validation passed 12 checks: Map/JDBC/File recipes remain rejected but
retryable, excessive nesting is retryable, corrected metadata/code can proceed to
real JVM boundary comparison, repeated invalid candidates exhaust the existing
attempt limit without acceptance/publication, and genuine capability gaps still
stop without repeated model requests. Results: `outputs/binding-correction-final-20261027.log`.

- **Harness coverage:** some legacy classes depend on framework services that are hard to stub. Those units end as Verification incomplete until a stub exists; they are never accepted on static checks.
- **Slice size:** conservative call resolution can pull in many candidates for interface calls. Supported exclusions keep generation focused; the slice itself is not trimmed.
- **Exclusion list:** the fixed list of `not_applicable` reasons must stay small and checkable, or it becomes a loophole.
- **Side-effect adapters:** each external kind (stored procedure, HTTP service, file) needs one adapter that maps legacy calls to the generated collaborators.
- **Comparison rules:** which differences are acceptable (date types, number formatting, empty vs missing element, exception message text) needs one agreed rule set per result type.
- **Open question:** who approves explicit exceptions and `unresolved` items?

### Logging comparison implementation checkpoint — 2026-10-31

`boundary_logging.py` separates recognized harness Logger events from business calls and compares counts per numeric severity. The shared comparator retains strict checks for unrecognized events, outputs, XML prefixes, context and escaped exception types. Non-blocking raw logging details are recorded separately by both standard and thin-path report producers; existing observations are never rewritten. Reports record `logging-severity-count-v1`, while historical reports without a policy remain unlabelled.

Changed implementation files: `source/tools/behavior_verification/boundary_logging.py`, `boundary_comparison.py`, `boundary_verification.py`, `thin_path_observations.py`, `thin_path_comparison.py`, and `source/models/boundary_comparison_report.py`. The optional diagnostic collector preserves existing comparison return values. `source/tests/test_boundary_logging.py` covers policy, report persistence, AI feedback separation and a real JVM warning/missing-warning mutation. Generation prompts, retry limits, original Java/XML sources, and historical conversion outputs remain unchanged.

A read-only re-evaluation of the prior 340 observations still rejects the same 20 missing warnings, now as severity-count mismatches; it is not a fresh execution or acceptance. Matching message variants alone cannot establish matching content or exhaustive equivalence.

Validation: 154 focused/regression checks passed, including real JVM warning normalization and missing-warning mutation checks. A fresh response-only trial started at `outputs/bank-response-logging-policy-20261031-042140` using Gemini 3.7 Flash, 300-second timeout, unchanged retry limits and technical validation. Monitoring is active; no live acceptance is claimed yet. No commit or push performed.

## Sources

- [PIT Maven configuration](https://pitest.org/quickstart/maven/): scoped class/test targets and XML/HTML reports.
- [PIT JUnit 5 adapter](https://github.com/pitest/pitest-junit5-plugin): Maven plugin dependency and version compatibility.

- [Automated Testing of COBOL to Java Transformation (IBM, FSE 2025)](https://arxiv.org/abs/2504.10548v1): tests generated on the legacy side, external calls mocked, run against the translation
- [Migrating Code At Scale With LLMs At Google](https://arxiv.org/pdf/2504.09691): deterministic location discovery and a cheap-to-expensive validation ladder
- [Specification-Driven Code Translation Powered by LLMs: How Far Are We?](https://arxiv.org/pdf/2412.04590): AI-written specs omit details and are wrong in about 12.8% of cases
- [PAST: Program State Alignment for Long Code Translation](https://arxiv.org/html/2504.02017v1): compare intermediate values to localize differences
- [Kaizen: Differential Testing for LLM-Translated HPC Applications](https://arxiv.org/pdf/2607.04058): compilation is a weak proxy; semantic bugs are input-dependent
- [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/html/2501.12862v1): mutants check that tests catch real faults
- [AWS Mainframe Modernization Application Testing](https://docs.aws.amazon.com/m2/latest/userguide/what-is-apptest.html): capture and replay with equivalence rules
- [AlphaTrans (FSE 2025)](https://arxiv.org/abs/2410.24117): dependency-ordered translation with test translation
