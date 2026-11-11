# Framework Boundary Plan

Status: implemented in the working tree; see the migration guide for configuration and saved-run updates.

## Objective

Honor the original Composer conversion design: translate application business behavior into native Java, not the Composer framework, inheritance structure, runtime, or architecture. Proprietary framework source is often unavailable. Its absence must not prevent the model from attempting conversion using the application code already captured and the existing Composer explanations.

The explicit configuration of framework JARs establishes ownership boundaries. It does not establish behavioral equivalence or exempt generated code from the selected validation policy.

## Agreed methodology

1. Application code already selected for conversion remains the model's implementation input.
2. Existing Composer Manual explanations supply framework semantics. Reuse the existing embedded manual content and its established selection path; do not introduce class-specific wrapper contracts, a method-contract registry, new handwritten behavior descriptions, or mandatory JAD evidence.
3. Scan explicitly configured framework JARs locally to inventory their classes and packages. Missing source for a class proven to belong to that inventory is an expected framework boundary, not a missing-application-source failure.
4. Do not convert, copy, decompile, or recreate those framework classes. Generate equivalent business behavior with native Java APIs and appropriate libraries.
5. Ordinary third-party libraries retain their existing approved dependency treatment. Do not classify all IBM namespaces or all classpath JARs as Composer.
6. During original-versus-native comparison, execute the original application with its real framework JARs on the original-side classpath. The framework is available and runs normally there. Generated native code does not acquire a Composer runtime dependency.
7. New boundary configuration supplements the current run. It must not require fresh indexing, capture, Composer mapping, or loss of completed conversion work.

## Current implementation findings

- `PipelineConfiguration` supports `classpath_jars` but has no explicit framework-ownership JAR list. It rejects unknown configuration fields.
- `resume_pipeline` loads the saved run profile, so changing an unrelated start profile alone will not update an existing run.
- `EntryMethod.write` resolves inherited methods through the classpath, then requires a source AST. This makes a framework method available in bytecode fail solely because its source body is unavailable.
- Component request building rejects unresolved basic-format lifecycle reports and requires parser-backed entry points/checklists. Removing the Java exception alone would leave downstream blockers.
- Configured format chains also require source-derived hook and decorator-order evidence. They need the same boundary semantics, without weakening source-backed application checks.
- Existing dependency treatment already separates retained libraries from documented Composer replacement behavior. Extend that separation rather than replacing it.
- Composer generation guidance uses an embedded manual snapshot. Runtime does not simply reread the whole configured manual file. Preserve this existing knowledge path and its traceability.
- Scoped checkpoint validation includes conversion policy and classpath fingerprints; stale handling can currently require fresh intake. A boundary-only update needs its own compatible resume path.
- Component reuse compares parser obligations, entry points, analysis-tool identity, classpath identity, requirements, and generation policy. Compatibility must be evaluated explicitly instead of globally clearing results.

## Configuration and local inventory

Add one additive configuration field, empty by default:

```yaml
framework_jars:
  - 'C:/Workspace/composer/lib/composer-runtime.jar'
  - 'C:/Workspace/composer/lib/composer-formats.jar'
```

These are illustrative paths. The user supplies the actual original framework archives. Multiple JARs are supported. Relative paths follow a documented configuration-file base; persisted configuration uses resolved paths.

Use a small dedicated inventory module to:

- Validate each path and archive; compute a content hash.
- Read class-entry names without loading or executing classes, extracting Java source, or sending archive contents to the model.
- Record exact class membership, derived packages, archive identities, and inventory version. Handle nested classes and multi-release entries consistently.
- Deduplicate identical archives and report conflicting class ownership or classpath shadowing. Use the same effective project/classpath resolution as the analyzer when selecting the actual owner.
- Cache inventory by archive content hash. Reuse existing verified class inventories where suitable.

Exact class membership establishes the boundary. Package lists are descriptive and useful for lookup, but must not classify an application class merely because it shares an IBM package prefix.

A framework JAR can contain application-specific extensions as well as runtime code. Explicitly selected application source remains convertible; JAR membership must not silently suppress that source. Resolve genuinely ambiguous source/binary ownership explicitly.

