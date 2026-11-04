"""Fill trusted provenance/APIs locally and keep semantic choices separate from citations."""
from copy import deepcopy
from models.staged_metadata import metadata_schema
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.component_inventory_tools.identity import stable_id
from agents.behavior_conversion.metadata_checklist import SEMANTICS


def semantic_request(payload,production,inventory):
    """Exclude checklist, test templates, historical responses and redundant transport data."""
    allowed={'kind','configured_unit','configured_format','unit','selected_unit','contract','requirements',
        'typed_boundary_contract','runtime_controls','operation_calls','service_connections','required_step_dependencies',
        'required_runtime_resources','format_partition','native_package'}
    result={k:v for k,v in payload.items() if k in allowed}
    owners={name for f in production.files for name in public_api_types(f.content)}
    result.update(production_files=[f.model_dump(mode='json') for f in production.files],
        parsed_apis=[dict(type_name=api['type_name'],members=[dict(member_id=stable_id(api['type_name'],signature),signature=signature) for signature in api['method_signatures']]) for api in inventory['apis'] if api['type_name'] in owners],
        api_owners=sorted(owners))
    # Exact original methods/configuration can be followed through this local source
    # selection. Do not resend test examples, checklist entries or previous giant bundles.
    result['sources']=payload.get('sources',[])
    if payload.get('executable_verification',{}).get('mode') in {'executable_boundary_v1','conversion_checklist_v1'}:
        result['slice_sources']=payload.get('slice_sources',[])
    return result


def materialize(value,payload,inventory,production):
    """Only APIs on owned types can be exported; no model-created signatures or hashes."""
    data=deepcopy(value.model_dump(mode='json'))
    owned={name for f in production.files for name in public_api_types(f.content)}
    apis={api['type_name']:api for api in inventory['apis'] if api['type_name'] in owned}
    def selected(names,members):
        if len(set(names))!=len(names) or not names or set(names)-set(apis):raise ValueError('Select distinct API owners from the supplied owned native types')
        if set(members)-set(names):raise ValueError('API member selections must belong to selected owners')
        result=[]
        for name in names:
            api=deepcopy(apis[name])
            if name in members:
                index={stable_id(name,s):s for s in api['method_signatures']}
                if not members[name] or len(set(members[name]))!=len(members[name]) or set(members[name])-set(index):raise ValueError('Select distinct existing parser member IDs')
                api['method_signatures']=[index[key] for key in members[name]]
            result.append(api)
        return result
    expected=payload.get('expected_contract_fields',{})
    if 'contracts' in data:
        if set(data['contracts'])!=set(expected):raise ValueError('Semantic metadata must select exactly the assigned component IDs: '+str(sorted(expected)))
        contracts={}
        for key,semantics in data['contracts'].items():
            names=semantics.pop('api_types')
            members=semantics.pop('api_members')
            contracts[key]={**semantics,**expected[key],'apis':selected(names,members)}
        data['contracts']=contracts
    evidence=list(dict.fromkeys([item for fields in expected.values() for item in fields['evidence_ids']] or [s['identity'] for s in payload.get('sources',[])]))
    if not evidence and payload.get('executable_verification',{}).get('mode') in {'executable_boundary_v1','conversion_checklist_v1'}:
        evidence=list(payload.get('evidence_ids',[]))
    if data.get('unit_contract') is not None:
        unit=payload.get('unit') or payload.get('selected_unit') or payload
        data['unit_contract']=dict(unit_id=unit.get('unit_id') or payload['unit_id'],apis=selected(data['unit_contract']['api_types'],data['unit_contract']['api_members']),
            requirements=payload['requirements'],evidence_ids=evidence,dependency_units=[d['unit_id'] for d in payload.get('converted_dependency_apis',[])])
    if data.get('operation_contract') is not None and payload.get('accepted_units') is not None:
        units={}
        for accepted in payload['accepted_units'].values():
            contract=deepcopy(accepted['contract']);identity=contract['unit_id']
            if identity in units and units[identity]!=contract:
                raise ValueError('Conflicting accepted unit contracts: '+identity)
            units[identity]=contract
        data['operation_contract']['units']=[units[key] for key in sorted(units)]
    data['evidence_ids']=evidence
    return data


def describe(tasks,payload,production,inventory,schema,check):
    """Only semantic repair is sent here; checklist work uses its own item controller."""
    request=semantic_request(payload,production,inventory)
    from runtime.behavior_conversion.deterministic_contracts import enabled,derive,INSTRUCTION
    from models.staged_metadata import deterministic_metadata_schema
    from runtime.behavior_conversion.verification_mode import conversion_mode
    local=enabled(payload,schema)
    meta=deterministic_metadata_schema(schema,conversion_mode(tasks.profile)) if local else metadata_schema(schema,True)
    instruction=INSTRUCTION if local else SEMANTICS
    if conversion_mode(tasks.profile):
        instruction='Return only the supplied semantic details schema for compiled native code. The application derives APIs, ownership and provenance. Where entry_type is supplied, select the actual native entry owner from parsed_apis. Describe required configuration, initialization, runtime inputs and effects. Do not return comparison bindings, invocation recipes, checklist mappings, source code or tests.'
    if payload.get('kind')=='service' and 'unit_contract' in meta.model_fields:
        instruction+='\nThis is whole-operation metadata, not a single configured unit: leave unit_contract null. Describe operation_contract and its actual compiled service API. The application populates operation_contract.units from verified accepted contracts; do not invent or reconstruct unit identities.'
    from runtime.behavior_conversion.verification_mode import executable_mode
    from runtime.behavior_conversion.verification_mode import conversion_mode
    limit=(tasks.profile.behavior_context_chars if executable_mode(tasks.profile) or conversion_mode(tasks.profile) else
           min(tasks.profile.behavior_context_chars,tasks.profile.metadata_checklist_request_chars)-tasks.profile.metadata_checklist_response_chars)
    try:encode_request(dict(request,schema=meta.model_json_schema()),instruction,limit)
    except ValueError as error:
        # Never fall back to the old giant combined metadata task.
        raise VerificationIncomplete(dict(stage='metadata_semantic_evidence',errors=[str(error)],
            action='Partition this semantic contract/evidence; no checklist request has been sent')) from error
    def completed(value):
        if local and not conversion_mode(tasks.profile) and 'verification_binding' in type(value).model_fields and value.verification_binding is None:
            from runtime.behavior_conversion.executable_adapters import resolve_adapter
            binding=resolve_adapter(tasks,payload,production,inventory)
            value=value.model_copy(update={'verification_binding':binding})
        if local:value=metadata_schema(schema,True).model_validate(derive(value,payload,inventory,production))
        return materialize(value,payload,inventory,production)
    def validate(value):check(completed(value))
    value=tasks.ask('semantic_metadata',request,instruction,meta,validate,request_limit=limit)
    return completed(value)
