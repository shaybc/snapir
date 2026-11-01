# Metadata Checklist, Eping, Alternative 1

Status: implementation in progress; completed slices and remaining work are recorded below.

The plan is to replace mandatory AI checklist mappings with isolated execution checks, measured coverage, and tests that detect deliberately broken code. Reuse the existing Java harness and comparison tools rather than build another verification system. Neither observed agreement nor coverage establishes exhaustive equivalence.

## Implementation milestones

1. Separate essential connection contracts from checklist citations.
2. Remove checklist citations as an acceptance requirement.
3. Derive APIs and known configuration data deterministically.
4. Add narrowly scoped executable adapters where automatic binding is insufficient.
5. Extend deterministic input generation and controlled external responses.
6. Run independent original/native comparisons.
7. Measure coverage and attempt bounded input expansion.
8. Test comparison strength with mutations.
9. Correct the responsible artifact within fixed budgets.
10. Validate the replacement on the bank demo before making it the default.

## 1. Define the new verification policy

Introduce a versioned verification mode that explicitly separates:

- Structural validity: safe code, supported dependencies, correct public interfaces.
- Observed agreement: original and native executions produced matching results.
- Verification strength: exercised branches and detected mutations.
- Limitations: unsupported framework behavior, unobserved outputs, and uncovered paths.

Do not silently reinterpret existing acceptance receipts. Historical results retain their original policy and evidence.

Completion check: reports distinguish a passing build, matching observations, incomplete verification, and full operation acceptance.

## 2. Remove mandatory AI checklist mapping

Stop requesting and validating an excerpt for every parser checklist item in the new mode.

Keep the parser's original findings for input generation, coverage measurement, and diagnostics. They no longer require AI-written mappings.

Retain contracts needed for typed reuse and operation assembly. Derive known IDs, hashes, dependencies, and APIs in application code wherever possible.

Completion check: a candidate can reach execution comparison without `checklist_answers` or `checklist_implementations`; unsafe or incomplete executable code still fails.

## 3. Establish executable boundary adapters

Reuse existing automatic bindings where they work. Where they do not, ask AI for a small adapter as a separate task.

Adapters translate the common test input into each implementation's arguments. Converter-owned harness code captures the results and performs comparison.

Adapters must not:

- Replace the original business implementation.
- Supply expected answers.
- Change generated production code.
- Remove or normalize observable differences without an explicit comparison policy.

Validate selected entry-point invocation, permitted dependencies, input handling, and observable collection. Unsupported cases remain explicitly incomplete.

Completion check: formats and OP steps run in isolated JVMs without a Composer server. Deliberately constant-returning or entry-skipping adapters are detected by targeted tests.

## 4. Extend deterministic test inputs and fixtures

Extend existing generators using XML field types, original constants, conditions, and runtime settings.

Cover missing, null, empty, ordinary, and boundary values. Preserve nested field paths and collection structure.

Provide identical controlled external responses to both executions. Control clocks and randomness where supported. Record unsupported dependencies instead of inventing their behavior.

AI may suggest additional inputs, but it must not determine expected answers.

Completion check: repeated runs with the same seed and fixtures produce the same cases and observations.

## 5. Make original execution the reference

Run the original implementing classes and native implementation separately with the same logical inputs.

Converter-owned code compares:

- Returned values and XML.
- Relevant state writes, removals, and presence.
- Exceptions.
- Recorded external calls.
- Logging under the existing agreed policy.

Keep literal XML-prefix requirements where applicable. Do not normalize away the original `xsi:nil` problem.

Completion check: deliberately introduced value, prefix, state-write, and external-call differences produce precise failing cases.

## 6. Measure coverage and expand inputs

Reuse existing original-code instrumentation to report executed methods and branch outcomes.

Attempt additional cases within a fixed time/case budget. Support deterministic expansion for recognized conditions; report unresolved conditions honestly.

Do not require every parser item or every conceivable path to be covered. Do not label uncovered behavior as verified. The policy must state which gaps block acceptance and which remain reported limitations.

Completion check: a deliberately unexercised branch appears as a coverage gap, without causing an endless generation loop.

## 7. Measure whether comparisons detect broken behavior

Extend existing mutation support to exercise the original/native comparison suite, not just generated JUnit tests.

Start with supported mutations such as:

- Negated conditions.
- Changed return values.
- Removed observable writes.
- Changed output literals.

Run mutations only in disposable native-code copies. Verify the unchanged candidate first.

Distinguish detected mutations, survivors, uncovered mutations, invalid mutations, and tool failures. A survivor is a test-strength concern, not automatic proof that production code is wrong. Keep existing advisory PIT behavior until an explicit replacement policy is validated.

Completion check: the suite detects deliberate prefix changes and removed output writes, while leaving the real candidate untouched.

## 8. Route failures and bound all work

Collect all comparison differences for the executed cases.

Send corrections to the responsible task:

| Problem | Action |
| --- | --- |
| Proven output difference | Correct production code |
| Adapter compilation or invocation error | Correct the adapter |
| Unsupported harness/framework behavior | Report a verification limitation |
| Missing coverage | Expand inputs within budget |
| Surviving mutation | Investigate test strength |
| Provider timeout | Retry within the existing bounded policy |

Preserve valid artifacts independently. Revalidate affected artifacts after changes. Nested retries, splitting, or adapter repairs must not create unlimited additional attempts.

Completion check: failure-injection tests prove termination and show that tooling failures cannot trigger arbitrary business-code edits.

## 9. Run acceptance trials and switch over

Start with the three familiar boundaries:

- `GetClientLinksRQFmt`
- `StandardErrorRSFmt`
- `NoLinksFound`

Include deliberate defects to prove the replacement rejects incorrect behavior. Then run the complete `INTERNET/GetClientLinksOp`.

Only after these checks pass should the new mode become the default. Keep the old mode available explicitly during transition; do not fall back silently when verification fails.

## Expected files to change:

Paths below are relative to this document. Proposed files do not exist yet. These are expected implementation targets, not changes performed by saving this plan.

### Existing orchestration and contracts

- [pipeline_configuration.py](../../source/models/pipeline_configuration.py): select the versioned verification mode and bounded settings.
- [staged_metadata.py](../../source/models/staged_metadata.py): omit mandatory citation fields in the new mode.
- [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py): connect generation, adapters, verification, and correction stages.
- [staged_adapters.py](../../source/runtime/behavior_conversion/staged_adapters.py): retain structural checks without citation requirements.
- [Component validation.py](../../source/runtime/component_conversion/validation.py): apply the selected policy to component acceptance.
- [verification_ladder.py](../../source/runtime/behavior_conversion/verification_ladder.py): replace citation prerequisites with executable evidence.

### Existing execution and measurement

- [boundary_harness_binding.py](../../source/models/boundary_harness_binding.py): represent checked executable adapters.
- [BoundaryAdapter.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/BoundaryAdapter.java): preserve the shared invocation boundary.
- [BoundaryHarness.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/BoundaryHarness.java): execute adapters and capture independent observations.
- [controlled_inputs.py](../../source/tools/behavior_verification/controlled_inputs.py) and [verification_cases.py](../../source/runtime/behavior_conversion/verification_cases.py): extend bounded deterministic cases.
- [boundary_comparison.py](../../source/tools/behavior_verification/boundary_comparison.py) and [boundary_coverage.py](../../source/tools/behavior_verification/boundary_coverage.py): retain comparisons and expose coverage gaps.
- [verification_test_strength.py](../../source/runtime/behavior_conversion/verification_test_strength.py): connect mutation measurement to comparison strength.

### New focused modules expected during implementation

- [executable_adapters.py — proposed](../../source/runtime/behavior_conversion/executable_adapters.py): adapter generation and validation.
- [comparison_mutations.py — proposed](../../source/tools/behavior_verification/comparison_mutations.py): bounded mutations checked against differential execution.

### Tests and documentation

- Extend existing staged-conversion, boundary-comparison, coverage, and mutation tests; add adapter and bounded-loop regression tests.
- Update the [Behavior Verification Design Plan](Snapir%20Behavior%20Verification%20Design%20Plan.md) and [Component-First Implementation Plan](Component-First%20Composer%20Conversion%20Implementation%20Plan.md) during implementation.

## Scope preserved

Mapper behavior, Excel generators, operation ordering, typed-object reuse, logging policy, and original business implementations remain outside this change.

## Implementation checkpoint — 2026-10-31

Work started on `codex/metadata-1`, created from local `main`. Existing local changes were preserved.

The first slice implements the opt-in separation of mandatory checklist citations from executable verification. It uses the existing isolated original/native JVM harness and trusted typed binding. It does not require a Composer server.

Enable it explicitly in the pipeline profile:

```json
{
  "staged_unit_conversion": true,
  "executable_verification": {
    "mode": "executable_boundary_v1",
    "max_cases": 512,
    "require_branch_coverage": true
  }
}
```

