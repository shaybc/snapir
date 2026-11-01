"""Separate whole-unit translation from architectural simplification instructions."""

from runtime.behavior_conversion.native_reflection_policy import INSTRUCTION as NO_REFLECTION

BASELINE = NO_REFLECTION + '''Whole-unit IBM-free baseline translation, not architectural simplification.
Convert only the complete selected unit and its required supporting behavior from the supplied
XML and implementing sources. All original Java is evidence, never a permitted runtime library.
Return a NativeUnitBundle with complete native main/test sources, dependencies, source evidence,
unit_contract and verification_binding. No IBM imports, references or runtime dependencies in
implementation or tests. Implement required supporting behavior rather than retaining IBM calls.
Temporary internal structure resembling the original is allowed at this stage. Keep the public
boundary typed; internal support objects do not have to be flattened yet. Preserve runtime settings,
Declare the caller-facing boundary and DTO APIs; do not export temporary internal helper APIs.
defaults, branches, side effects, exception behavior and outputs. Do not freeze sample values.
Preserve supplied accepted native APIs unchanged. Supply focused executable JUnit tests and exact
required coverage IDs. No TODOs, replacement stubs or invented behavior. Follow the supplied schema,
testing contract and known dependency pins. This candidate is isolated and is not final acceptance.
'''

SIMPLIFY = NO_REFLECTION + '''Simplify the verified IBM-free baseline into ordinary native Java business code.
Use verified_baseline as the working implementation, and original XML/source as behavior evidence.
Preserve its declared public API, binding and accepted dependency APIs. Remove framework-style
Context/holder/initialization plumbing; use typed objects and plain transformations instead of a
generic Composer interpreter. Keep supporting business behavior, runtime configuration, defaults,
exceptions, side effects and output structure/prefixes. Do not change behavior to simplify code.
Return a complete NativeUnitBundle, including tests, exact requirement coverage and matching API
metadata/binding. No IBM references or dependencies in implementation or tests. Compile, tests and
original/native comparisons will run again. Failed simplification does not replace the baseline.
'''
