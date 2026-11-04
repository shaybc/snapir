"""Role-specific full-pipeline instructions with no combined implementation/test duties."""
from agents.behavior_conversion.staged_instructions import IMPLEMENTATION,TESTS,DEPENDENCIES

CODE=IMPLEMENTATION+'''
This task_kind determines the selected conversion boundary. For basic components implement all supplied
source_entry_points; for configured formats/steps specialize their XML and direction; for service
assembly compose accepted typed APIs and preserve routing, initialization and side effects.
Supporting/framework/decorator sources are evidence, not extra conversion targets. Preserve the
assigned packages, accepted DTOs/APIs and dependency injection/resource requirements. Complete source
evidence is authoritative; behavior_requirements describe required behavior, not coverage metadata.
If planned_structure is supplied, implement its exact DTOs/interfaces as production code.
No checklist citations, API metadata, bindings or tests in this response.
'''
METADATA='''Return only the metadata schema for the supplied frozen, compiled production Java.
Do not generate/edit code or tests or propose Maven dependencies. parsed_apis are authoritative.
Assign exported native APIs to their owning component/unit; do not invent signatures or planned methods.
Include required inherited public entry methods listed in parsed_apis. Their declaring_type identifies
the native parent implementation; do not claim ownership of that parent or invent inherited constructors.
Copy expected_contract_fields, evidence identities and dependencies exactly where supplied.
Keep accepted interfaces unchanged. Resolve verification bindings from actual methods and runtime controls.
Map required parser checklist IDs to real production excerpts; citations are traceability, not behavior proof.
Preserve all existing configured-format/step and operation routing, resource and dependency obligations.
For services, operation_contract.units must exactly reuse accepted unit contracts.
Return unresolved_questions rather than inventing business behavior. No files or source definitions.
For whole configured formats use checklist_answers and leave checklist_implementations empty. Bind
unit_id/source_manifest_hash/configuration_hash to verification_boundary. Subtrees and basic components
use checklist_implementations. Cite minimal exact excerpts, not whole files for each item.
Format-subtree contracts need runtime_inputs.parent_environment describing actual typed parent inputs.
Service step_dependencies/runtime_resources must describe actual constructor parameters and fields,
copying source binding/connection identities; never alter accepted unit contracts or injection roles.
'''
STRUCTURE='''Describe only the typed operation data/interface structure in the metadata schema.
Use the original XML and implementing evidence to define fields/types, units, dependencies and service
API. Reuse accepted native types when provided. Return no Java source or tests. A separate code stage
will implement these declarations, then the application parses, compiles and validates them.
'''
TESTS_ONLY=TESTS+'''
task_kind determines test scope: basic components cover supplied entry points; configured units cover
the selected direction; route scenarios cover only the supplied scenario and expected_test_path.
Use frozen code and parsed APIs. Retained tests are the repair starting point; keep evidenced assertions
and passing cases. API incompatibility is not permission to remove behavior tests. Source-derived
production contradictions remain unresolved or implementation failures, not weakened assertions.
'''


def code_instruction(payload):
    """Carry task-specific implementation obligations without mixed response duties."""
    prompt=CODE
    if payload.get('executable_verification',{}).get('mode')=='conversion_checklist_v1':
        prompt+='\nConversion readiness uses source checklist traceability, compilation and JUnit. Expose typed production APIs and settings normally; no legacy execution, comparison adapters or harness invocation recipes are required. Behavioral equivalence is not assessed.'
    if payload.get('kind')=='step_implementation':
        from agents.behavior_conversion.step_component import step_instruction
        prompt+=step_instruction('step_implementation')
    if payload.get('kind')=='configured_step':
        prompt+='\nSpecialize only this occurrence from configured_unit. Expose its original int execute outcome; routing belongs to the caller. Reuse its validated implementation API and collaborators.'
    if payload.get('kind')=='format_implementation':
        from agents.behavior_conversion.format_component import FORMAT_IMPLEMENTATION_INSTRUCTION
        prompt+=FORMAT_IMPLEMENTATION_INSTRUCTION
    if payload.get('format_partition'):
        prompt+='\nConvert only format_partition.tree. Preserve typed parent environment, namespace/prefix ownership, decorator and evaluation order. Call frozen child APIs at their original positions; do not precompute/reorder effects.'
    if payload.get('kind')=='format_composition':
        prompt+='\nCompose only configured_format and its selected direction. Preserve reference/child order, collection and decorator semantics and parent runtime inputs. Invoke frozen native prerequisites rather than copying their implementations.'
    if payload.get('assembly_phase')=='implementation_compile' or payload.get('kind')=='service':
        prompt+='''
Receive EVERY required_step_dependencies role as a public constructor argument, store each in its
own field and call that supplied object. No new step instances, hidden factories, service locators
or no-argument fallback. Receive each required_runtime_resources provider through the constructor.
The current constructor contract checks EVERY public constructor on the exported service class:
each must directly assign every supplied step to its own declared field and call those fields.
Use a single explicit constructor when possible. Do not use this(...) or super(...) forwarding
constructors, inherited step fields, or a compatibility facade as the exported service entry.
Preserve source-resolved connection ownership, transaction scope, release and early-return behavior;
never invent commits, credentials or pooling. Reuse accepted API return types exactly, without
assuming a wire-to-business conversion when an accepted method already returns business data.
Preserve routing, timeout priority, initialization, channel filtering, error-body switches and final
steps. No HTTP controller or test-specific switches. Do not return accepted units' source files.
'''
    if payload.get('side_road_origin',{}).get('stage')=='baseline':
        prompt+='\nTemporary internal original-like helper structure is allowed for this baseline; public APIs stay typed and IBM-free. Simplification and all validation still follow.'
    if payload.get('side_road_origin',{}).get('stage')=='simplify':
        prompt+='\nSimplify verified_baseline without changing its public APIs, verification binding or observed behavior. Remove framework plumbing.'
    if payload.get('format_chain_policy'):
        from runtime.component_conversion.format_chains import INSTRUCTION
        prompt+='\n'+INSTRUCTION
    return prompt
