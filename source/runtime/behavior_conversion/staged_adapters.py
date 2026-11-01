"""Assemble existing final bundle schemas from frozen code and metadata-only stages."""
from models.native_unit_bundle import NativeUnitBundle
from models.operation_data_contract import OperationDataContract
from runtime.behavior_conversion.bundle_output import validate_bundle


def task_revision_payload(payload):
    """Keep source/contracts in task identity; feedback and derived advice cannot reset budgets."""
    from runtime.scoped_native.results import fingerprint_payload
    value=fingerprint_payload(payload,'staged')
    for key in ('whole_unit_feedback','final_validation_feedback','behavior_review_feedback','previous_bundle',
                'previous_model_response','correction_feedback','compiler_correction','test_correction'):
        value.pop(key,None)
    return value


def production_request(payload,kind):
    """Exclude testing and citation duties without removing original Java/XML behavior evidence."""
    excluded={'parser_checklist','analysis_tool_hash','schema','testing_contract','coverage_example',
        'coverage_response_example','versioned_requirements','expected_contract_fields','requirements',
        'final_validation_feedback','final_validation_requirements','approved_exclusions'}
    if payload.get('executable_verification',{}).get('mode')=='executable_boundary_v1':excluded.add('checklist')
    request={key:value for key,value in payload.items() if key not in excluded}
    request['task_kind']=kind
    request['behavior_requirements']=list(payload.get('requirements',{}).values())
    return request


def accepted_api_names(payload):
    """Read native class names only from supplied accepted prerequisite contracts."""
    names=set()
    def visit(value):
        if isinstance(value,dict):
            for api in value.get('apis',[]):
                if isinstance(api,dict) and isinstance(api.get('type_name'),str):names.add(api['type_name'])
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    for key in ('accepted_units','converted_dependency_apis','prerequisite_components'):visit(payload.get(key))
    return names


def assemble(schema,metadata,production,dependencies,payload,tests=None):
    """Only the application can join independently checked code, metadata and test files."""
    data=metadata.model_dump(mode='json')
    main=[file.model_dump(mode='json') for file in production.files]
    if schema is OperationDataContract:
        data['sources']=main
        return schema.model_validate(data)
    operation=data.get('operation_contract')
    if operation is not None:
        operation['sources']=(payload.get('contract') or {}).get('sources') or main
    data.update(files=main+([f.model_dump(mode='json') for f in tests.files] if tests else []),
                dependencies=[d.model_dump(mode='json') for d in dependencies],coverage=tests.coverage if tests else {})
    return schema.model_validate(data)


def check_metadata(bundle,inventory,profile,payload=None,prerequisites=None):
    """API declarations must exist in the frozen production files; citations are checked later."""
    apis=[]
    if getattr(bundle,'contracts',None):apis=[api for contract in bundle.contracts.values() for api in contract.apis]
    if getattr(bundle,'unit_contract',None):apis+=bundle.unit_contract.apis
    if getattr(bundle,'operation_contract',None):apis.append(bundle.operation_contract.service_api)
    native=NativeUnitBundle(files=bundle.files,unresolved_questions=bundle.unresolved_questions)
    validate_bundle(native,apis,allowed_classes=profile.allowed_ibm_classes,dependency_files=(prerequisites or {}).items(),api_inventory=inventory)
    for api in apis:
        if api.type_name not in inventory['types']:raise ValueError('Metadata invented native API '+api.type_name)
    payload=payload or {}
    if getattr(bundle,'unit_contract',None) and not set(payload.get('requirements',{})).issubset(bundle.unit_contract.requirements):
        raise ValueError('Unit metadata must declare all versioned behavior requirements')
    if getattr(bundle,'contracts',None):
        expected=payload.get('expected_contract_fields',{})
        if expected and set(bundle.contracts)!=set(expected):raise ValueError('Metadata must cover exactly the assigned components')
        for key,fields in expected.items():
            actual=bundle.contracts[key].model_dump(mode='json')
            if any(actual.get(name)!=value for name,value in fields.items()):raise ValueError('Component metadata changed expected identity/configuration: '+key)
        from runtime.behavior_conversion.verification_mode import executable_mode
        if not payload.get('configured_format') and not executable_mode(profile):
            files={**(prerequisites or {}),**{f.path:f.content for f in bundle.files}}
            from runtime.behavior_conversion.metadata_checklist_validation import validate_component_mappings
            validate_component_mappings(bundle.checklist_implementations,{i['id'] for i in payload.get('parser_checklist',[])},files)