- `checklist_v1` remains the default. Existing checklist validation and batching remain available.
- The new mode skips AI citation mapping in staged generation, component validation and whole-unit promotion. Small contract/binding descriptions are still needed where deterministic binding is not available.
- Exported APIs are selected from JavaParser results. Known source/configuration identities are filled locally.
- Structural checks, compilation, executed JUnit tests, controlled inputs, original/native comparisons and existing logging policy remain required.
- All prepared comparison cases are attempted even if an earlier case is incomplete. Tooling limitations remain distinct from observed differences.
- A separate `executable-boundary-v1` receipt binds acceptance to exact candidate files, configuration, source provenance, tool revisions and retained comparison evidence. It requires execution of the selected production entry.
- Unsupported adapters and blocking original coverage gaps remain incomplete. This is observed-case agreement, not exhaustive equivalence.

This completes the initial mode/gate separation, not the entire plan. Executable adapter generation, broader deterministic input generation, bounded coverage expansion, comparison-driven mutation testing, and bank-demo rollout remain subsequent milestones. Existing PIT remains advisory. No default rollout, full operation acceptance, commit or push is implied by this checkpoint.

### Files changed for this slice

| Files | Purpose |
| --- | --- |
| [executable_verification_settings.py](../../source/models/executable_verification_settings.py), [pipeline_configuration.py](../../source/models/pipeline_configuration.py) | Define explicit opt-in policy and require staged generation. |
| [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py), [fingerprints.py](../../source/tools/conversion_tools/scoped_reuse/fingerprints.py) | Resolve the selected mode and invalidate reuse when its policy changes. |
| [native_format_component_bundle.py](../../source/models/native_format_component_bundle.py) | Allow citation-free format bundles; legacy runtime checks still require citations. |
| [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py), [staged_adapters.py](../../source/runtime/behavior_conversion/staged_adapters.py), [metadata_semantics.py](../../source/runtime/behavior_conversion/metadata_semantics.py) | Separate small contract descriptions from checklist mapping and omit checklist delivery in the new mode. |
| [requests.py](../../source/runtime/component_conversion/requests.py), [validation.py](../../source/runtime/component_conversion/validation.py), [partition_validation.py](../../source/runtime/component_conversion/partition_validation.py) | Carry mode policy and skip only citation gates for opted-in components/subtrees. |
| [unit_provider.py](../../source/runtime/component_conversion/unit_provider.py), [format_verification.py](../../source/runtime/component_conversion/format_verification.py), [verification_units.py](../../source/runtime/behavior_conversion/verification_units.py) | Carry the mode through composed formats and whole-unit verification without synthesizing citation answers. |
| [verification_ladder.py](../../source/runtime/behavior_conversion/verification_ladder.py), [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py) | Select the new structural/execution ladder and retain the existing legacy ladder. |
| [boundary_verification.py](../../source/tools/behavior_verification/boundary_verification.py) | Allow the new mode to attempt all prepared cases after an incomplete case. |
| [verification_state.py](../../source/runtime/behavior_conversion/verification_state.py), [executable_receipts.py](../../source/runtime/behavior_conversion/executable_receipts.py) | Persist and revalidate distinct execution receipts before packaging. |
| [pilot_measurement.py](../../source/tools/behavior_verification/pilot_measurement.py) | Recognize execution receipts without claiming citation-based literal measurements. |
| [test_executable_verification.py](../../source/tests/test_executable_verification.py), [test_staged_pipeline.py](../../source/tests/test_staged_pipeline.py) | Exercise opt-in generation, actual JVM comparison, evidence integrity and retained legacy behavior. |
| This document | Record configuration, implementation scope and remaining milestones. |

Unrelated Mapper/Excel behavior, business code, operation ordering, typed reuse and logging policy were not modified by this slice. Existing local work was preserved.

### Validation of this slice

- Five focused tests passed, including actual Maven compilation, executed JUnit, independent original/native JVM comparison, rejected behavioral differences and immutable receipts.
- Forty-two staged/checklist/pilot regression tests passed; four excluded tests were outside that regression selection. The bank-demo preparation fixture passed without claiming conversion acceptance.
- After the final prompt/provenance tightening, the affected prompt/policy tests and missing-build/changed-configuration test passed again.
- No model-backed conversion was launched. Full operation acceptance and default rollout remain untested.

## Milestone 3 checkpoint — deterministic contracts

Implemented on `codex/metadata-1`, for the opt-in executable mode only.

- AI receives a details-only schema. It no longer copies API declarations, API owner/member selections, unit contracts or component contract IDs.
- One assigned component owns the public types declared in its generated production artifact. Prerequisite sources remain outside that ownership.
- A configured unit exports its selected entry type and the public types referenced by that API, including constructor, parent and generic DTO references. Unrelated helper types are excluded.
- Existing local materialization supplies known IDs, evidence identities, requirement definitions and dependency identities. JavaParser supplies exact API declarations. Source/configuration hashes remain application-owned execution evidence.
- Bindings and runtime descriptions still require interpretation. They retain their existing validation; this milestone does not implement executable adapter generation.
- Missing or ambiguous ownership is reported as incomplete. Multi-component assignments are not guessed.
- A versioned derivation policy participates in request/stage and component reuse fingerprints. Changed derivation cannot silently reuse earlier contracts.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [deterministic_contracts.py](../../source/runtime/behavior_conversion/deterministic_contracts.py) | Derive production-owned APIs and their referenced public type closure; reject ambiguous ownership. |
| [staged_metadata.py](../../source/models/staged_metadata.py) | Define details-only response schemas that exclude known contract fields. |
| [metadata_semantics.py](../../source/runtime/behavior_conversion/metadata_semantics.py) | Use the narrower schema, then materialize and validate local contracts through the existing flow. |
| [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py), [fingerprints.py](../../source/tools/conversion_tools/scoped_reuse/fingerprints.py) | Version request and reuse identities for the new derivation behavior. |
| [test_deterministic_contracts.py](../../source/tests/test_deterministic_contracts.py), [test_staged_pipeline.py](../../source/tests/test_staged_pipeline.py) | Cover real JavaParser ownership/type resolution and staged component, format and unit integration. |
| This document | Record completion, limitations and verification. |

Validation: 40 focused/regression tests passed, with five real-Maven/operation-assembly tests outside this selection. After generic DTO handling was added, all six parser/contract tests passed again. Model calls in staged flow tests were controlled fixtures; no live conversion was launched.

The next milestone is narrowly scoped executable adapters where automatic binding is insufficient. Legacy mode, production generation, comparison/logging rules, technical gates and retry limits remain unchanged. No unrelated code was modified, and existing local changes were preserved. No commit or push was performed.

## Milestone 4 checkpoint — restricted executable adapters

Implemented on `codex/metadata-1` for the opt-in executable mode.

Adapters use restricted invocation plans executed by converter-owned Java. The model does not generate arbitrary Java adapter source. This keeps translation executable while preventing adapter code from returning invented expected answers or replacing business logic.

- Existing valid bindings are reused. Missing bindings first use deterministic resolution. Where that is insufficient, a separate adapter task selects existing parsed constructors, setters, factories, entry methods and result/presence accessors.
- Public static DTO factories are now supported when they return their declared native type. Inputs come only from unchanged XML, original context values or recursively constructed native objects.
- The selected production entry owner must be unambiguous. Unrelated helpers and competing constant-returning entry classes cannot be selected as shortcuts.
- Staged unit/format generation and component-to-unit promotion use the adapter resolver. Format metadata may defer its binding to this task.
- Adapter repairs use a durable bounded role budget. Declared limitations stop as incomplete. They do not request arbitrary production edits or reset implementation attempts.
- Original context-key/API inspection runs independently of checklist mapping in this mode. Existing source/API guards, production compilation/JUnit, isolated comparisons, logging policy and presence/partial-write limitations remain in force.
- Valid input keys include deterministic `dataName` fields from the original XML configuration, even when Java accesses them through variables rather than string literals.
- The adapter policy version participates in request/reuse fingerprints. Execution receipts retain the actual binding and pinned tool/compiled evidence.

Unsupported operations, ambiguous entry ownership, framework behaviors not represented by the trusted harness, and observations requiring unsupported dynamic-write tracking remain incomplete. This is a bounded adapter capability, not a generic Composer engine or exhaustive proof of equivalence.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [native_executable_adapter.py](../../source/models/native_executable_adapter.py), [executable_adapters.py](../../source/runtime/behavior_conversion/executable_adapters.py) | Define restricted plans or explicit limitations and resolve them in a bounded adapter task. |
| [native_boundary_value.py](../../source/models/native_boundary_value.py), [native_format_component_bundle.py](../../source/models/native_format_component_bundle.py) | Represent native DTO factories and allow a format binding to be deferred to the adapter task. |
| [NativeBoundaryValues.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/NativeBoundaryValues.java) | Execute validated public static DTO factories while retaining existing argument and observation handling. |
| [native_binding_builder.py](../../source/runtime/behavior_conversion/native_binding_builder.py), [verification_binding.py](../../source/runtime/behavior_conversion/verification_binding.py) | Check factory names, parsed signatures, return types and input shapes. |
| [metadata_semantics.py](../../source/runtime/behavior_conversion/metadata_semantics.py), [deterministic_contracts.py](../../source/runtime/behavior_conversion/deterministic_contracts.py), [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py) | Delegate missing wiring to the adapter task and inspect original context APIs independently of legacy checklist delivery. |
| [unit_binding.py](../../source/runtime/component_conversion/unit_binding.py) | Reuse the resolver and existing scoped authorization/budget during component-to-unit promotion. |
| [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py), [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py) | Version the adapter policy and report missing validated plans accurately. |
| [test_executable_adapters.py](../../source/tests/test_executable_adapters.py), [test_staged_pipeline.py](../../source/tests/test_staged_pipeline.py) | Test real factory invocation/comparison, staged wiring, forbidden plans, ambiguity and bounded resume behavior. |
| This document | Record implementation, scope and validation. |

