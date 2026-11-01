"""Select three configured bank units and request native boundaries without AI checklist citations."""
from copy import deepcopy
from agents.behavior_conversion.native_instructions import COMMON_INSTRUCTION
from runtime.behavior_conversion.testing_contract import attach_testing_contract

SELECTION = [('request_unformat', 'GetClientLinksRQFmt'), ('response_format', 'StandardErrorRSFmt'),
             ('configured_step', 'NoLinksFound')]
OPERATION = 'INTERNET/GetClientLinksOp'

INSTRUCTION = 'Isolated thin-path native generation.\n' + COMMON_INSTRUCTION + '''
This is an isolated thin-path experiment, not a production acceptance task.
Convert only selected_unit, including its configured XML and required implementing/dependent source behavior.
Sources are read-only evidence, not a list of classes to recreate. Do not translate framework inheritance.
For a request, parse the original XML String and expose actual context writes via typed result/argument getters.
For a response, take typed field/runtime inputs and return the XML String. Preserve significant prefixes.
For a step, expose the integer outcome and actual writes through a typed result, not a Context/map runtime.
Initialization comes from this unit's XML. Do not compile other steps or other format definitions into it.
Keep source-defined runtime configuration and all applicable decorator behavior. Do not hardcode sample settings.
Use plain Java/Jackson transformations, native DTOs and ordinary JDK libraries. No Composer interpreter,
Tag/Context classes, holder chains, XML initialization runtime or subclasses of original framework types.
Return NativeUnitBundle: files, dependencies, coverage, evidence_ids, unit_contract and verification_binding.
The unit_contract must identify selected_unit.unit_id and declare the actual public entry API.
verification_binding describes that API using scalar context inputs, unchanged XML, or native DTO construction.
context_writes must expose actual values AND presence via presence_getters when a write is conditional.
Use a mutable native output argument if the original can write fields before throwing; a return value
is unavailable when a method throws. Preserve original exception types and actual partial writes.
Request units use output=none; response units return XML; step output is the original integer outcome
(output_getters may project it from a result). Bind all supplied runtime_controls through settings_bindings.
Do not return executable harness adapters, expected observations or parser checklist answers/citations.
The parser checklist is used by the application for inputs and diagnostic coverage, not AI-written metadata.
Write focused executable JUnit tests derived from the original sources and configuration.
coverage_example is only a metadata template: replace its path with actual returned tests, keeping exact IDs.
All response Java sources must have a public top-level type matching their file/package.
Example native shape ONLY: public void unformat(String xml, RequestState state);
RequestState has getClientId()/hasClientId(). Bind it as a native object argument and project its real values.
The getter returns the real parsed value, and hasClientId records whether the original wrote it, even on failure.
This shape illustrates typed access, not domain behavior or an expected response. Derive your actual API from evidence.
'''


def select_units(preparation):
    """Select one real request, response and non-dispatch step; never expand to the full operation."""
    operation = preparation['operations'].get(OPERATION)
    if operation is None or operation['status'] != 'prepared':
        raise ValueError('Thin path requires prepared INTERNET/GetClientLinksOp')
    result = []
    for kind, name in SELECTION:
        found = [unit for unit in operation['units'] if (unit['kind'], unit['logical_id']) == (kind, name)]
        if len(found) != 1:
            raise ValueError('Thin path needs exactly one configured unit: ' + name)
        if found[0].get('operation_calls'):
            raise ValueError('Thin path does not include operation dispatch')
        result.append(deepcopy(found[0]))
    return result


def build_request(unit, boundary, controls, profile, *, correcting=False, accepted=()):
    """Send complete unit evidence and runtime controls, without operation-wide code or checklist mappings."""
    selected = {key: unit[key] for key in ('unit_id', 'kind', 'logical_id', 'configuration_xml',
        'effective_configuration', 'referenced_definitions', 'fingerprint')}
    requirements = {'observed-boundary': 'Exercise the configured unit and preserve its evidenced observable behavior'}
    request = dict(kind='thin_path_experiment', selected_unit=selected, sources=deepcopy(unit['sources']),
        allowed_evidence_ids=[source['identity'] for source in unit['sources']],
        runtime_controls=controls, requirements=requirements,
        boundary_identity={key: getattr(boundary, key) for key in ('unit_id', 'source_manifest_hash', 'configuration_hash')},
        coverage_example={'coverage': {'observed-boundary': ['src/test/java/com/company/generated/UnitTest.java']}},
        analysis_usage='Parser items guide deterministic cases and diagnostic coverage; no AI citation table required.',
        native_package='com.company.generated.thinpath', experiment_only=True)
    request['converted_dependency_apis'] = deepcopy(list(accepted))
    for dependency in accepted:
        request.setdefault('known_dependencies', []).extend(deepcopy(dependency['dependencies']))
    attach_testing_contract(request, profile)
    presence = ('\nPreserve the saved candidate API. Missing presence information remains a comparison limitation, '
        'not a requested code correction; do not add presence machinery to fix that limitation.' if correcting else
        '\nFor new DTO outputs that can be absent, record whether each field was written, including null, using '
        'public has<Field>() or was<Field>Set() boolean accessors backed by flags. Null alone is not presence information.')
    return request, INSTRUCTION+presence
