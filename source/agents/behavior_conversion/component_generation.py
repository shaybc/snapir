"""Source-driven instructions for basic native components below configured verification units."""
from agents.behavior_conversion.native_instructions import native_instructions
from runtime.behavior_conversion.compiler_feedback import CORRECTION_INSTRUCTION
from runtime.behavior_conversion.test_feedback import TEST_CORRECTION_INSTRUCTION


def component_instruction(known=()):
    """Reuse shared native rules without importing configured-step or formatter policies."""
    return native_instructions('step', known, include_example=False) + CORRECTION_INSTRUCTION + TEST_CORRECTION_INSTRUCTION + '''
Convert only the supplied basic implementation group, using the NativeComponentBundle schema.
Only format and operation-step implementations are separate generation targets.
Sources marked supporting_source_only supply dependent behavior, not additional component contracts.
Incorporate required utility/decorator behavior into this native implementation or native companions;
use typed inputs/results for framework state instead of recreating Context or a Composer runtime.
Do not return unit_contract. Request sources/XML are input evidence, not response examples.
coverage_response_example is a metadata template, not source code or a completed test.
Use every exact requirements key as a coverage key, including entry- IDs; never substitute business.
Replace each example test path with an actual returned src/test/java/ file that exercises that requirement.
One real test file may cover multiple requirement IDs. Do not claim coverage without writing the tests.
Implement the original source behavior, initialization, exceptions and runtime-dependent inputs.
Do not infer rules from class/tag names. Do not hardcode channel, application, date, null or XML rules.
Preserve significant wire names, prefixes, ordering and distinctions from the source.
Use the assigned native_package. Return one contract for every component ID in the group.
Each contract cites its original definition ID, exact dependencies and supplied source_entry_points.
Copy the supplied expected_contract_fields for each contract, then add its native APIs and other schema fields.
Keep its evidence_ids; add supporting source IDs only from allowed_evidence_ids. For every evidence_ids array choose only
allowed_evidence_ids; component IDs, group IDs and parser-checklist IDs identify different records.
API type_name and Java packages use the assigned native_package, including when original source uses IBM packages.
Declare explicit typed configuration and runtime inputs, and state initialization, effects and exceptions.
Implement both directions when supplied entry points include format and unformat; identify tested
entry points through the supplied requirements. Include complete relevant shared behavior.
Reuse direct prerequisite APIs exactly. Do not regenerate them or alter their files/interfaces.
Retained external policies are not generated implementations. Do not invent missing prerequisites.
The original complete source is authoritative; parser_checklist contains syntactic obligations,
not AI facts. Cite and test source behavior rather than relying on samples as proof of equivalence.
Map every parser_checklist ID exactly once in checklist_implementations to nonempty exact excerpts
in returned or direct-prerequisite main Java files. These citations are traceability, not equivalence.
Return executable focused JUnit tests with coverage for every supplied behavior requirement.
Passing component compilation/tests permits reuse only; final configured-unit comparison is required.
'''