The next milestone is deterministic input/fixture expansion. Existing business code, default verification mode, comparison/logging policy and implementation retry limits were not changed. Existing local work was preserved; no live conversion, commit or push was performed.

Validation: the 50-test staged/metadata/typed-boundary regression selection passed (five real-Maven/operation-assembly tests were outside that selection). After the final entry-owner/configured-key checks, all eight focused adapter tests passed. The harness was built with Maven, and the factory-backed original/native comparison ran actual compiled code in fresh JVMs for null and ordinary inputs. A disposable deliberately incorrect production copy was detected; the retained candidate stayed unchanged. Adapter plan rejection, entry skipping, ambiguous competing entries, explicit limitations, staged format integration, component-step promotion and bounded resume were checked. This is boundary/tool validation, not full operation acceptance or a live provider trial.

## Milestone 5 checkpoint — deterministic inputs and controlled fixtures

Implemented on `codex/metadata-1` for the opt-in executable mode.

- Request cases retain nested element paths, duplicate leaf names under different parents, definition references and declared XML child occurrences. They distinguish missing elements, `xsi:nil`, empty strings, ordinary values and escaped text.
- Scalar domains use supported date patterns, boolean samples, bounded integer/decimal literal samples and configured inclusive numeric bounds. They sample the threshold and neighboring values. This is sampling, not a proof that every condition was exercised.
- Context cases preserve missing versus explicit null and retain supported date/boolean shapes. Duplicate context names that cannot safely be interpreted as distinct flat keys remain incomplete.
- Explicitly declared XML collections sample empty, ordinary and bounded multiple occurrences. Baselines respect supported minimum counts. Unknown indexed layouts, reference-name overrides and repeated document roots remain incomplete rather than being flattened or guessed.
- Unit-scoped replay responses apply unchanged to generated cases. Supplemental fixtures may supply captured XML/context inputs, clocks, seeds, settings and exact external responses. Replay target/argument mismatches still fail as incomplete; no service behavior is invented.
- Fixture contents and replay values stay out of model prompts. Only their policy hashes are delivered for cache invalidation. Actual expected boundary observations still come from original execution.
- Generation is lazy and bounded by case count, per-case characters, scalar-domain samples, collection items and nesting depth. Settings permutations cannot allocate an unbounded Cartesian product. Reports record sampled paths, omitted domain values and planned case counts.
- Exact controlled cases are retained in `input-cases.json` and hashed into new execution receipts. Packaging verifies that comparison used those cases and rejects changed input evidence. A policy changed after structural inspection is incomplete. Historical receipts without the new input-generation marker retain their earlier interpretation.

### Configuration

The default remains `checklist_v1`. The new mode's defaults are seed `1729`, clock `1704153600000`, 12 seeded combinations, 32 scalar-domain values, 8 collection items, 512 cases and 131072 characters per controlled case. Clocks and seeds must fit a Java `long`.

`executable_verification.replays` maps a configured unit ID to an ordered list of supplied `{target, arguments, value}` responses, or `{target, arguments, exception_type, message}` exceptions. `value: null` is a valid supplied response. These are controlled dependency results, not expected formatter/step outputs.

`executable_verification.fixtures` maps a configured unit ID to supplemental `BoundaryCase` inputs, including `case_id`, `input_xml` or `initial_context`, and optional `external_responses`/runtime controls. Expected boundary-output fields are rejected. Fixtures supplement automatic cases; they do not bypass an unsupported automatic shape or a technical gate.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [executable_input_fixture.py](../../source/models/executable_input_fixture.py), [executable_verification_settings.py](../../source/models/executable_verification_settings.py) | Define unit-scoped controlled fixtures/replays, supported runtime ranges and generation limits. |
| [input_domains.py](../../source/tools/behavior_verification/input_domains.py) | Sample recognized source/configuration scalar boundaries and cache shared domain analysis. |
| [structured_inputs.py](../../source/tools/behavior_verification/structured_inputs.py) | Preserve XML occurrence paths and generate bounded nested/repeated cases. |
| [input_scenarios.py](../../source/tools/behavior_verification/input_scenarios.py) | Combine deterministic context/XML inputs with caller-supplied replay and supplemental fixtures. |
| [controlled_inputs.py](../../source/tools/behavior_verification/controlled_inputs.py) | Add an optional baseline-only context path; existing default behavior is unchanged. |
| [verification_cases.py](../../source/runtime/behavior_conversion/verification_cases.py) | Select the opt-in generator, bound settings expansion and report the planned case count. |
| [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py) | Version input generation and fingerprint fixture changes without disclosing their contents to the model. |
| [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py), [executable_receipts.py](../../source/runtime/behavior_conversion/executable_receipts.py) | Freeze policy/input evidence and revalidate it alongside actual comparison evidence. |
| [test_structured_input_scenarios.py](../../source/tests/test_structured_input_scenarios.py), [test_input_replay_execution.py](../../source/tests/test_input_replay_execution.py), [test_executable_verification.py](../../source/tests/test_executable_verification.py) | Check shapes, determinism, limits, fresh-JVM replay, compilation/JUnit and evidence/policy integrity. |
| This document | Record implementation, usage, limits and validation. |

No business code, Java framework stand-ins, logging/comparison policy or default verification mode was changed in this milestone. Existing unrelated local work was preserved. No live model conversion, commit or push was performed. The next milestone is the independent original/native comparison phase, building on the existing isolated comparison foundation.

Validation: the 42-test staged/input/contract regression run passed (three staged-build/operation-assembly tests were outside that selection). The final 16-test focused pass also passed after the resource/type/policy changes. It included fresh-JVM controlled external-call, clock and random replay; actual Maven/JUnit acceptance verification; rejection of changed input evidence and policy; unchanged legacy context generation; and staged opt-in integration. These results establish the tested boundary/tool behavior, not full bank-operation acceptance or exhaustive coverage.

## Milestone 6 checkpoint — independent observation comparison

Implemented on `codex/metadata-1` for the opt-in executable mode. The existing separate original/native compilation and fresh-JVM execution remain the foundation; neither side is replaced with AI-written expected answers or a Composer server.

- `independent-observations-v1` compares actual returns/XML, state, exceptions and external calls under the existing logging policy. Internal method organization is irrelevant.
- Every prepared case is attempted after a case-specific execution limitation. Reports distinguish matched, different, incomplete and unexecuted cases, plus cases containing limitations. A report cannot become a complete match while limitations or evidence errors remain.
- Observation IDs must match the requested case. Malformed observations and incomplete invocations are limitations, not fabricated business differences.
- DTO getters without presence flags do not establish missing/null equivalence. Repeated write traces and removals that final DTO projections cannot expose remain explicit limitations. Partial state after an exception remains not compared until the operation policy/observer supports it.
- Known differences in independently compared fields can request correction even when another field remains unobservable. Correction feedback contains only the input and compared deltas, without full observation dumps, checklist-ID lists or limitation-repair requests. Once genuine differences are fixed, remaining limitations stop verification rather than causing further business-code retries.
- Global source/tool/compiled-evidence errors prevent correction as well as acceptance. Case counts and passing JUnit do not override those failures.
- The harness records whether the adapter invocation actually completed. Failed final replay validation now preserves captured observations for diagnosis while retaining incomplete status. If both invocations ended, their completed external-call traces can establish a real call difference; unknown fields are not silently compared as equal.
- New acceptance receipts recompute the comparison from retained observations, check the selected policy and summary, and require completed invocations. Match labels alone are insufficient. Older receipts without the new marker retain their prior validation path.
- Prefix, namespace, significant whitespace, empty/nil, numeric and exception comparison rules remain unchanged. Logging severity/count remains blocking; the previously agreed logging details remain diagnostic.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [independent_comparison.py](../../source/tools/behavior_verification/independent_comparison.py) | Classify compared values, state observability limitations and case summaries. |
| [thin_path_observations.py](../../source/tools/behavior_verification/thin_path_observations.py) | Reuse the existing presence/partial-state comparison, adding opt-in partial-removal handling. |
| [boundary_verification.py](../../source/tools/behavior_verification/boundary_verification.py) | Select the versioned policy and run all prepared cases without altering legacy comparison defaults. |
| [boundary_observation.py](../../source/models/boundary_observation.py), [BoundaryHarness.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/BoundaryHarness.java) | Record invocation completion and retain diagnostics after replay-finalization failure without bypassing that failure. |
| [comparison_receipts.py](../../source/runtime/behavior_conversion/comparison_receipts.py), [executable_receipts.py](../../source/runtime/behavior_conversion/executable_receipts.py) | Recompute observed agreement before packaging. |
| [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py), [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py) | Carry policy identity, persist summaries and invalidate incompatible reuse. |
| [verification_feedback.py](../../source/runtime/behavior_conversion/verification_feedback.py) | Separate proven correction deltas from limitation diagnostics. |
| [test_independent_comparison.py](../../source/tests/test_independent_comparison.py), [test_independent_comparison_execution.py](../../source/tests/test_independent_comparison_execution.py) | Exercise classification, receipt tampering, mixed outcomes and deliberately broken compiled implementations. |
| This document | Record scope, verification and remaining limits. |

