"""Resolve complete parser mappings and describe only an already-built native entry API."""
from models.component_unit_binding import ComponentUnitBinding
from models.unit_checklist_answers import UnitChecklistAnswers
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete

INSTRUCTION = '''Return only ComponentUnitBinding metadata for the supplied frozen native API.
Do not generate, change or invent implementation code, public methods, expected outputs or harness
adapters. Describe the actual entry method, unchanged XML/context inputs, runtime settings and
observable context getters from the supplied source. Step methods preserve their integer result;
request-unformat exposes actual writes with output=none; response-format returns XML.
Metadata will be validated against the built source and compared to the original unit boundary.
Correct binding feedback without weakening behavior checks. Sources and syntax are authoritative.
'''


def resolve_checklist(artifacts, boundary):
    """Every original item needs a real current citation or an existing whole-format exclusion."""
    report = artifacts['root_report']
    if report.get('format_candidate'):
        return UnitChecklistAnswers.model_validate(report['format_candidate']['checklist_answers'])
    locations = {}
    master = {item['id']:item for item in boundary['parser_checklist']['items']}
    for evidence in artifacts['reports'].values():
        for item in evidence['parser_checklist']:
            expected = master.get(item['id'])
            if expected is None:
                continue
            if (item['source_identity'], item['source_hash']) != (expected['source_identity'], expected['source_hash']):
                raise ValueError('Component checklist provenance changed')
            for location in evidence['checklist_implementations'].get(item['id'], []):
                if (location['path'].startswith('src/main/java/') and location['excerpt'].strip()
                        and location['excerpt'] in artifacts['files'].get(location['path'], '')):
                    if location not in locations.setdefault(item['id'], []):
                        locations[item['id']].append(location)
    missing = sorted(set(master)-set(locations))
    if missing:
        raise VerificationIncomplete(dict(stage='component_checklist', missing_item_ids=missing))
    return UnitChecklistAnswers(unit_id=boundary['unit_id'], source_manifest_hash=boundary['source_manifest_hash'],
        configuration_hash=boundary['configuration_hash'], responses=[dict(checklist_id=key,status='implemented',locations=locations[key])
            for key in sorted(master)])


def native_unit_binding(conn, config, profile, unit, artifacts, build_bundle, validator, model_call):
    """Reuse trusted format recipes; ask only for missing step metadata through bounded retries."""
    candidate = artifacts['root_report'].get('format_candidate')
    if candidate:
        metadata = ComponentUnitBinding(verification_binding=candidate['verification_binding'])
        bundle = build_bundle(metadata)
        validator(bundle, cached=False)
        return bundle
    owned = artifacts['root_report']['owned_sources']
    from runtime.behavior_conversion.api_surface import api_surface
    from models.native_unit_bundle import NativeUnitBundle
    public = api_surface(NativeUnitBundle(files=[dict(path=name,content=text) for name,text in artifacts['files'].items()]))
    request = dict(unit_id=unit.unit_id, kind=unit.kind, component_proof=artifacts['proof'],
        entry_apis=artifacts['contract']['apis'], configuration=unit.effective_configuration,
        native_contract=artifacts['contract'],native_api_surface=public,
        native_sources={name:artifacts['files'][name] for name in owned},
        context_obligations=dict(direction=unit.kind, configuration_xml=unit.configuration_xml))
    def check(metadata, cached=False):
        validator(build_bundle(metadata), cached=False)
    from runtime.behavior_conversion.verification_mode import executable_mode
    if executable_mode(profile):
        from models.native_implementation import NativeImplementation
        from runtime.behavior_conversion.native_metadata import inspect_native
        from runtime.behavior_conversion.executable_adapters import resolve_adapter
        production=NativeImplementation(files=[dict(path=name,content=text) for name,text in artifacts['files'].items()
            if name.startswith('src/main/java/')])
        inventory=inspect_native(production.files,original_sources=unit.model_dump(mode='json')['sources'])
        class AdapterTask:
            """Keep the existing scoped unit-binding authorization and durable retry budget."""
            def ask(self,stage,payload,instruction,schema,validate):
                value,_=generate(conn,config,profile,'unit_binding',unit.unit_id,instruction,{**request,**payload},schema,
                    validator=lambda value,cached=False:validate(value),model_call=model_call,label='Native executable adapter: '+unit.logical_id,
                    require_coverage=False)
                return value
        binding=resolve_adapter(AdapterTask(),dict(unit.model_dump(mode='json'),requirements={'business':'Preserve configured boundary'},
            native_contract=artifacts['contract']),production,inventory)
        result=build_bundle(ComponentUnitBinding(verification_binding=binding))
        validator(result,cached=False)
        return result
    metadata, _ = generate(conn, config, profile, 'unit_binding', unit.unit_id, INSTRUCTION, request,
        ComponentUnitBinding, validator=check, model_call=model_call, label='Native entry binding: '+unit.logical_id)
    return build_bundle(metadata)