Framework inventory is classification metadata. Keep it separate from ordinary dependency approval and from application source indexes. An unreadable configured archive is a configuration error, not a reason to pretend an unknown class is framework-owned.

## Boundary handling through the pipeline

### Preparation and dependency planning

Apply framework ownership to saved, selected application evidence without rerunning the mapper. Preserve source hashes, configuration occurrences, selected operations, and application component identities.

A missing class or method body may be treated as framework-owned only when the resolved declaring class is present in the configured framework inventory. For an inherited method, use the analyzer's resolved declaring type where available. No per-method behavior registry is required. If method resolution itself fails, distinguish that from the expected absence of framework source.

Record framework dependencies as contextual/original-runtime dependencies, not generated prerequisites. They must not create component-generation tasks or unsatisfiable native-contract prerequisites.

Missing application source remains a real issue. Unconfigured unknown binaries retain existing treatment. Source-backed application overrides remain application behavior even when they override a framework method.

### Boundary analysis

Preserve a source-backed analysis result when available. At a proven framework boundary, record a non-blocking classification with the available owner/signature, archive identity, and source-unavailable reason. Do not manufacture a source AST, source-line evidence, parser checklist, or executable body.

Distinguish analysis states explicitly: application source analyzed; framework boundary encountered; actual application resolution failure. A framework boundary must not be counted as a failed application lifecycle solely because its AST is absent.

Continue collecting detected application code and relevant configuration. Do not recursively expand into framework implementations. Apply the same rule to preparation boundary reports, basic component generation, configured formats/decorators, operation steps, and unit verification where their semantics require it.

### Model requests and generation

Provide:

- The application code already detected for the selected conversion unit.
- Its effective XML/configuration and existing required native prerequisite APIs.
- Existing Composer explanations through the current manual-context path.
- Compact boundary metadata identifying relevant unavailable framework dependencies and stating that they are not conversion targets.

Do not attach entire JAR inventories, decompiled IBM packages, new wrapper implementations, or class-specific behavior recipes. Boundary metadata identifies ownership; it does not invent behavior.

The model should attempt native business conversion despite missing framework source. Preserve documented initialization, values, errors, effects, and configuration behavior without reproducing Context, Composer base classes, or a generic Composer interpreter.

Keep existing request budgeting. Framework traversal must stop at the boundary rather than increase request size. Do not reduce application evidence silently or claim that this change resolves unrelated oversized application requests.

### Checklists, generation eligibility, and acceptance

Do not require parser obligations for absent framework implementations. Retain obligations for supplied application code and retain requirements derived from configuration and existing documented behavior.

Allow a framework-owned entry boundary to reach generation without satisfying a source-only eligibility requirement. Do not treat non-blocking analysis classification as successful conversion or accepted equivalence.

If generation or testing exposes genuinely unresolved behavior, report that specific limitation. Do not reinstate a generic requirement to supply proprietary source or require the user to author a method contract first.

Preserve the selected verification mode. Build/JUnit readiness must not become a claim of paired equivalence; paired-comparison modes must still perform their required comparisons.

## Comparison execution: original framework stays available

Original-side comparison must execute the real original application against the configured framework binaries. Framework-source absence is not a reason to omit the original invocation.

- Resolve configured framework JARs into the original analysis/execution classpath without widening unrelated project visibility or changing classpath precedence silently.
- Reuse existing archive verification, dependency resolution, harness isolation, and fixture mechanisms.
- Initialize original framework objects using supported original-side setup and configuration; retain public API/bytecode metadata needed to invoke them without needing method bodies.
- Where the current harness requires source-derived entry/lifecycle metadata, allow framework-boundary metadata plus existing documented setup to reach the original binary invocation. Do not fabricate source receipts.
- Do not copy original IBM classes, add substitutes that shadow them, or attach Composer JARs to the generated native application's production dependencies.
- Compare original and native output, state, exceptions, and relevant effects under the existing policy. Missing setup capability or an actual binary/runtime error remains a specific test failure, distinct from missing source.

Check both standalone components and configured complete-unit comparisons. Preserve intentional differences between their setup and observation requirements.

## Updating an existing run without fresh intake

### Supported update interface

Add a narrow resume option such as:

```text
resume --run-id <existing-run> --framework-config <framework-only.yaml>
```