Validation: 74 regression tests passed, with three staged-build/operation-assembly tests outside that selection. The latest 16 focused comparison tests also passed. The runs included real Maven/JUnit acceptance checks and fresh-JVM output, removed-write, removed-external-call and XML-prefix counterexamples. A separate comparison/logging run passed 44 tests under Java 25. These deliberate counterexamples validate the comparison gate; they do not constitute the planned general mutation-strength implementation.

Remaining limits: unknown presence, dynamic state-event traces and partial error state cannot establish acceptance. Instrumentation of a discarded non-void external-call expression remains an existing unsupported harness shape; it is reported as incomplete, not sent as a business-code defect. No default acceptance policy was relaxed, no unrelated business code was modified, and existing local work was preserved. No live provider conversion, full operation acceptance, commit or push was performed.

The next milestone is measured coverage with bounded input expansion.

## Milestone 7 checkpoint — measured coverage and bounded expansion

Implemented on `codex/metadata-1` for the opt-in executable mode.

- After the initial comparisons agree, deterministic code proposes additional inputs for supported uncovered source conditions. No AI call, expected answer, production edit or generated-test edit is involved.
- Supported conditions contain one direct configured-context getter with a literal key, or a direct `System.currentTimeMillis()` call. Source literals and numeric neighbors provide samples. Local-variable/dataflow inference and unsupported predicates remain explicit gaps. Proposals are never credited as coverage until original-side probes execute.
- Nested conditions reuse an agreeing input that reached the branch. Context mutations preserve other fields; XML mutations require a unique configured path, preserve prefixes and refuse ambiguous repeated elements or unsafe documents. Settings, dependency replays, seeds and clocks stay fixed except for the targeted clock input.
- Compiled code is reused, with a fresh JVM for each side of every added case. Defaults are two rounds, sixteen additional cases, four cases per round and thirty seconds of expansion, within the existing overall 512-case and per-case character limits. The elapsed budget starts after the initial batch; subprocess admission/timeouts respect it. Evidence writing and process cleanup can add overhead.
- Expansion stops on complete coverage, actual comparison differences/limitations, no progress, unsupported inputs or a fixed limit. Reports retain the stop reason, round inputs, executed counts, unsupported conditions and remaining source gaps. Coverage-only limitations never request business-code correction.
- Branch coverage remains required by default. An explicit existing nonblocking policy retains gaps and emits a warning; unresolved source edges still block. Agreement and branch coverage do not establish exhaustive equivalence.
- The final input manifest includes additional proposed controls. New acceptance receipts recompute source coverage from retained original observations and a frozen branch inventory, then check expansion budgets and executed case identities. A reported coverage label cannot substitute for probes.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [coverage_inputs.py](../../source/tools/behavior_verification/coverage_inputs.py) | Propose deterministic context/XML/clock samples for supported source conditions. |
| [coverage_expansion.py](../../source/tools/behavior_verification/coverage_expansion.py) | Enforce expansion rounds, cases, time and no-progress limits. |
| [boundary_verification.py](../../source/tools/behavior_verification/boundary_verification.py), [boundary_execution.py](../../source/tools/behavior_verification/boundary_execution.py) | Execute added cases using compiled sides and bounded fresh JVM invocations. |
| [boundary_coverage.py](../../source/tools/behavior_verification/boundary_coverage.py) | Retain source conditions and identities alongside measured outcomes. |
| [executable_verification_settings.py](../../source/models/executable_verification_settings.py), [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py) | Define and fingerprint expansion policy for opt-in reuse. |
| [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py) | Integrate expansion, persist final inputs and expose gaps/stop reasons. |
| [coverage_receipts.py](../../source/runtime/behavior_conversion/coverage_receipts.py), [executable_receipts.py](../../source/runtime/behavior_conversion/executable_receipts.py) | Recompute source coverage and audit expansion evidence before packaging. |
| [test_coverage_expansion.py](../../source/tests/test_coverage_expansion.py), [test_coverage_expansion_execution.py](../../source/tests/test_coverage_expansion_execution.py) | Check bounds, unsupported cases, XML paths, real JVM probes, deliberate defects, build gates and receipts. |
| This document | Record the implementation, validation and limits. |

The default checklist mode, comparison/logging semantics, production code, AI correction budgets and advisory PIT policy remain unchanged. Existing unrelated local changes were preserved. No live model conversion, full operation acceptance, commit or push was performed. The next milestone is comparison-driven mutation-strength measurement.

Validation: 32 focused coverage/input/comparison tests passed. A 13-test run also passed, including real JVM clock-threshold exploration, detection of a deliberately wrong native result, existing Maven/JUnit executable verification and coverage unit checks. The staged regression selection passed 22 tests, with three staged-build/operation-assembly tests outside that selection. The latest seven coverage checks also passed after adding XML-prefix collision and persisted-receipt/counter tampering checks.

The final four Java 25 integration checks passed: actual Maven/JUnit and receipt validation after expansion; required coverage blocking when expansion is disabled; explicit nonblocking coverage retaining gaps and warnings; and two-round nested-context exploration preserving the input that reached the inner branch. Two earlier clock-counterexample checks were outside this last selection because they had already passed. These are tool/boundary checks, not full operation acceptance or exhaustive equivalence.

## Milestone 8 checkpoint — comparison-driven mutation strength

Implemented on `codex/metadata-1` for the opt-in executable mode.

- The unchanged candidate is freshly compared on the exact retained inputs before any mutation is attempted. Failed or incomplete baseline verification stops measurement, with no mutations generated.
- The pinned JavaParser tool produces bounded single-site native-source copies: negated `if` conditions, changed integer/boolean return constants, changed string literals, and removed standalone map/context writes or setter calls. Unsupported syntax is not guessed. Targets are limited to the current unit's candidate files; tests, original sources and supporting files owned by other units are excluded.
- Mutation runs use the existing independent original/native comparison suite and unchanged runtime controls, not AI-written expected answers or generated JUnit alone. No input expansion or model calls occur during measurement.
- Every mutation carries an exact executed-site probe. Results distinguish detected mutations, executed survivors, uncovered sites, invalid compilations and tooling failures. A matching result without an executed site is uncovered, never a survivor. Comparison limitations cannot establish survival.
- The report retains source hashes, mutation kinds/locations, baseline evidence and per-mutation comparison evidence. The detection rate uses only detected plus executed surviving mutants; uncovered, invalid and tool-failure counts remain separate. A survivor is a test-strength concern, not proof of a production defect.
- Measurement is explicitly enabled with `executable_verification.comparison_mutations.enabled: true`. Defaults are four mutants and a 120-second worker budget. Limits allow at most 32 mutants and 900 seconds. The process-tree timeout includes baseline execution, parser work, compilation and comparisons; partial counts remain available after a timeout.
- Measurement stays advisory and does not change acceptance, request code corrections, reset role counters or replace advisory PIT. The real candidate remains unchanged. Publication receipts still require all existing compilation, JUnit, binding, source, input, coverage and comparison checks.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [ComparisonMutations.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/ComparisonMutations.java) | Generate bounded AST mutations and exact site probes using the pinned parser. |
| [comparison_mutation_sources.py](../../source/tools/behavior_verification/comparison_mutation_sources.py) | Pass disposable source plans to the Java mutation generator. |
| [comparison_mutations.py](../../source/tools/behavior_verification/comparison_mutations.py) | Verify the baseline, run mutations through the canonical comparator and persist classifications. |
| [comparison_strength.py](../../source/runtime/behavior_conversion/comparison_strength.py) | Bound the worker process tree and retain advisory results without changing acceptance. |
| [comparison_mutation_settings.py](../../source/models/comparison_mutation_settings.py), [executable_verification_settings.py](../../source/models/executable_verification_settings.py) | Define explicit opt-in measurement budgets. |
| [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py), [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py) | Attach measurement to verified executable candidates and fingerprint its policy. |
| [test_comparison_mutations.py](../../source/tests/test_comparison_mutations.py), [test_comparison_mutations_execution.py](../../source/tests/test_comparison_mutations_execution.py) | Check classification, bounds, worker handling, real defects, baseline rejection and unchanged candidate/build evidence. |
| This document | Record usage, validation and limits. |

The default checklist mode, original/native comparison rules, AI retry budgets, business sources and advisory PIT remain unchanged. Unrelated local changes were preserved. No live model conversion, full operation acceptance, commit or push was performed. The next milestone is failure routing and bounded-work integration.

Validation: all six Java 25 execution scenarios passed. They detected deliberate XML-prefix, removed-write, negated-condition and return-value changes; distinguished a real survivor, an uncovered helper and an invalid compilation; stopped before mutation generation on a failing baseline; and preserved the candidate through actual Maven compilation, JUnit, worker measurement and receipt validation. The scoped build integration passed again after limiting targets to current-unit files. The latest ten focused classification/scope/disabled/timeout checks passed. Regression selections passed 40 coverage/input/comparison tests and 22 staged tests (three staged-build/assembly cases outside that selection). Eleven existing advisory PIT/timeout checks passed, with the real PIT execution case outside that selection. These results validate the tested tooling boundaries, not bank-operation acceptance or exhaustive equivalence.

