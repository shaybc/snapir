"""Prepare source-defined settings and executable cases before requesting native tests."""
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete,VerificationFailure
from runtime.behavior_conversion.failure_routing import AdapterRepairRequired
from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
from runtime.behavior_conversion.native_binding_builder import validate_parsed_binding
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.verification_cases import controlled_cases
from tools.component_inventory_tools.identity import stable_id
from runtime.behavior_conversion.context_key_evidence import with_context_key_evidence


def prepare_settings(unit,boundary,bundle,controls,*,tool=None,settings=None,inventory=None):
    """Require real native settings APIs, complete wiring and constructible comparison cases."""
    if controls and not unit.get('effective_configuration'):
        raise VerificationIncomplete(dict(stage='configuration_preparation',errors=['Resolved configuration XML is required before test generation']))
    if inventory is None:
        from runtime.behavior_conversion.native_metadata import inspect_native
        originals={s['identity']:s for s in unit.get('sources',[])}
        for control in controls:
            if control.get('source_identity') and control.get('source_content'):
                originals[control['source_identity']]=dict(identity=control['source_identity'],content=control['source_content'])
        inventory=inspect_native(bundle.files,tool,list(originals.values()))
    inventory=with_context_key_evidence(unit,inventory)
    for control in controls:
        original=[m for m in inventory.get('original_methods',[]) if m['target']==control['target']]
        if len(original)!=1:
            raise VerificationIncomplete(dict(stage='settings_preparation',errors=['Original settings signature is missing or ambiguous: '+control['target']]))
        parameters=original[0]['parameters']
        candidates=[(owner,m['name']) for owner,t in inventory['types'].items() for m in t['methods']
                    if m.get('static')=='true' and [p['type'] for p in m['parameters']]==parameters]
        if not candidates:
            raise ImplementationInterfaceError('Missing native runtime-settings API for '+control['target']+
                '; required static parameter types: '+str(parameters))
    try:
        validate_binding(bundle)
        validate_parsed_binding(bundle.verification_binding,inventory,controls)
    except (ValueError,VerificationFailure) as error:
        repair=AdapterRepairRequired(dict(stage='binding_preparation',errors=[str(error)],
            required_settings=[dict(target=c['target'],arity=c['arity']) for c in controls]))
        repair.preparation_context=dict(configured_format=unit,configured_unit=unit,unit=unit,runtime_controls=controls)
        if bundle.verification_binding:
            inventory=dict(inventory,owned_types=[bundle.verification_binding.owner_type])
        repair.preparation_inventory=inventory
        repair.preparation_files=bundle.files
        raise repair from error
    generation={}
    cases=controlled_cases(unit,boundary,bundle.verification_binding,controls,
        executable_settings=settings,generation_report=generation)
    return dict(settings_targets=sorted(c['target'] for c in controls),case_count=len(cases),
        cases_hash=stable_id([c.model_dump(mode='json') for c in cases]),
        binding_hash=stable_id(bundle.verification_binding.model_dump(mode='json')))
