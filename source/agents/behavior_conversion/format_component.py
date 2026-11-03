"""Source-driven composition instructions; no per-tag business rules or framework recreation."""
from agents.behavior_conversion.native_instructions import native_instructions
from runtime.behavior_conversion.compiler_feedback import CORRECTION_INSTRUCTION
from runtime.behavior_conversion.test_feedback import TEST_CORRECTION_INSTRUCTION


def format_instruction(known=()):
    """Compose one actual configured format from frozen native implementations."""
    from runtime.component_conversion.format_chains import INSTRUCTION
    return native_instructions('format', known, include_example=False) + CORRECTION_INSTRUCTION + TEST_CORRECTION_INSTRUCTION + INSTRUCTION + '''
Return NativeFormatComponentBundle, not unit_contract. Request sources/XML are input evidence.
coverage_response_example is a metadata template, not source code or a completed test.
Use every exact requirements key as a coverage key; never substitute business.
Replace example paths with actual returned src/test/java/ files exercising those requirements.
One test file may cover multiple IDs; the template itself is not evidence of executable coverage.
Generate only configured_format. Declare its component contract with specialized configuration,
the assigned native_package, supplied source_entry_points, configuration evidence and exact dependencies.
Copy the supplied expected_contract_fields into the corresponding contract, then add its native APIs.
All evidence_ids must come from allowed_evidence_ids. Component/group/checklist IDs are different record identities.
Use the validated prerequisite implementations and their actual APIs. Do not copy their business
logic, fabricate imports, or implement a generic Composer XML interpreter or compatibility engine.
Preserve the supplied parent structure, child/reference order, field attributes/defaults,
collection semantics and decorator sequence. Preserve parent-derived runtime inputs, namespaces,
literal prefixes, missing/empty/null distinctions, exceptions and side-effect ordering from source.
Use explicit typed data/configuration and ordinary Jackson wire models/plain mapper methods.
Implement only the selected format/unformat direction; shared helpers remain real dependencies.
For this whole format use checklist_answers, leaving checklist_implementations empty. Answer every
whole-unit parser ID exactly once with exact current main-source citations, including prerequisite
files. Supported exclusions require the existing proof/authorization rules, never an AI assertion.
Bind unit_id/source_manifest_hash/configuration_hash to verification_boundary. Declare
verification_binding for an actual public method in this component's APIs. Input XML is an
unchanged String; other inputs are supported scalars or native DTO constructor/setter recipes.
Request unformat methods expose their actual context writes through getters on result/argument
objects and output=none. Response format methods return XML. Preserve write presence on exceptions.
Expose source-defined runtime settings through actual native settings_bindings. No Java harness
adapter code or expected-response recipes. The trusted harness compares both implementations
on identical generated inputs/settings before this component may be saved.
Passing component comparison is observed evidence, not final unit/operation acceptance.
'''


FORMAT_IMPLEMENTATION_INSTRUCTION = '''
Translate this format-wrapper implementation as a parameterized native helper, without recreating
a runtime that loads Composer tags or dynamically interprets configuration. The configured format
composition owns concrete structure/fields; provide the evidenced reusable behavior through explicit
native arguments/collaborators. Keep source initialization, inherited behavior and runtime conditions.
'''