## Milestone 9 checkpoint — failure routing and bounded correction

Implemented on `codex/metadata-1` for the opt-in executable registered-stage path.

- Independent comparison feedback retains every proven difference from every executed failing case, with its exact input controls. Checklist IDs, whole observation dumps and unrelated limitations are excluded from production correction. All reports still retain limitations and unexecuted cases. Existing request-size checks stop an oversized correction as incomplete instead of silently dropping differences.
- The trusted typed adapter marks reflection wiring failures separately. Missing entry/accessor/constructor wiring can request a restricted adapter-plan correction. Exceptions thrown inside business constructors, factories, getters or entry methods do not gain that marker merely because they are reflective exceptions. Unrecognized invocation, observation and framework limitations remain incomplete.
- Adapter repair uses the existing persisted `adapter` role and frozen compiled production APIs. It cannot return Java or rewrite the implementation. After a repaired plan, metadata, selected test scope and structural evidence are checked again; the owning validator reruns compilation, tests and comparison. Valid test artifacts remain independently retained. A cached valid adapter may be revalidated without another model call.
- Proven boundary differences still return to implementation. Compiler diagnostics against production files escape the tests role; diagnostics already in the implementation role keep its ordinary bounded correction path. Tests-only failures retain their own existing budget.
- Native parser tooling failures, validation-time OS/process failures and build failures without usable compiler/test diagnostics stop as explicit limitations. They cannot cause speculative production changes. Candidate syntax errors and supported compiler/JUnit diagnostics retain their existing repair paths. Provider transport retries remain unchanged and consume the same durable logical role budget across resume.
- A persisted `failure_routes` record checks actual role-attempt progress before repeated implementation/adapter transitions. Changed feedback or cached failures cannot replenish attempts. No-progress cycles stop; a task also has a ceiling of eight times its configured role-attempt limit for these correction transitions. The ledger stores feedback hashes; detailed requests and validation evidence remain in their existing records. No successful artifact or counter is erased.
- Missing coverage still uses milestone 7's bounded deterministic expansion. Mutation survivors and measurement failures still use milestone 8's advisory reporting. They never enter the business correction loop. New routing policy is fingerprinted for reuse.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [failure_routing.py](../../source/runtime/behavior_conversion/failure_routing.py) | Classify known tool/compiler/adapter failures and bound cached correction transitions durably. |
| [adapter_repair.py](../../source/runtime/behavior_conversion/adapter_repair.py), [executable_adapters.py](../../source/runtime/behavior_conversion/executable_adapters.py) | Repair restricted invocation plans with the existing adapter budget and frozen production evidence. |
| [AdapterBindingFailure.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/AdapterBindingFailure.java), [TypedBoundaryAdapter.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/TypedBoundaryAdapter.java), [BoundaryHarness.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/BoundaryHarness.java) | Identify trusted reflection wiring failures without marking business-thrown exceptions as wiring errors. |
| [boundary_observation.py](../../source/models/boundary_observation.py), [executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py) | Retain adapter failure provenance and route it before a production correction. |
| [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py), [stage_tasks.py](../../source/runtime/behavior_conversion/stage_tasks.py), [generation.py](../../source/runtime/behavior_conversion/generation.py) | Dispatch role-specific corrections, revalidate affected artifacts and stop tool/budget failures. |
| [verification_feedback.py](../../source/runtime/behavior_conversion/verification_feedback.py), [verification_mode.py](../../source/runtime/behavior_conversion/verification_mode.py) | Collect all compared deltas and fingerprint routing policy. |
| [test_failure_routing.py](../../source/tests/test_failure_routing.py), [test_failure_routing_execution.py](../../source/tests/test_failure_routing_execution.py), [test_staged_failure_routing.py](../../source/tests/test_staged_failure_routing.py) | Inject failures to check termination, durable budgets, actual JVM provenance and role/artifact preservation. |
| This document | Record scope, validation and remaining limits. |

The default checklist mode, business sources, comparison/logging rules, role attempt limits, advisory PIT and mutation acceptance policy remain unchanged. Historical isolated thin-path orchestration is unchanged; the new repair integration belongs to the executable registered-stage pipeline. Unrelated local changes were preserved. No live provider conversion, operation acceptance, default rollout, commit or push was performed. The next milestone is acceptance trials on the three selected bank boundaries, followed by the full operation only when their checks pass.

Validation: the latest 43 focused failure-routing, comparison, coverage and mutation tests passed. A 41-test Java 25 routing/adapter/staged regression selection passed, with three staged-build/assembly tests outside that selection. New actual-JVM cases verified that a missing native method uses one adapter call and no implementation call, while a business-thrown reflective exception does not request adapter repair. The registered stage-flow injection passed with one implementation, one details, one tests and one adapter call; it revalidated and retained tests without regenerating production. The injected stage-flow validator is a flow fixture, not compilation or equivalence evidence.

The final two real Maven/JUnit executable-verification checks passed under Java 25: matching code retained valid acceptance evidence and the deliberate wrong-result candidate was rejected before publication. Two non-Maven cases in that file were outside this final selection. No bank-operation acceptance is established by these tooling tests.

## Milestone 10 checkpoint — guarded bank acceptance trials

The trial implementation is on `codex/metadata-1`. Rollout remains conditional on real acceptance results.

- Read the existing Mapper preparation and configuration database in read-only mode. Verify current bank source/configuration hashes before generation and validation. Historical evidence is not modified.
- Select exactly `GetClientLinksRQFmt`, `StandardErrorRSFmt` and `NoLinksFound` from `INTERNET/GetClientLinksOp`. Use fresh trial state, the registered staged pipeline and `executable_boundary_v1`, rather than the historical isolated thin-path comparator.
- Preserve actual production compilation, executed JUnit, binding/source/input checks, strict branch coverage, independent observations and acceptance-receipt validation. Every boundary must have an accepted receipt and at least one detected mutation in a completed comparison-strength measurement before the next gate can pass. Missing strength evidence remains incomplete; it does not redefine technical unit acceptance.
- Attempt the other selected boundaries after a per-boundary failure. Keep accepted, failed, incomplete and pending counts separate. No preparation or successful model response counts as acceptance.
- Only after all three boundaries and defect checks pass, start the existing fresh component-first pilot for the single full operation, including its normal technical checks and warm-reuse check. Require exactly one accepted operation and all its configured units accepted before reporting rollout readiness.
- Keep the current default mode unchanged while trials are pending or blocked. The runner never rewrites repository defaults or silently falls back to checklist mode.

### Files changed and why

| Files | Purpose |
| --- | --- |
| [bank_acceptance_trials.py](../../source/tools/behavior_verification/bank_acceptance_trials.py) | Orchestrate the three boundary trials, authoritative status and the guarded full-operation run. |
| [bank_trial_inputs.py](../../source/tools/behavior_verification/bank_trial_inputs.py) | Load historical Mapper evidence read-only and recheck actual source/configuration freshness. |
| [acceptance_trial_validation.py](../../source/tools/behavior_verification/acceptance_trial_validation.py) | Reuse the real registered build/JUnit/executable comparison ladder before trial publication. |
| [acceptance_trial_gates.py](../../source/tools/behavior_verification/acceptance_trial_gates.py) | Require all boundary/defect results and actual full-operation counts before rollout readiness. |
| [test_acceptance_trial_gates.py](../../source/tests/test_acceptance_trial_gates.py), [test_acceptance_trial_validation.py](../../source/tests/test_acceptance_trial_validation.py) | Reject incomplete rollout claims and exercise actual Maven/JUnit/comparison receipt validation. |
| This document | Record implementation, command, validation and actual trial outcome. |

Command: `PYTHONPATH=source python -B -m tools.behavior_verification.bank_acceptance_trials --input-run outputs/single-operation-full-current-20261031-052006/single-get-client-links --output outputs/bank-executable-acceptance-m10-20261031`.

Validation: the two rollout-gate tests and the real Java 25 Maven/JUnit/comparison/receipt integration test passed. Bank evidence freshness and configured provider readiness passed. The live run uses the saved Gemini 3.7 Flash profile, 300-second call timeout and 900000-character request budget. Actual progress is retained in `outputs/bank-executable-acceptance-m10-20261031/acceptance-trials.json`; no live boundary or operation acceptance is implied by these infrastructure tests.

The live trial ended blocked: zero accepted boundaries, three failed generation attempts at the boundary level, zero incomplete-verification records and no pending boundaries. `GetClientLinksRQFmt` and `StandardErrorRSFmt` each exhausted four provider transport attempts on HTTP 503 high-demand errors. `NoLinksFound` exhausted four transport attempts, ending on HTTP 429: the reported free-tier quota was five requests per minute. The quota message names `gemini-3.8-flash`; the configured/requested model remained `gemini/gemini-3.7-flash`. No successful response identifies a generated candidate or proves a different model was used.

The persisted database has one failed logical implementation-role call per boundary and no candidate responses. Therefore the bank candidates never reached production compilation, JUnit, output comparison, mutation measurement or acceptance-receipt creation. The full-operation gate remained closed, rollout readiness is false, and the default remains `checklist_v1`. Infrastructure implementation and fixture validation passed; bank acceptance and default rollout are not complete.