This interface is implemented by the CLI. The framework-only file accepts only `framework_jars`; it must not silently change source roots, selected operations, mapper settings, target language, or verification policy. An explicit empty list removes the classification configuration through the same audited process; omission leaves it unchanged.

Provide the equivalent interactive resume input if the CLI's established workflow requires it. Default resume remains unchanged when no update is supplied.

### Update sequence

1. Load and validate the existing saved profile and run state.
2. Read the framework-only update, resolve paths relative to that file, and scan/cache the supplied archives.
3. Validate compatibility with the existing original classpath. Report archive replacements, conflicts, or newly added binary availability separately from ownership annotation of an already-present JAR.
4. Persist the effective framework configuration and a revision/audit record atomically through existing state/report facilities. Retain the previous revision and reason for the update.
5. Load existing map, intake, source evidence, prepared units, and progress. Existing integrity checks may verify saved source/JAR identities; verification is not re-indexing or mapping.
6. Reclassify affected dependency edges from the saved application evidence. Rebuild only conversion-derived boundary decisions, affected planning edges, request eligibility, and affected reports. Do not reread the whole workspace through the mapper.
7. Resume conversion for failed, blocked, or affected units. Preserve unaffected completed work and validated native artifacts.
8. Regenerate diagnostics from the updated attempt.

### Checkpoint and receipt compatibility

Keep intake/map identity independent of the additive framework-boundary revision. Do not bump a global intake policy version merely to force existing runs through fresh capture.

For the existing run, establish a narrow compatibility transition after checking that imported source evidence, selected operations, configuration, and map identity still match. Do not bypass genuine source or mapping changes.

An unchanged archive newly labelled as framework is an ownership-policy addition, not a changed original binary. Adding/replacing a binary can affect behavior and requires the existing relevant classpath checks, but still does not inherently require source remapping.

Version affected generation requests and boundary results using the applicable boundary inventory/policy revision. Avoid including the entire unrelated framework inventory in every component fingerprint.

Existing successful artifacts remain stored. Reuse unaffected receipts under their original meaning. For affected artifacts, run necessary compatibility checks or revalidation and regenerate only when behavior/obligations actually changed. Do not delete progress, clear attempt history, or mark previous build/test receipts as comparison acceptance.

The current analyzer-tool hash check is broad. Audit that path so a diagnostic/boundary-policy change can revalidate compatible existing results instead of unconditionally regenerating all components. Do not ignore hashes globally or silently rewrite receipts.

If required application evidence is missing from the saved run, report the exact missing artifact. Do not make a fresh run the default response to an additive framework configuration.

## Diagnostics

Show a framework boundary as expected, non-blocking context, including class, resolved declaring method when available, and supplying archive. Explicitly state that native generation uses application source and existing Composer explanations.

Report application-source failures, configuration errors, generation failures, and original-side comparison failures separately. Preserve existing logs, redaction, source-integrity checks, and historical attempt evidence.

## Expected files to change:

Paths below are relative to this plan. New paths are proposed; detailed implementation may adjust them only within this scope.

