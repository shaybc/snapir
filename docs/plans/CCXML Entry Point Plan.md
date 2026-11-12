# CCXML Entry Point Plan

Status: implemented in the working tree. Changes are limited to entry recognition, boundary metadata, and original-side test invocation diagnostics.

## Goal

Recognize the real CCXML entry methods, including inherited declarations, record their exact signatures, and let comparison tests invoke them with the real framework JARs. The AI remains responsible for converting format behavior using the existing application evidence, configured format structure, and Composer Manual.

## Small implementation scope

1. Extend the existing format resolver to recognize these additional public instance signatures, alongside all currently supported field-format methods:
   - `DataElement unformatContext(String, Context)`
   - `KeyedCollection unformatKeyedCollection(String, KeyedCollection)`
   - `String formatContext(Context)`
   - `String format(Context)` and `String format(KeyedCollection)` remain supported.
   Resolve actual qualified parameter/return types and declaring classes through the existing hierarchy and configured classpath. Do not hardcode a CCXML class name, superclass chain, or inheritance depth. Do not choose arbitrarily between overloads.
2. Record the selected invocation and its declaring class, full signature, return type, and argument binding using existing boundary/lifecycle metadata wherever possible. Prefer the applicable externally called context entry when testing context-based invocation; permit the collection entry when the test explicitly supplies that argument. Do not replace the external call with a recursive implementation helper automatically.
3. Use the existing original-side reflection adapter to call the recorded method. Bind only the XML string and the existing original Context or KeyedCollection required by that invocation. Keep the real framework JARs on the original-side classpath. Report unsupported/missing argument bindings explicitly rather than constructing a Composer replacement runtime.
4. Preserve before-format/unformat behavior by invoking the correct original wrapper and retaining existing source-proven lifecycle handling. Do not synthesize a new hook sequence or call hooks again when the invoked wrapper already calls them. Existing child-field detection remains unchanged.
5. Add focused regressions for inherited context and collection entries, source-backed and JAR-backed methods, overload ambiguity, original invocation effects/hooks, and unchanged scalar formats. Check the generation-request handoff still receives the selected entry and existing evidence without changing conversion responsibilities. Reuse existing cache compatibility checks to refresh affected results only.

## Expected files to change:

- [FormatLifecycle.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/FormatLifecycle.java): extend existing method discovery/selection, without implementing format behavior.
- [LegacyFormatLifecycle.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/harness/LegacyFormatLifecycle.java): only the original argument binding needed for the resolved Context/KeyedCollection entry.
- [test_format_lifecycle.py](../../source/tests/test_format_lifecycle.py): test signature recognition, inheritance, ambiguity, existing field methods, and the request handoff.
- [test_format_comparison_execution.py](../../source/tests/test_format_comparison_execution.py): execute the selected original entries and verify hooks/effects through real fixture code/JARs.
- [running_migrations.md](../running_migrations.md): document the analyzer rebuild and normal saved-run resume.

Conditional handoff changes, only if regression tests demonstrate they are needed:

- [unit_verification_boundary.py](../../source/models/unit_verification_boundary.py): accept the additional resolved method names when reloading boundary records. This handoff change was required by the comparison regression.

- [boundary_execution.py](../../source/tools/behavior_verification/boundary_execution.py): pass the recorded entry/binding through the existing comparison protocol.
- [EntryMethod.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/EntryMethod.java): preserve actual selected signature metadata if the existing fallback handoff needs adjustment.
- [FrameworkBoundary.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/FrameworkBoundary.java): recognize the additional entry names in the existing binary-framework selection path without weakening ownership or ambiguity checks.

## Explicit exclusions

No converter implementation of XML parsing, serialization, recursive child traversal, collection semantics, decorators, business transformations, or Jackson generation recipes. No new Composer runtime, per-class behavior registry, JAR decompilation requirement, manual redesign, framework ownership changes, or replacement of existing scalar-format methods. No unrelated refactoring, global cache reset, or intake/mapping changes.

## Verification and resume

Run the focused lifecycle/comparison tests and existing framework-boundary regressions. Confirm the selected methods reach AI requests while conversion instructions and the manual path remain unchanged. Rebuild the Java analyzer/harness because its code changes, then resume the same run with its existing configuration and saved progress. Existing compatibility checks may revalidate or regenerate affected format results; do not invalidate unrelated completed work. Entry recognition alone does not guarantee AI conversion success or resolve the separate fixture/budget failures.

## Implementation results

- Extended `FormatLifecycle.java` to recognize inherited context/collection signatures without replacing existing basic scalar-field selection. Metadata retains the actual declaring class, qualified signature, parameters, and return type. Ambiguous candidates remain errors.
- Updated the existing binary-framework selection path to use the same context-wrapper preference, keeping framework ownership checks and scalar-field behavior intact.
- Extended only the boundary model's allowed method-name values. The existing reflection adapter already invokes the selected methods with existing Context/object recipes; no new argument-construction or format-processing engine was needed. Its missing-input diagnostic now names the required input and retains the lookup failure.
- Verified the selected lifecycle reaches generation requests. Context wrappers run their original hooks once and preserve observed request-saving side effects. Direct collection entries use explicit original object inputs; no extra hooks are synthesized.
- 54 focused regressions passed across lifecycle, comparison, and existing framework-boundary suites. These include source-backed and actual JAR-backed invocation, invalid/ambiguous entries, legacy scalar and configured-collection comparisons, missing bindings, and unchanged framework/manual safeguards. Syntax and Git whitespace checks passed.
- No changes were needed to `EntryMethod.java`, the Python invocation protocol, conversion instructions, Composer Manual integration, framework ownership/configuration, or saved-run identities. No converter XML parsing, child traversal, serialization, or business logic was added. Rebuild the Java analyzer/harness with JDK 25 and resume the existing run normally.