Next action: retry within retained role budgets after provider availability recovers and the reported quota window resets. Do not restart into fresh state merely to reset counters, weaken checks or switch models/billing silently. Repository defaults, business sources and unrelated work remain unchanged. No commit, push or deployment was performed.

### Requested Flash Lite rerun

The user requested `gemini/gemini-3.7-flash-lite`. The runner now accepts an explicit `--model-name` override, so a saved historical profile cannot silently keep the prior Flash model. Optional `--prior-trials` copies only a stopped, provider-only ledger into fresh trial output; it preserves role counters and rejects relocated candidates or inherited acceptance claims. Historical state remains read-only. These focused additions are in [bank_acceptance_trials.py](../../source/tools/behavior_verification/bank_acceptance_trials.py) and [acceptance_trial_state.py](../../source/tools/behavior_verification/acceptance_trial_state.py), with counter/history tests in [test_acceptance_trial_state.py](../../source/tests/test_acceptance_trial_state.py). All four counter-inheritance and rollout-gate tests passed.

The rerun at `outputs/bank-executable-acceptance-lite-20261031` ended blocked: all three provider generation calls exhausted four transport attempts on HTTP 404 for the requested model ID. Zero candidates were returned and zero boundaries were accepted. No bank compilation/JUnit/comparison/defect checks or full-operation conversion ran. Total retained implementation-role attempts advanced from 1 to 2 per boundary; the prior database hash was unchanged. One response boundary received a different stage revision, so the rerun helper also enforces the inherited implementation budget across revisions before another provider call. A failure-injection test checks that a revision change cannot replenish that budget.

An authenticated model-list request returned `gemini-flash-lite-latest`, `gemini-2.5-flash-lite`, `gemini-3.1-flash-lite-preview`, `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` among text Lite options; it did not list the requested 3.7 Lite ID. Model substitution requires the user's selection. The default verification mode, source code, technical gates and retry limits were not changed. No commit, push or deployment was performed.

### Gemini 3.5 Flash Lite rerun

At the user's request, [constants.py](../../source/constants.py) now selects `gemini/gemini-3.5-flash-lite`. The acceptance runner explicitly used that model, the same 300-second timeout, inherited provider-only state and unchanged technical checks. Results are in `outputs/bank-executable-acceptance-flash35lite-20261031`.

The run ended with zero accepted and three verification-incomplete boundaries. This time the provider returned six implementation responses, two per boundary. Both formatters initially retained IBM dependencies; their corrections recreated a generic Composer `Context` runtime. The guards rejected these before compilation. `NoLinksFound` initially retained IBM dependencies; its correction passed production compilation but exposed `execute(Map<String,Object> context)`, which failed the typed public-boundary check. The production compile receipt recorded zero tests. No JUnit, independent output comparison, mutation checks or full-operation run occurred.

The inherited four-call implementation budget stopped further correction: earlier provider failures had consumed two logical calls per boundary. A changed response-format stage revision caused one additional reservation, but the inherited aggregate-budget guard blocked it before a provider call. Historical state hashes remained unchanged. No acceptance policy was relaxed and no output-equivalence claim can be made.

The next investigation concerns the production-generation contract: concrete native typed boundaries must guide code generation so source framework classes remain behavior evidence rather than copied APIs or replacement Context/Map engines. Validation already rejects the invalid shapes. Default-mode rollout remains blocked. No unrelated source change, commit, push or deployment was performed.

### Controlled comparison with Gemini 3.5 Flash

The user requested a stronger available model while keeping the same request and validation checks. After an initial Pro-model lookup, the user explicitly selected `gemini/gemini-3.5-flash`; its authenticated model entry listed `generateContent` support. No Pro generation was performed.

The first Lite `GetClientLinksRQFmt` implementation request was read from retained state, not rewritten. [frozen_model_request.py](../../source/tools/behavior_verification/frozen_model_request.py) reproduces the original generator fingerprint against the reconstructed instructions, complete retained payload and baseline settings. [model_comparison_replay.py](../../source/tools/behavior_verification/model_comparison_replay.py) verifies identical live inputs before replaying the frozen serialized request, routes the response through the same registered pipeline, and prevents any additional correction or later-stage provider call. Three [fingerprint tests](../../source/tests/test_frozen_model_request.py) passed. Production prompts and validators were not changed.

The isolated comparison at `outputs/bank-model-comparison-flash35-20261031` made one logical provider call. Flash returned 6975 response characters in 70.5 seconds. Its raw response was rejected at JSON parsing: the Markdown closing fence was attached to the JSON closing brace, while the unchanged normalizer requires a separate closing-fence line. Compilation and typed-boundary/JUnit/output checks therefore did not run. The earlier Lite response had reached and failed the IBM-dependency source guard.

Read-only inspection of the enclosed JSON found a typed request DTO with written-presence flags, a DTO-returning `unformatToDto` method, and additional public Map/Object overloads. This diagnostic inspection did not bypass response parsing or count as validation. The result shows different output from Flash but does not establish model choice as the sole cause, nor prove the generated API or behavior correct. No typed API contract was added to this experiment. Original trial state/counters and the Lite application default remain unchanged; no commit, push or deployment occurred.

### Narrow wrapper fix and saved-response replay

The user authorized accepting an enclosing Markdown wrapper whose closing marker is attached to the JSON closing brace. [managed_conversion_response.py](../../source/runtime/managed_conversion_response.py) changes only that fence matcher's closing-newline requirement. The opening fence and whole-response match remain constrained. JSON/schema validation still rejects malformed JSON, extra surrounding text and multiple response bodies. Embedded Java strings are not rewritten.

[test_managed_conversion_response.py](../../source/tests/test_managed_conversion_response.py) adds same-line/LF/CRLF closing cases, malformed/mixed-content rejections and preservation of embedded Java markers and escape sequences. The relevant response parsing, structural escape, service-response parsing and fingerprint selection passed 35 tests. One broader service-flow correction test failed; the exact test also failed with the original fence matcher restored in-memory, so unrelated service logic was not changed.

[model_comparison_replay.py](../../source/tools/behavior_verification/model_comparison_replay.py) now accepts a saved-response option, delivers it once through the existing registered stages, preserves the raw bytes and stops before any later provider request. The replay at `outputs/bank-model-wrapperfix-replay-20261031` made zero AI calls. Its original response bytes and retained Java source contents matched exactly. JSON parsing, production-source guards and real Java production compilation passed.

The replay reached the subsequent semantic-details/binding stage, for which no saved output exists. It stopped rather than generating or inventing missing artifacts. Typed-boundary acceptance, JUnit and behavior comparisons remain unperformed; compilation alone is not unit acceptance. No bank response formatter, generated Java, prompt, schema or business gate was changed. Existing unrelated work, trial counters and default model were preserved. No commit, push or deployment occurred.

### Configured executable mode and frozen-candidate acceptance continuation

At the user's request, [bank-demo/scoped_converter_validation.yaml](../../bank-demo/scoped_converter_validation.yaml) explicitly selects `executable_boundary_v1`, staged conversion and Gemini 3.5 Flash. Other profiles and the globally available legacy mode remain unchanged. This is a bank-profile selection, not an assertion that the bank acceptance milestone has passed.

The staged pipeline can now revalidate a saved implementation instead of generating it. Its code content hash must match the saved production compile proof; the stage artifact fingerprint remains a separate input/request identity. Any later interface or behavior failure that requires changing production stops the frozen continuation. Metadata, bindings and tests keep their own existing bounded roles. A no-response tooling/provider error is not supplied as fake code-correction feedback when resuming the executable mode.

| Files | Purpose |
| --- | --- |
| [frozen_implementation.py](../../source/runtime/behavior_conversion/frozen_implementation.py), [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py) | Revalidate hashed frozen production, skip implementation generation, and refuse later Java corrections. |
| [generation.py](../../source/runtime/behavior_conversion/generation.py) | Suppress false code-correction context when the previous executable-mode attempt returned no model output. |
| [frozen_trial_state.py](../../source/tools/behavior_verification/frozen_trial_state.py), [continue_frozen_trial.py](../../source/tools/behavior_verification/continue_frozen_trial.py) | Verify saved compile/content proof, copy stage state read-only, preserve counters and continue later roles with current configured model/mode. |
| [acceptance_trial_validation.py](../../source/tools/behavior_verification/acceptance_trial_validation.py) | Bind structural evidence to the complete current code-and-tests bundle, preventing test addition from being misreported as a changed implementation. The full candidate hash guard is preserved. |
| [test_frozen_implementation.py](../../source/tests/test_frozen_implementation.py), [test_frozen_trial_state.py](../../source/tests/test_frozen_trial_state.py), [test_acceptance_trial_validation.py](../../source/tests/test_acceptance_trial_validation.py) | Test mutation refusal, no implementation calls, stopped production corrections, retained counters, content-proof integrity, clean no-response resume and real complete-bundle Maven/JUnit/receipt checks. |
| This document and new run reports | Record actual progress, limits and remaining blocker. |