- [Pipeline configuration](../../source/models/pipeline_configuration.py): add the framework JAR list with backward-compatible defaults.
- [Framework inventory model — new](../../source/models/framework_boundary_inventory.py): typed archive/class ownership and revision metadata.
- [Framework boundary package — new](../../source/tools/framework_boundaries/): focused inventory scanning, classification, and run-update compatibility modules.
- [CLI entry](../../source/cli/main.py) and [interactive selection](../../source/cli/interactive.py): supported framework-only update when resuming an existing run.
- [Checkpoint resume](../../source/runtime/checkpoints.py): apply the validated update before saved preparation/checkpoint decisions.
- [Dependency treatment](../../source/tools/conversion_tools/dependency_treatment.py) and [Composer recognition](../../source/tools/conversion_tools/composer_runtime_contracts.py): authoritative explicit JAR ownership without a new wrapper-contract registry.
- [Component planning](../../source/tools/conversion_tools/component_graph.py): prevent framework-only dependencies becoming native generation prerequisites.
- [Scoped preparation](../../source/tools/conversion_tools/scoped_workflow/preparation.py) and [runtime preparation](../../source/runtime/scoped_conversion.py): refresh derived boundary treatment using existing imported evidence.
- [Checkpoint validation](../../source/tools/conversion_tools/scoped_reuse/checkpoint.py), [fingerprints](../../source/tools/conversion_tools/scoped_reuse/fingerprints.py), and [prepared reuse](../../source/tools/conversion_tools/scoped_reuse/artifacts.py): additive configuration compatibility without fresh intake.
- [Boundary reports](../../source/tools/behavior_verification/boundaries.py), [boundary model](../../source/models/unit_verification_boundary.py), and [basic lifecycle preparation](../../source/tools/behavior_verification/format_lifecycle.py): propagate non-blocking framework boundary state.
- [Java entry analysis](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/EntryMethod.java) and [lifecycle analysis](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/FormatLifecycle.java): preserve resolved binary metadata without requiring framework source bodies.
- [Component requests](../../source/runtime/component_conversion/requests.py), [format chains](../../source/runtime/component_conversion/format_chains.py), and [component runner](../../source/runtime/component_conversion/runner.py): generation eligibility, source-only obligations, configured composition, and compatible result reuse.
- [Component generation guidance](../../source/agents/behavior_conversion/component_generation.py): explain the boundary using the existing manual context; prohibit framework recreation.
- [Comparison runner](../../source/runtime/format_comparison/runner.py), [original harness lifecycle](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/LegacyFormatLifecycle.java), and [boundary execution](../../source/tools/behavior_verification/boundary_execution.py): preserve original framework execution through real JARs without requiring implementation ASTs.
- [Diagnostics](../../source/tools/run_diagnostics/): expose non-blocking classification and saved-run update effects.
- [Migration guide](../running_migrations.md): configuration, current-run update, and comparison classpath instructions.
- [Regression tests](../../source/tests/): inventory, missing-source generation, unchanged-run upgrade, reuse, and comparison execution.
- [Architecture model](../../.aice/model.yaml) and affected flows/narration: describe new boundary inventory and resume-update responsibilities when implementation adds them; read the architecture skill first and validate the model.

## Implementation sequence

1. Add multi-JAR configuration and exact local inventory, with empty-list compatibility.
2. Carry framework classification through preparation and planning using existing application evidence.
3. Remove source-only generation blockers at proven framework boundaries across all applicable paths; preserve existing manual context.
4. Verify original-side execution with real framework binaries and isolated native output.
5. Implement the audited framework-only saved-run update and narrow checkpoint/receipt compatibility transition.
6. Finish diagnostics, documentation, architecture updates, and focused end-to-end regression checks.

Do not deploy a partial implementation where the analyzer stops throwing but component requests, decorator chains, checklists, or comparison setup still reject the same absent framework source.

## Acceptance tests

- Two or more configured framework JARs produce a stable exact class inventory without source extraction or framework execution.
- A captured application formatter inheriting a binary-only framework method can reach generation with application source, configuration, and existing manual explanations.
- No JAD content, entire JAR class list, or framework implementation is added to the model request.
- Missing application source still fails appropriately; a source-backed override is not hidden by framework membership.
- Framework dependencies do not become generated component prerequisites or native Composer dependencies.
- Formats, decorators, operation steps, and complete configured-unit paths consistently honor the boundary where applicable.
- Comparison actually runs original code against the real framework JAR and detects a deliberately incorrect native result.
- The native side cannot accidentally load original framework code or shadow original classes with generated substitutes.
- Updating the existing blocked run invokes no mapper, fresh capture, or application re-indexing; tests fail if those actions are attempted.
- Existing imported evidence, selected operations, application identities, and unaffected completed artifacts/receipts remain intact. Affected artifacts are revalidated or regenerated selectively.
- Repeated resume with unchanged configuration is stable; archive changes and genuine source changes remain detectable.
- Old runs without the setting load normally. Bad JAR paths, conflicts, and incompatible updates produce specific actionable messages.

## Scope exclusions

No new method-contract registry, decompiler integration, external framework source ingestion, mandatory user-written behavioral evidence, blanket exemption for IBM packages, weakening of comparison requirements, or unrelated fixes for model validation and oversized application requests.

Only this plan document is changed by the planning task. Implementation must begin with its own minimal-scoped file plan after authorization.
