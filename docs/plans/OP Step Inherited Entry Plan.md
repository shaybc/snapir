# OP Step Inherited Entry Plan

Status: implemented in the working tree. The Java resolver, framework-boundary policy, and Composer Manual integration are unchanged.

## Objective and scope

Allow a configured OP step to use execution and business methods declared anywhere in its actual application inheritance chain. A concrete OP-step class must not be required to declare either `execute()` or a Composer business hook itself. Preserve the implemented Framework Boundary Plan and existing Composer Manual integration.

This is a correction to the handoff from resolved analysis into component conversion. Do not introduce a second framework-boundary design, prescribed superclass sequence, class-name registry, fixed inheritance depth, or hardcoded hook-dispatch recipe. Names such as `CCStoredProcedure` and `CCOperationStep` illustrate production cases; they are not matching rules.

## What the reviewed code establishes

- `boundary_contracts.py` defines the original configured-step entry as public instance `int execute()` with no parameters. The implementation comes from the resolved binding, explicit configuration, or existing mapping.
- `EntryMethod.resolve` prefers a declared matching method and otherwise examines inherited methods through JavaParser. Its existing framework branch records a resolved method supplied only by a configured framework JAR without requiring source.
- `ReachableSlice.analyze` already distinguishes a source-backed execution body from binary framework orchestration. For binary orchestration it includes supplied application methods on configured classes and their ancestors as potential roots. This is conservative evidence, not proof of the exact proprietary call sequence.
- `CallBindings` already records source calls and possible virtual dispatch targets. Preserve its uncertainty and unbounded-path reporting.
- `component_sources` already includes declared supporting application sources and validates them against their recorded identities and hashes.
- `build_component_request` currently selects ordinary method entry evidence by the concrete implementation source identity/hash. Its checklist selection is similarly rooted in the concrete source except for existing format-specific handling. An inherited application execution body or business hook can therefore be present in supplied supporting sources and the graph, yet be omitted from step request obligations.
- Framework ownership, compact framework metadata, embedded Composer Manual delivery, output rejection rules, and original-side JAR execution already exist. Reuse them unchanged.

## Implementation steps

### 1. Establish focused failing regression cases

Add isolated OP-step fixtures that exercise the real analyzer and request builder without depending on the older component fixture that expects helpers to be standalone conversion targets.

Cover these variations:

1. The concrete class declares `execute()`.
2. The concrete class inherits source-backed `execute()` through multiple application ancestors and declares no execution method itself.
3. A source-backed wrapper invokes a business hook implemented in an intermediate application superclass; the concrete class inherits both methods.
4. A concrete subclass overrides that hook; the analysis must retain the relevant dispatch evidence without asserting that every possible target definitely executes.
5. The execution wrapper exists only in a configured framework JAR, while an intermediate application superclass supplies business behavior. Include a concrete class with no local method declarations.
6. Multiple framework JARs and different superclass depths preserve the existing ownership and source-less-framework behavior.

Vary class names and hierarchy depths. Include a Composer-style hook in a fixture, but do not turn its spelling, visibility, or position into a new converter rule. Include `throws Exception` to establish that an exception declaration does not disqualify the execution method.

### 2. Select inherited step evidence from the existing analyzed graph

Add a small step-specific selection helper and call it from component request construction for both reusable step implementations and configured occurrences.

- Use the selected original boundary, its resolved declaring-method record, graph roots, reachable nodes/edges, and the application sources already supplied for that component.
- Include the source-backed inherited execution entry when its identity/hash matches supplied evidence, rather than requiring it to belong to the concrete class source.
- Retain the analyzed application business-method and checklist obligations needed for that entry, including inherited supporting-source methods. Keep source identity/hash checks authoritative.
- Use graph relationships and existing configured receiver/framework evidence to determine relevance. Do not select every method from every supplied class just because its source is available. Retain conservative candidates where the existing binary-framework path cannot establish an exact call sequence.
- Keep original invocation entry metadata distinct from reachable business-method obligations. A business hook may be protected or have another signature; it does not need to satisfy the public `int execute()` boundary contract.
- Preserve the current payload schema where its existing fields suffice. Keep source-backed entry records tied to real supplied code. Preserve separate framework-boundary records for binary execution methods.
- Keep utility/supporting classes as evidence within their existing component, not new standalone conversion targets.
- Leave format and decorator evidence selection unchanged.

### 3. Preserve resolution and failure semantics

Keep inherited-method resolution as the authoritative execution check. Do not remove the check or replace it with an assumption that any configured class is executable.

A missing local declaration is not an error. A resolved framework method without source remains non-blocking under the current framework policy. Real unresolved implementation bindings, missing non-framework dependencies, invalid original signatures, conflicting matches, or changed application sources retain their existing validation.

If a step still lacks usable evidence, carry through the actual recorded analysis issue or resolved declaring-method context. Do not replace an analyzer failure with a generic missing-concrete-method explanation. Preserve the recently implemented inactivity timeout and explicit analysis/dependency failure links.

Do not change the Java resolver or call graph speculatively. If a new regression demonstrates a separate resolver/dispatch defect, isolate that defect and its smallest file-level fix before expanding this scope.

### 4. Check generation, validation, and saved-result reuse

Trace the selected evidence through request construction, source authorization, generated-test requirements, cached component validation, and whole configured-step comparison. Both implementation groups and occurrence groups must receive the corrected obligations.