Validation: the 35-test frozen/routing/staged selection passed (three separate staged-build/assembly cases were outside that selection); 30 state/fingerprint/parser tests passed; focused no-response-resume/integrity checks passed; and the complete-bundle regression passed with real Java 25 Maven/JUnit and receipt validation.

Live continuation: `outputs/bank-frozen-acceptance-flash35-20261031` generated valid details/binding and a final test bundle, without generating implementation. The four test calls included two malformed replies and a non-public class correction. Nine JUnit tests passed. Comparison first stopped on a trial bookkeeping hash taken before tests were added. That validator ordering was fixed, without weakening or excluding tests from the hash.

The read-only-state resume at `outputs/bank-frozen-acceptance-flash35-validationfix-20261031` made zero new AI calls and reran the retained nine tests successfully. The saved implementation, original compiled-state database and first-continuation database remained unchanged. Comparison then stopped at native instrumentation: an uncontrolled reflective invocation in an object-context compatibility helper caused rejection before any of 81 planned cases executed. The selected DTO method calls the map overload, not that object-context overload. This is a native harness scoping limitation, not an observed business difference. No unit or operation was accepted.

Next action: safely scope native instrumentation to the selected boundary, adapter-accessed DTO members and reachable code, keeping reachable uncontrolled reflection blocked. Do not regenerate the frozen implementation or globally allow reflection to bypass this failure. No bank response formatter, unrelated business code, acceptance rule, retry limit, commit, push or deployment was changed.

### Explicit no-reflection production policy and corrected-candidate replay

The user subsequently rejected reflection anywhere in generated production, including unused helpers. This supersedes the instrumentation-scoping proposal above. Known source targets must become direct typed calls. Runtime-selected targets require an evidence-based typed interface/factory/dispatcher. Unknown targets remain unresolved. The converter-owned controlled harness may still use reflection. Its existing resolved-call guard is unchanged.

| Files changed for this requirement | Reason |
| --- | --- |
| [native_reflection_policy.py](../../source/runtime/behavior_conversion/native_reflection_policy.py) | Shared generation rule and early production-source checks for reflective APIs, Class lookups, dynamic proxies, method handles and known reflective property helpers. Comments/literals and test-owned harness sources are excluded; ordinary typed dispatcher methods named `invoke` are permitted. Existing resolved-call verification remains required. |
| [bundle_output.py](../../source/runtime/behavior_conversion/bundle_output.py) | Apply the source policy before candidate compilation, including unused production helpers. |
| [native_instructions.py](../../source/agents/behavior_conversion/native_instructions.py), [staged_instructions.py](../../source/agents/behavior_conversion/staged_instructions.py), [side_road_instructions.py](../../source/agents/behavior_conversion/side_road_instructions.py) | Apply the same rule to ordinary, staged, baseline and simplification generation/corrections. |
| [continue_frozen_trial.py](../../source/tools/behavior_verification/continue_frozen_trial.py) | Accept an explicitly supplied corrected implementation, record its separate hash and freeze it during fresh compile/test/comparison. Preserve historical source hashes and inherited counters. |
| [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py), [test_frozen_implementation.py](../../source/tests/test_frozen_implementation.py) | Explicit saved-test replay runs the same tests-only scope, API, build and comparison validators without a provider call or counter reset. Invalid supplied tests stop; they cannot be treated as passing or trigger regeneration. |
| [test_native_reflection_policy.py](../../source/tests/test_native_reflection_policy.py) | Exercise forbidden APIs/dead helpers, typed dispatch, non-code text, source scope, central validation and all prompt paths. |
| This document and new output artifacts | Record the authorized correction, provenance and observed acceptance outcome. |

The new artifact at `outputs/bank-typed-no-reflection-20261031/corrected-implementation.json` replaces the request formatter's reflective Object-context overload with a `GetClientLinksRequest` overload and direct setters. The selected `unformatToDto` method, existing DTO and parsing/decorator logic are unchanged. No dispatcher is necessary because the target type is known. Historical artifacts/databases are read-only. No original Composer source, harness guard, retry budget, unrelated code, commit or push was changed.

Validation so far: 55 focused policy, frozen-state, staging and side-road regression tests passed. The fresh acceptance replay uses the configured `gemini/gemini-3.5-flash` in `executable_boundary_v1`, retains prior counters and revalidates passing tests rather than trusting their old receipts. Live outcome is recorded in `outputs/bank-typed-no-reflection-20261031/acceptance/continuation.json`; compilation or passing tests alone do not establish acceptance.

The first replay compiled production and received updated binding information from Gemini 3.5 Flash. Two retained tests still called the removed Object-context compatibility API, so test compilation failed before comparison. The existing four-call test budget remained exhausted; no extra test-model call was made. The corrected replay at `outputs/bank-typed-no-reflection-20261031/corrected-replay` updates only these tests to the typed DTO API, retaining the same value and null-target assertions and removing the obsolete reflective test target. The typed overload preserves the prior null-target no-write behavior after parsing. Explicit supplied tests must pass every fresh validator; this is not an old passing receipt. The additional frozen-test flow tests cover both successful validation and refusal of invalid supplied test sources (26 focused tests passed).

Final corrected replay: production compiled and all nine JUnit tests passed. All 81 original/native cases executed: eight matched, zero established differences, 73 incomplete, zero unexecuted. Reflection no longer blocks instrumentation. Every incomplete case reports `Unsupported observable type: com.company.generated.thinpath.GetClientLinksRequest` while capturing the native output. The eight observed matches are mandatory-input exception cases, not successful DTO-output equivalence. No unit or operation was accepted.

The next correction belongs to binding selection: the legacy unformat entry returns no output and writes context fields. The selected native method returns a DTO representing those fields. The generated binding already projects `ClientId` and `BankId` through getters/presence flags, but additionally requests the entire DTO as `output=result` with no output getter. For this void legacy boundary, compare the projected context writes and select no separate observable return (`output=none`), validated against the original entry contract. Do not enable arbitrary DTO serialization or change business parsing to hide this limitation. Branch/path coverage diagnostics also remain unresolved; fixing output capture alone is not full acceptance.

Both replays used Gemini 3.5 Flash for one binding-details call each. Neither regenerated implementation or tests with AI. Inherited counters remain implementation 1, binding details 4, tests 4; the historical failed test-call stage remains recorded while the supplied corrected tests have their own fresh nine-test proof. The original compiled database, each resumed source database and corrected production during validation remained unchanged. All build, JUnit, source/API, comparison and coverage gates remain enabled. No unrelated source/configuration or original Composer behavior was modified.

### Source-derived context-only request output binding

The user authorized fixing this binding and rerunning acceptance without regenerating implementation. [verification_binding.py](../../source/runtime/behavior_conversion/verification_binding.py) now derives `output=none` and an empty separate-output getter path when the boundary is a request unformat, the resolved original declaration returns `void`, and context-write projections exist. It preserves every projected getter, presence accessor, argument and settings binding. Other boundary kinds, non-void originals, missing original declarations and bindings without projections are unchanged.

[executable_verification.py](../../source/runtime/behavior_conversion/executable_verification.py) applies this binding before the existing structural checks and execution. Original source/configuration provenance is still checked before execution. [test_context_only_binding.py](../../source/tests/test_context_only_binding.py) covers preservation of projected fields, removal of the extra return path, idempotence, nonmutation and all unchanged cases. This document records the reason and trial outcome. No production Java, saved tests, response/step output behavior, retry limit or historical run artifact was changed.

The replay is `outputs/bank-context-only-binding-flash35-20261031`, using the same saved corrected implementation and nine-test bundle, with Gemini 3.5 Flash configured. It copies the previous stage state read-only and revalidates cached binding details instead of resetting exhausted role counters or regenerating code. All build, JUnit, original/native comparison, coverage and mutation gates remain required.

Outcome: 37 focused regression tests passed. Fresh production compilation and all nine saved JUnit tests passed. All 81 original/native cases matched: 73 successful-input cases and eight exception cases, zero differences, zero incomplete cases, zero unexecuted cases and no comparison limitations. The whole-DTO output capture blocker is resolved.

Acceptance remains `verification_incomplete` at the separate coverage gate: nine original branch outcomes were not exercised and one abstract `child.unformat(xml, context)` dispatch remains unbounded in the original call graph. Coverage expansion stopped with `no_new_supported_inputs` and added zero cases. The missing outcomes concern XML element traversal, padding setup/left-padding choices and CCXML configuration flags. Next, prove which setup outcomes are fixed by the selected XML, resolve the configured child types from that same evidence, and add cases for any genuinely reachable input-dependent gaps. Do not waive coverage or alter production to address this analysis limitation. Mutation-strength validation was not reached because coverage failed first. No unit or full operation was accepted.

No new model calls were needed; the saved Gemini 3.5 Flash binding was revalidated with the deterministic return projection. Production hash `8885d388d4cdd48012c35a0cb64dfdab84e6e60e7a24623b2693ab346991d754` was unchanged. Original and resumed source databases remained unchanged, and role counters stayed implementation 1, binding details 4, tests 4. No original Composer code, saved implementation/tests, configuration, unrelated behavior, commit or push was changed.

### Configuration-aware preparation and current coverage-gap resolution

