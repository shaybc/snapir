"""Resolve unsupported wiring in its own bounded role without editing business code."""
from models.native_executable_adapter import NativeExecutableAdapter
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.native_binding_builder import build_binding,validate_parsed_binding,BindingAmbiguous
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from runtime.behavior_conversion.java_api_types import public_api_types
from tools.behavior_verification.thin_path_binding import configured_fields
from runtime.behavior_conversion.adapter_configuration import resolve_configuration

VERSION='restricted-executable-adapter-v1'
INSTRUCTION='''Return only NativeExecutableAdapter for the supplied frozen production APIs.
This is an invocation plan executed by converter-owned Java, not business code or tests.
Bind unchanged XML or original context values to existing native constructors/setters.
Use factory_method only for an existing public static method returning its own native DTO type.
Call the selected format/serialize, unformat/parse or execute entry. Project actual result/argument
getters and presence accessors. Do not invent constants, expected answers, framework behavior,
source files, expressions or Java code. Preserve runtime setting bindings and observable writes.
If this plan cannot represent the boundary, return limitation instead of binding; do not change production code.'''


def resolve_adapter(tasks,payload,production,inventory,*,repair_feedback=None):
    """Try deterministic wiring first; adapter errors stay within the adapter role budget."""
    if hasattr(tasks,'fresh'):tasks.fresh()
    try:
        unit,partition=resolve_configuration(payload)
    except ValueError as error:
        raise VerificationIncomplete(dict(stage='adapter',errors=[str(error)],action='Restore trusted configuration; production is unchanged')) from error
    if unit.get('kind') not in {'request_unformat','response_format','configured_step'}:
        raise VerificationIncomplete(dict(stage='adapter',errors=['A configured executable boundary is required']))
    if 'effective_configuration' not in unit:
        raise VerificationIncomplete(dict(stage='adapter',errors=['Configured boundary XML evidence is required for adapter repair']))
    owned={name for file in production.files for name in public_api_types(file.content)}
    if inventory.get('owned_types') is not None:owned.intersection_update(inventory['owned_types'])
    declared=payload.get('native_contract',{}).get('apis',[])
    entries=owned & {a['type_name'] for a in declared} if declared else owned
    expected={'request_unformat':{'unformat','parse'},'response_format':{'format','serialize'},'configured_step':{'execute'}}
    owners={owner for owner in entries if any(m['name'] in expected[unit['kind']] for m in inventory['types'].get(owner,{}).get('methods',[]))}
    if len(owners)!=1:
        raise VerificationIncomplete(dict(stage='adapter',errors=['Selected production entry owner is missing or ambiguous'],candidates=sorted(owners)))
    selected_owner=next(iter(owners))
    metadata=dict(inventory,owned_types={selected_owner})
    keys={item['name'] for item in inventory.get('context_keys',[])}
    keys.update(field['context_key'] for field in configured_fields(unit))
    metadata['context_keys']=[dict(name=key) for key in sorted(keys)]
    controls=payload.get('runtime_controls',[])
    evidence=payload.get('evidence_ids') or [s['identity'] for s in payload.get('sources',[])]
    if not evidence:
        evidence=[key for fields in payload.get('expected_contract_fields',{}).values() for key in fields['evidence_ids']]
    if not evidence:
        raise VerificationIncomplete(dict(stage='adapter',errors=['Known original source identities are required']))
    def checked(binding):
        if binding.method_name not in expected[unit['kind']]:raise ValueError('Adapter must invoke the configured boundary entry')
        if binding.owner_type!=selected_owner:raise ValueError('Adapter must invoke the selected production entry owner')
        bundle=NativeUnitBundle(files=production.files,unit_contract=dict(unit_id=unit['unit_id'],apis=inventory['apis'],
            requirements=payload.get('requirements',{}),evidence_ids=evidence),verification_binding=binding)
        validate_binding(bundle)
        validate_parsed_binding(binding,metadata,controls)
        return binding
    try:
        if repair_feedback:raise BindingAmbiguous('Repair the failed frozen-production invocation plan')
        binding=build_binding(unit,metadata,controls)
        # Automatic request-result projection requires a presence-aware observer.
        # Never treat a DTO getter alone as proof of which context keys were written.
        if unit['kind']=='request_unformat':raise BindingAmbiguous('Request state needs explicit result/argument projections')
        return checked(binding)
    except (BindingAmbiguous,VerificationFailure,ValueError) as error:
        ambiguity=str(error)
    request=dict(unit_id=unit['unit_id'],kind=unit['kind'],configuration=unit.get('effective_configuration'),
        configuration_xml=unit.get('configuration_xml'),parsed_apis=inventory,runtime_controls=controls,
        production_files=[f.model_dump(mode='json') for f in production.files],ambiguity=ambiguity,
        adapter_version=VERSION)
    if repair_feedback:request['adapter_feedback']=repair_feedback
    if partition is not None:request['format_partition']=partition
    def check_plan(value):
        if value.limitation:
            raise VerificationIncomplete(dict(stage='adapter',errors=[value.limitation],action='Unsupported adapter capability; production is unchanged'))
        checked(value.binding)
    try:
        return tasks.ask('adapter',request,INSTRUCTION,NativeExecutableAdapter,check_plan).binding
    except VerificationIncomplete:raise
    except (ValueError,OSError) as error:
        raise VerificationIncomplete(dict(stage='adapter',errors=[str(error)],
            action='Adapter repair budget exhausted or wiring unsupported; production is unchanged')) from error
