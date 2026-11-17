# Format Entry Ownership Plan

Status: planned; implementation is not included in this document.

Each format must use an entry method callable on its own implementation class, either declared there or inherited. A containing format such as CCXML must never supply CCString's boundary merely because it calls CCString.

## Implementation

1. **Enforce entry ownership in deterministic analysis.** Retain the accepted field-format and CCXML signatures and existing override resolution. Verify that a selected declaration belongs to the target class or its ancestors. A resolved parent-to-child call can provide evidence of the child's invoked signature, but must resolve against the child's type and accepted direction/signature rules. Do not require a containing caller to exist. Record the target class separately from the declaring class and full signature. Preserve lifecycle hooks and existing ordering evidence.
2. **Remove the containing-format fallback.** When building a basic format request, require that format's own analyzed boundary. If it is missing, report an explicit entry-resolution failure naming the target, direction, and missing or conflicting evidence; never copy the configured parent's lifecycle. Apply the same ownership rule to decorator members and every format-chain boundary consumer, without borrowing another group member's framework evidence.
3. **Preserve framework behavior.** An inherited method resolved from a configured framework JAR remains a non-blocking framework boundary. Continue supplying application evidence and the Composer Manual to the AI. Do not require proprietary source, convert framework classes, or implement parsing in the converter. Original-side comparison tests retain the real JAR classpath.
4. **Make resume and reuse safe.** Advance the format-specific policy used by local input revisions and shared implementation identity; include it in request and validation receipts and check it before reuse. Reject old or mismatched format receipts, including accepted staged snapshots and shared-store candidates, even if build/tests previously passed. Refresh affected format analysis and regenerate/revalidate affected format results and dependent receipts. Preserve historical attempts for diagnostics. Resume the existing run without repeating intake, capture, mapping, or unrelated component conversion. Avoid a global component-policy bump that invalidates unrelated OP steps.
5. **Verify the handoffs.** Cover request construction, generation, validation, local resume, staged-result reuse, and cross-run reuse. Test CCString under multiple parent formats; declared and inherited methods; CCXML's own context/collection methods; missing basic evidence; mismatched owner rejection; decorator handling; and JAR-only inherited methods. Prove that old-policy results are rejected and corrected results are reusable. Rebuild the analyzer and run focused Python/Java checks.

## Expected files to change:

- [EntryMethod.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/EntryMethod.java) and [FormatLifecycle.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/FormatLifecycle.java): enforce target/declaring-class ownership while preserving signature selection and framework resolution.
- [requests.py](../../source/runtime/component_conversion/requests.py) and [format_chains.py](../../source/runtime/component_conversion/format_chains.py): require correctly owned evidence at request and chain handoffs.
- [component_identity.py](../../source/tools/conversion_tools/component_identity.py) and [shared_identity.py](../../source/runtime/component_conversion/shared_identity.py): version affected local and shared format results.
- [runner.py](../../source/runtime/component_conversion/runner.py) and [validation.py](../../source/runtime/component_conversion/validation.py): persist and enforce the format policy on reuse and validation receipts.
- [test_format_lifecycle.py](../../source/tests/test_format_lifecycle.py) and [test_cross_run_component_reuse.py](../../source/tests/test_cross_run_component_reuse.py): add focused ownership and stale-result regression cases, including staged/local resume coverage in the applicable existing test modules.

## Scope limits

No changes to Composer behavior, AI-owned conversion logic, framework boundary policy, operation-step detection, model response handling, or intake/mapping identities. Any additional production file found necessary must be identified before editing it.