The user authorized combining the current-gap investigation with deterministic preparation before comparison inputs are generated. Eight of the nine missing outcomes concern initialization attributes or private boolean fields set exclusively during configured initialization. The ninth is the false side of a DOM element traversal predicate; leading XML whitespace provides an actual input that can exercise it. The unresolved abstract call iterates a private child list populated by the converter-owned configured-tree harness.

| Files changed | Reason |
| --- | --- |
| `source/behavior-verification-java/src/main/java/il/co/dcd/verification/ConfigurationPreparation.java` | Orchestrate original-source preparation without executing candidate code or asking AI for proof. |
| `ConfiguredBranchPreparation.java` in that package | Prove a narrow set of pure Tag lookup predicates and private setup-only boolean fields over every relevant configured occurrence. Verify the ordinary Map reader/copy constructor from source; reject mutation, runtime reinitialization, unknown getters, escaping state and unsupported expressions. |
| `ConfiguredDispatchPreparation.java` in that package | Resolve private final child-list dispatch only when registration matches the trusted harness protocol, configured class hierarchies are supplied, registration is not overridden, and reachable source cannot mutate or expose the list. Unknown patterns remain unresolved with diagnostics. |
| `StaticConstantValues.java`, `StaticCheckAnalysis.java`, `source/tools/behavior_verification/static_analysis.py` | Carry typed field constants and the expanded effective configuration through the existing JavaParser analysis protocol. |
| `source/models/unit_verification_boundary.py`, `source/tools/behavior_verification/configured_preparation.py` | Retain tool-owned preparation with exact source/configuration revisions and validate proof identities, predicates and configured targets. |
| `source/runtime/behavior_conversion/executable_verification.py` | Prepare before generating comparison cases; runtime observations contradicting a fixed-configuration proof are a tooling blocker, never an AI code correction. |
| `source/tools/behavior_verification/boundary_coverage.py`, `source/runtime/behavior_conversion/coverage_receipts.py` | Keep raw expected/observed outcomes and separate configured exclusions. Retain dispatch evidence, recompute coverage from probes and prepared inventory, and reject stale or contradictory proof. No fabricated execution coverage. |
| `source/tools/behavior_verification/input_scenarios.py` | Prepare an additional leading-whitespace request before execution, preserving the original component configuration and all case/size limits. |
| `source/tests/test_configured_preparation.py` and this document | Positive and adversarial proof, provenance, input preparation and receipt tests; record implementation and acceptance evidence. |

This is source/configuration analysis, not a new Composer runtime or a formatter-specific exception list. Generated implementation, saved tests, model selection, retry budgets and comparison semantics are unchanged. Unsupported configurations/calls remain blocking. Final coverage is still checked after execution; source-proven excluded outcomes are explicitly distinguished from observed outcomes. All existing build/JUnit, comparison and defect-detection checks remain enabled.

Validation on 2026-11-01: the broader real-build/input/comparison regression selection passed 28 tests; the proof/exclusion/coverage compatibility selection passed 36 tests; the final eight configured-preparation tests passed after the short-circuit predicate correction. These selections overlap. Adversarial tests reject mutable fields, impure Tag getters, runtime reinitialization, runtime child additions, stale source/configuration proof and contradictory probes, even if both outcomes appear in a reported run. The bank preflight at `outputs/bank-configured-preparation-preflight-20261101` proves eight predicates and closes one dispatch; replaying prior observations leaves only the DOM traversal gap. It prepares 82 cases before execution.

The fresh replay at `outputs/bank-configured-preparation-acceptance-flash35-20261101` is **accepted for GetClientLinksRQFmt only**. Production compiled, all nine saved JUnit tests passed, and all 82 original/native cases matched (zero differences, incomplete cases, unexecuted cases or comparison limitations). All relevant original branch outcomes are either observed or explicitly excluded by one of the eight source/configuration proofs; there are zero remaining coverage gaps, unresolved calls or contradictory observations. The new leading-whitespace case actually exercises the DOM predicate's missing false outcome. The original conservative call graph remains intact; its one open child dispatch has separate configured-tree proof in coverage evidence. The acceptance receipt was validated before persistence.

The full 82-case advisory mutation measurement reached its existing 120-second wall-clock limit after verifying the unchanged baseline. It recorded one incomplete mutant as a tooling failure and three pending; that timeout report/receipt remains unchanged. A separate, explicitly scoped four-input smoke used the same unchanged candidate, four selected cases from the accepted 82-case report (ordinary success, exception, leading whitespace and null-valued context), the same four-mutation cap and 120-second limit. It completed and detected all four deliberately changed implementations (a negated condition, two changed literals and a removed write), with no survivors, invalid mutants or tooling failures. Its evidence is under `defect-smoke`; it is a focused detector check, not exhaustive mutation coverage or a replacement for the timed-out full-case measurement.

Gemini 3.5 Flash remained configured, with zero new AI calls. Implementation hash `8885d388d4cdd48012c35a0cb64dfdab84e6e60e7a24623b2693ab346991d754`, saved tests, original/resumed databases and role counters (implementation 1, binding details 4, tests 4) were preserved. Disposable mutants never replace production. No configuration, original Composer code, unrelated behavior, commit, push or deployment was changed. No full-operation or production acceptance is claimed; the response formatter, OP step and operation assembly were not rerun here.

### Bounded mutation execution, early detection and verified baseline reuse

The user authorized a 10-minute total mutation budget, retaining per-case protection, stopping a deliberately broken implementation once a valid difference is observed, and safely reusing an already verified baseline.

| Files changed | Purpose |
| --- | --- |
| [comparison_mutation_settings.py](../../source/models/comparison_mutation_settings.py), [bank profile](../../bank-demo/scoped_converter_validation.yaml) | Set the default and selected bank comparison-mutation total timeout to 600 seconds. Preserve the existing opt-in flag, four-mutant default and upper bounds. |
| [continue_frozen_trial.py](../../source/tools/behavior_verification/continue_frozen_trial.py) | Apply the currently selected mutation timeout when continuing a historical profile; do not silently retain its old explicit 120-second value. Other historical settings/counters remain unchanged. |
| [boundary_verification.py](../../source/tools/behavior_verification/boundary_verification.py) | Keep normal full-case execution as the default. Explicit mutation-only early stopping requires independent comparison and no coverage expansion, and occurs only after a completed, limitation-free observable difference. Report remaining cases as unexecuted. Keep the existing 15-second timeout for each JVM side of a case. Capture and recheck runtime provenance. |
| [comparison_environment.py](../../source/tools/behavior_verification/comparison_environment.py) | Fingerprint comparison code, Java launcher/constants, JDK binaries/runtime libraries, Python/package versions, controlled working directory and relevant JVM/identity/locale options. Environment option values are hashed, not recorded. |
| [mutation_baseline.py](../../source/tools/behavior_verification/mutation_baseline.py) | Reuse only a complete matched report with its exact hash, original/native source sets and content, configuration, ordered input/control cases, bindings, dependency files, tool and runtime fingerprint. Missing, old, altered or mismatching evidence triggers a fresh full baseline. Compiled baseline directories are not reused. |
| [comparison_strength.py](../../source/runtime/behavior_conversion/comparison_strength.py), [comparison_mutations.py](../../source/tools/behavior_verification/comparison_mutations.py) | Pass only the producer's hash-verified baseline reference, pin the worker to the same working directory, retain reuse/fallback reasons, use bounded early stopping for mutants, and record executed/unexecuted case counts. Preserve process-tree timeout cleanup and advisory scoring. |
| [test_mutation_baseline.py](../../source/tests/test_mutation_baseline.py), [test_mutation_stopping.py](../../source/tests/test_mutation_stopping.py), existing comparison mutation tests | Reject changed reports, inputs, configuration, sources, candidate manifests, bindings, dependencies, tools and environments; test fingerprint changes, missing provenance fallback, real-JVM early stopping, limitation handling, unchanged normal full runs and actual worker reuse. |
| This document and new validation artifacts | Record scope and measured outcomes. |

The 33-test mutation/reuse selection passed, including real JVM and normal build-to-worker integration. The 24 fingerprint/policy unit tests also passed after the additional runtime-version/library fingerprinting (selections overlap). Mutation detection remains advisory, not exhaustive equivalence; survivors and tooling failures retain their original meanings. Main acceptance still executes every case and retains all build, comparison, coverage and source/API checks. Generated implementation/tests, model/API timeouts, AI retry budgets, PIT policy, unrelated source and historical reports are unchanged.

The full saved 82-case bank workload was validated under the selected 600-second cap at `outputs/bank-mutation-budget-validation-20261101`. The first run correctly refused the old baseline's missing runtime provenance and executed a fresh full baseline: all 82 cases matched. Four deliberate mutants were then detected; each executed one completed, limitation-free witness case and explicitly recorded the remaining 81 cases as unexecuted. No timeout, survivor, invalid mutant or tooling failure occurred.

The second run reused that newly verified exact baseline (`baseline_reuse_reason=exact_verified_baseline`), created no replacement baseline directory and again detected all four mutants after one case each. Both measurement processes returned successfully within their 600-second limits. These checks validate timeout wiring, conservative fallback, real reuse and mutation-only early stopping; they do not regenerate implementation or claim exhaustive mutation/operation acceptance. The prior accepted boundary report and prior timeout/smoke reports remain unchanged.