Existing reuse checks already compare `source_entry_points`, parser checklists, generation policy, and requirements. Use those checks to revalidate or regenerate only results whose obligations change. Do not bump global source/map identity or clear caches to force this fix through.

Add a regression that a saved result omitting inherited business obligations is not accepted solely because it passed its old tests. Also verify unchanged requests/results remain compatible under existing rules.

The same saved run must remain resumable with its existing profile and framework JAR settings. No fresh intake, capture, Composer mapping, or manual database edits should be needed for this request-building correction. Normal freshness verification remains in place; this plan does not redesign resume caching.

### 5. Verify existing framework behavior remains intact

Run the existing framework-boundary regression suite alongside the new tests. Verify all of the following:

- Framework ownership still comes exclusively from configured JAR inventories, not package-name guesses.
- Source overrides remain application code.
- Missing framework source does not prevent conversion preparation.
- Generation receives the existing Composer explanations once through the established knowledge path, plus relevant compact framework metadata; no new handwritten per-class contracts or JAD/decompilation requirement is added.
- Framework classes are not converted, copied, shadowed, or retained in generated native production dependencies.
- Original-side comparisons execute with the real framework JARs. Native code is judged by equivalent business behavior and the existing verification policy.
- Analysis uncertainty and failures retain their existing meaning. Compilation alone does not establish equivalence.
- Formats, decorators, framework-only configured steps, and successful saved-result reuse retain their current behavior.

## Expected files to change:

The following paths define the implemented scope. The conditional Java/runner changes listed below were not needed.

- [requests.py](../../source/runtime/component_conversion/requests.py): integrate inherited step evidence selection into method and checklist obligations, without altering format selection or framework/manual attachment.
- [step_entry_evidence.py](../../source/runtime/component_conversion/step_entry_evidence.py) (new): select and validate relevant inherited application evidence using existing boundary/graph/source records. Do not resolve framework ownership or interpret proprietary wrapper behavior here.
- [test_step_inherited_entries.py](../../source/tests/test_step_inherited_entries.py) (new): cover varied source-backed and JAR-backed inheritance, request construction, source authorization, obligations, and affected/unchanged reuse behavior.
- [test_framework_boundaries.py](../../source/tests/test_framework_boundaries.py): add the multi-level binary-wrapper/application-superclass handoff regression while preserving current tests.
- [running_migrations.md](../running_migrations.md): document that inherited OP-step methods are supported and the same run can resume; no new configuration is introduced.

Conditional files, only if focused tests expose a defect in their own behavior:

- [EntryMethod.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/EntryMethod.java): only a demonstrated inherited-entry resolution defect, retaining the existing framework branch and exact execution contract.
- [CallBindings.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/CallBindings.java): only a demonstrated source dispatch defect; preserve conservative uncertainty and avoid class-specific hook rules.
- [ReachableSlice.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/ReachableSlice.java): only a demonstrated missing application-ancestor root or graph handoff; preserve binary framework orchestration semantics.
- [test_behavior_verification_boundaries.py](../../source/tests/test_behavior_verification_boundaries.py): extend resolver regression coverage if the Java resolution path requires a change.
- [runner.py](../../source/runtime/component_conversion/runner.py): only if tests show the existing saved-obligation comparisons fail to reject an affected stale result. Do not reset or broadly invalidate completed components.

## Areas intentionally unchanged

Do not edit the implemented Framework Boundary Plan, framework inventory/configuration/update logic, Composer Manual content or embedding/selection path, retained-library policy, native framework-output safeguards, original-side comparison classpaths, format lifecycle rules, operation routing, intake/indexing/mapping, approval gates, or the progress-based timeout behavior.

Do not rewrite the shared demo framework to force it into a single production hierarchy. Use isolated regression fixtures for the inheritance variations instead.

No architecture topology change is expected for a helper inside component conversion. If implementation adds a major subsystem or new integration beyond this scope, reassess the plan before editing the architecture model.

## Completion criteria

- A concrete OP-step class with no local execution/business-hook declaration can reach conversion using source-backed inherited application behavior.
- A binary framework execution wrapper and inherited application business implementation remain distinct, with the existing manual/boundary policy intact.
- Relevant inherited source/checklist obligations reach generation, test validation, and reuse checks with verified provenance.
- Invalid bindings and genuine missing application evidence remain actionable failures.
- The existing saved run can resume without clearing progress or repeating intake/mapping.
- New regressions and the existing framework-boundary suite pass; any unrelated baseline failures are reported separately.

## Implementation results

- Added `step_entry_evidence.py` and integrated it only for configured-step boundaries in `requests.py`. It traverses existing graph roots/edges, selects verified implementing/supporting application evidence, and retains parser obligations without changing certainty metadata or inventing framework source.
- Added isolated inheritance, override, overload, provenance, request-authorization, test-based-mode, and cached-result tests. Added a two-framework-JAR regression with a binary execution wrapper and an application superclass hook. The existing manual is attached through the same encoding path, once.
- Original-versus-native step execution matched through the real framework JARs; deliberately wrong native behavior was reported as different.
- 58 focused regressions passed across the inheritance/framework suites and the existing source-authorization/evidence/prompt tests. Python syntax and Git whitespace checks passed.
- Existing local reuse checks rejected receipts missing inherited obligations and retained compatible receipts; saved artifacts and run state were not cleared. No runner or global policy-version change was necessary.
- No Java analyzer rebuild, new configuration, framework/manual redesign, shared demo rewrite, or architecture topology change is required. The migration guide describes resuming the same run with normal freshness checks.
