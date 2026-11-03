"""Run registered full-converter tasks through narrow, durable generation stages."""
from pathlib import Path
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.native_dependency_proposal import NativeDependencyProposal
from models.native_unit_bundle import NativeUnitBundle,NativeSourceFile
from models.staged_metadata import metadata_schema
from runtime.behavior_conversion.stage_tasks import StageTasks
from runtime.behavior_conversion.stage_compilation import production_compiler
from runtime.behavior_conversion.staged_adapters import production_request,assemble,check_metadata,task_revision_payload
from runtime.behavior_conversion.native_metadata import inspect_native,resolve_dependencies
from runtime.behavior_conversion.conversion_tasks import PIPELINE_VERSION
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from runtime.behavior_conversion.compiler_feedback import CompilerCorrectionError
from runtime.behavior_conversion.typed_boundaries import attach_typed_boundary,validate_typed_boundary,TypedBoundaryError
from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
from runtime.behavior_conversion.bundle_output import validate_bundle
from agents.behavior_conversion.staged_pipeline import code_instruction,METADATA,STRUCTURE,TESTS_ONLY,DEPENDENCIES
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import staged_conversion_state as state


class ProductionCorrection(ValueError):
    """A proven boundary difference belongs to implementation, not tests-only repair."""
    staged_retry_owner='implementation'
    def __init__(self,error):
        super().__init__(str(error));self.verification_feedback=error.verification_feedback


def staged_pipeline(conn,config,profile,category,identity,payload,schema,validator,model_call,kind,label=''):
    """Keep final validation/acceptance with the existing owning task validator."""
    from runtime.behavior_conversion.stage_scope import verify_parent
    verify_parent(conn,config,profile,category,identity,payload)
    payload=dict(payload)
    from runtime.behavior_conversion.verification_mode import executable_mode,conversion_mode,policy_payload
    if executable_mode(profile) or conversion_mode(profile):payload['executable_verification']=policy_payload(profile)
    if not payload.get('typed_boundary_contract'):attach_typed_boundary(payload)
    from runtime.behavior_conversion.compatibility import versioned_requirements
    platform=(payload.get('testing_contract') or {}).get('requirement',{}).get('requirement_id')
    payload['requirements']={item['requirement_id']:item['description'] for item in versioned_requirements(profile,category,payload)
                             if item['requirement_id']!=platform}
    if validator is None:raise VerificationIncomplete(dict(stage='staged_adapter',issues=['Task requires its existing final validator']))
    if payload.get('source_summaries'):raise VerificationIncomplete(dict(stage='source_evidence',issues=['Code generation requires complete source evidence']))
    revision=stable_id(PIPELINE_VERSION,category,identity,task_revision_payload(payload),profile.java_version,
        profile.allowed_ibm_classes,profile.unit_verification_policy.model_dump(mode='json'))
    tasks=StageTasks(conn,config,profile,identity,revision,model_call,validator,label,
        getattr(validator,'implementation_attempt',None),category=category,payload=payload)
    ask=tasks.ask
    parent=(conn,config,profile,category,identity,payload)
    if kind=='tests':return _tests_only(conn,config,identity,revision,payload,validator,ask,parent)
    compiler=getattr(validator,'compile_implementation',None)
    if compiler is None and kind!='contract':
        raise VerificationIncomplete(dict(stage='staged_adapter',issues=['Missing compile-only adapter for '+category]))
    compiler=compiler or production_compiler(profile)
    meta_schema=metadata_schema(schema)
    structure=None
    if kind=='contract':
        def check_structure(value):
            if value.unresolved_questions:raise ValueError('Unresolved data structure: '+str(value.unresolved_questions))
            expected={u['unit_id'] for u in payload.get('units',[])}
            if expected and ({u.unit_id for u in value.units}!=expected or len(value.units)!=len(expected)):
                raise ValueError('Contract structure must cover each configured unit exactly once')
        structure=ask('structure',dict(payload,task_kind='contract_structure'),STRUCTURE,meta_schema,check_structure)
    saved=state.read(conn,config.run_id,identity,revision,'feedback')['artifact_json']
    import json
    feedback=json.loads(saved) if saved else None
    while True:
        context={}
        request=production_request(payload,kind)
        if structure:request['planned_structure']=structure.model_dump(mode='json')
        if feedback:request['implementation_feedback']=feedback
        def implementation_check(value):
            state.invalidate_readiness(conn,config.run_id,identity,revision,'implementation')
            if any(not f.path.startswith('src/main/java/') for f in value.files):raise ValueError('Production stage cannot return tests')
            validate_bundle(NativeUnitBundle(files=value.files,unresolved_questions=value.unresolved_questions),allowed_classes=profile.allowed_ibm_classes)
            frozen=getattr(validator,'stage_prerequisites',{})
            owned_paths={f.path for f in value.files}
            inherited=[NativeSourceFile(path=p,content=t) for p,t in frozen.items() if p.startswith('src/main/java/') and p not in owned_paths]
            originals=payload.get('sources',[]) if executable_mode(profile) or conversion_mode(profile) or profile.metadata_checklist_batching and payload.get('parser_checklist') else ()
            if (executable_mode(profile) or conversion_mode(profile)) and not originals:
                from runtime.behavior_conversion.verification_ladder import active_verification
                session=active_verification()
                if session:originals=session.unit['sources']
            try:inventory=inspect_native([*value.files,*inherited],getattr(validator,'tool',None),originals)
            except ValueError as error:
                if 'Original Java parse failed:' in str(error):
                    raise VerificationIncomplete(dict(stage='metadata_original_parser',errors=[str(error)])) from error
                raise
            from runtime.behavior_conversion.staged_adapters import accepted_api_names
            for name in accepted_api_names(payload):inventory['types'].setdefault(name,dict(name=name,methods=[]))
            pins,unknown=resolve_dependencies(inventory,payload.get('known_dependencies',[]))
            if unknown:
                def check_pins(proposal):
                    _,missing=resolve_dependencies(inventory,payload.get('known_dependencies',[]),[d.model_dump(mode='json') for d in proposal.dependencies])
                    if missing:raise ValueError('Unresolved imports: '+str(missing))
                proposal=ask('dependencies',dict(unresolved_imports=unknown,known_dependencies=payload.get('known_dependencies',[])),
                    DEPENDENCIES,NativeDependencyProposal,check_pins)
                pins,_=resolve_dependencies(inventory,payload.get('known_dependencies',[]),[d.model_dump(mode='json') for d in proposal.dependencies])
            receipt=compiler(NativeUnitBundle(files=value.files,dependencies=pins))
            if not receipt.get('build_passed'):raise VerificationIncomplete(dict(stage='compile',issues=['Missing production compile receipt']))
            if payload.get('configured_unit') is not None:
                from runtime.behavior_conversion.java_api_types import public_api_types
                owners={name for file in value.files for name in public_api_types(file.content)}
                if not any(m['name']=='execute' and m.get('returns')=='int' for owner in owners
                           for m in inventory['types'].get(owner,{}).get('methods',[])):
                    raise ValueError('Configured step implementation must expose an int execute entry method, directly or inherited; correct Java before metadata generation')
            proof=dict(production_hash=stable_id(value.model_dump(mode='json')),validation=receipt,
                       dependencies=[d.model_dump(mode='json') for d in pins],acceptance=False)
            state.retain(conn,config.run_id,identity,revision,'compile',proof,stable_id(proof))
            context.update(inventory=inventory,dependencies=pins,production=value,receipt=receipt)
        frozen=getattr(validator,'frozen_implementation',None)
        if frozen is None:
            production=ask('implementation',request,code_instruction(payload),NativeImplementation,implementation_check)
        else:
            from runtime.behavior_conversion.frozen_implementation import revalidate_frozen
            production=revalidate_frozen(frozen,validator.frozen_implementation_hash,implementation_check)
        inventory=context['inventory'];dependencies=context['dependencies']
        def check_description(value):
            bundle=assemble(schema,value,production,dependencies,payload)
            if kind=='contract':
                from runtime.behavior_conversion.stage_readiness import prepare_metadata
                prepare_metadata(tasks,payload,production,inventory,bundle,lambda candidate:validator(candidate,cached=False))
            else:
                check_metadata(bundle,inventory,profile,payload,getattr(validator,'stage_prerequisites',{}))
                try:validate_typed_boundary(bundle,payload.get('typed_boundary_contract'))
                except TypedBoundaryError as error:
                    error.staged_retry_owner='implementation'
                    raise
                def prepared(candidate):
                    if getattr(validator,'validate_metadata',None):validator.validate_metadata(candidate)
                    if kind=='unit':
                        from runtime.behavior_conversion.verification_ladder import active_verification
                        session=active_verification()
                        if session:session.prepare_tests(candidate)
                from runtime.behavior_conversion.stage_readiness import prepare_metadata
                prepare_metadata(tasks,payload,production,inventory,bundle,prepared)
                if hasattr(value,'verification_binding'):value.verification_binding=getattr(bundle,'verification_binding',None)
            context['metadata']=value
        try:
            if structure:
                check_description(structure);description=structure
            else:
                from runtime.behavior_conversion.metadata_checklist import mapping_enabled,map_checklist
                from runtime.behavior_conversion.verification_mode import facts_disabled
                if executable_mode(profile) or facts_disabled(profile):
                    from runtime.behavior_conversion.metadata_semantics import describe
                    data=describe(tasks,payload,production,inventory,schema,lambda data:check_description(meta_schema.model_validate(data)))
                    description=context['metadata']
                elif mapping_enabled(tasks,payload):
                    from runtime.behavior_conversion.metadata_semantics import describe
                    def check_semantics(data):
                        from models.operation_data_contract import NativeApiContract
                        apis=[NativeApiContract.model_validate(api) for contract in data.get('contracts',{}).values() for api in contract['apis']]
                        if data.get('unit_contract'):apis.extend(NativeApiContract.model_validate(api) for api in data['unit_contract']['apis'])
                        validate_bundle(NativeUnitBundle(files=production.files),apis,allowed_classes=profile.allowed_ibm_classes,
                            dependency_files=getattr(validator,'stage_prerequisites',{}).items(),api_inventory=inventory)
                    data=describe(tasks,payload,production,inventory,schema,check_semantics)
                    data.update(map_checklist(tasks,payload,production,inventory))
                    description=meta_schema.model_validate(data)
                    check_description(description)
                else:
                    description=ask('metadata',dict(payload,task_kind=kind,production_files=[f.model_dump(mode='json') for f in production.files],
                        parsed_apis=inventory),METADATA,meta_schema,check_description)
        except (TypedBoundaryError,ImplementationInterfaceError) as error:
            from runtime.behavior_conversion.frozen_implementation import refuse_production_change
            refuse_production_change(validator,error)
            feedback=dict(stage='implementation_interface' if isinstance(error,ImplementationInterfaceError) else 'typed_boundary',
                error=str(error),previous_implementation=production.model_dump(mode='json'))
            if executable_mode(profile):
                from runtime.behavior_conversion.failure_routing import record_correction
                record_correction(tasks,'implementation',feedback)
            state.retain(conn,config.run_id,identity,revision,'feedback',feedback,stable_id(feedback))
            continue
        if kind in {'contract','implementation'}:
            bundle=assemble(schema,description,production,dependencies,payload)
            if kind!='contract':validator(bundle,cached=False)
            return _complete(conn,config,category,identity,revision,bundle,parent)
        test_request=dict(task_kind=kind,original_evidence=payload,production_files=[f.model_dump(mode='json') for f in production.files],
            parsed_apis=inventory,requirements=payload.get('requirements',{}),testing_contract=payload.get('testing_contract'),
            known_dependencies=payload.get('known_dependencies',[]))
        if executable_mode(profile):
            test_request['original_evidence']={key:value for key,value in payload.items()
                if key not in {'parser_checklist','checklist','analysis_tool_hash','approved_exclusions'}}
        if not test_request['testing_contract']:test_request.pop('testing_contract')
        if hasattr(description,'verification_binding') and description.verification_binding:
            from runtime.behavior_conversion.native_test_scope import test_scope
            unit=payload.get('configured_format') or payload.get('configured_unit') or payload.get('unit') or payload
            if isinstance(unit,dict) and unit.get('kind'):
                test_request['selected_boundary']=test_scope(unit,description.verification_binding,payload.get('runtime_controls',[]))
        if conversion_mode(profile):
            from runtime.behavior_conversion.native_test_scope import conversion_test_scope
            unit=payload.get('configured_format') or payload.get('configured_unit') or payload.get('selected_unit') or payload.get('unit') or payload
            settings=getattr(validator,'preparation',{}).get('native_settings_apis',[])
            scope=conversion_test_scope(unit,inventory,production.files,settings)
            if scope:test_request['selected_boundary']=scope
        if payload.get('format_chains'):
            from runtime.component_conversion.format_chain_tests import INSTRUCTION as CHAIN_TESTS
            test_request['chain_regression_policy']=CHAIN_TESTS
        eligibility=stable_id(revision,TESTS_ONLY)
        test_context=dict(revision=revision,eligibility_hash=eligibility,production_hash=stable_id(production.model_dump(mode='json')),
            source_hash=stable_id(payload),selected_boundary=test_request.get('selected_boundary'),
            parsed_api_hash=stable_id(inventory['apis']),metadata_hash=stable_id(description.model_dump(mode='json')))
        def check_tests(value):
            state.invalidate_readiness(conn,config.run_id,identity,revision,'tests')
            if value.unresolved_questions or any(not f.path.startswith('src/test/java/') for f in value.files):raise ValueError('Tests-only stage must return complete executable tests')
            from runtime.component_conversion.format_chain_tests import validate_chain_tests
            validate_chain_tests(value,payload)
            test_inventory=inspect_native(value.files,getattr(validator,'tool',None))
            if test_request.get('selected_boundary'):
                from runtime.behavior_conversion.native_test_scope import validate_test_scope
                validate_test_scope(test_inventory,test_request['selected_boundary'])
            test_inventory['types']={**inventory['types'],**test_inventory['types']}
            pins,missing=resolve_dependencies(test_inventory,payload.get('known_dependencies',[]),[p.model_dump(mode='json') for p in dependencies])
            if missing:raise ValueError('Tests must use pinned libraries/native APIs: '+str(missing))
            all_pins={(d.group_id,d.artifact_id):d for d in [*dependencies,*pins]}
            bundle=assemble(schema,description,production,list(all_pins.values()),payload,value)
            native=NativeUnitBundle(files=bundle.files,dependencies=bundle.dependencies,coverage=bundle.coverage,
                                   unresolved_questions=bundle.unresolved_questions)
            validate_bundle(native,requirements=payload['requirements'],allowed_classes=profile.allowed_ibm_classes)
            if payload.get('testing_contract'):
                from runtime.behavior_conversion.testing_contract import validate_testing_contract
                validate_testing_contract(native,payload['testing_contract'])
            previous=getattr(validator,'last',None);outcome=None
            try:
                if executable_mode(profile):
                    from runtime.behavior_conversion.adapter_repair import validate_with_adapter_repair
                    def recheck(binding):
                        description.verification_binding=binding
                        from runtime.behavior_conversion.stage_readiness import prepare_metadata
                        def prepared(candidate):
                            if getattr(validator,'validate_metadata',None):validator.validate_metadata(candidate)
                            if kind=='unit':
                                from runtime.behavior_conversion.verification_ladder import active_verification
                                session=active_verification()
                                if session:session.prepare_tests(candidate)
                        prepare_metadata(tasks,payload,production,inventory,bundle,prepared)
                        from runtime.behavior_conversion.native_test_scope import test_scope,validate_test_scope
                        selected=test_scope(payload.get('configured_format') or payload.get('configured_unit') or payload.get('unit') or payload,
                            binding,payload.get('runtime_controls',[]))
                        if 'selected_boundary' in test_request:
                            test_request['selected_boundary'].clear();test_request['selected_boundary'].update(selected)
                        else:test_request['selected_boundary']=selected
                        validate_test_scope(test_inventory,selected)
                        test_context.update(selected_boundary=selected,metadata_hash=stable_id(description.model_dump(mode='json')))
                    from runtime.behavior_conversion.stage_readiness import testing_gate
                    with testing_gate(tasks,bundle):
                        outcome=validate_with_adapter_repair(tasks,payload,production,inventory,bundle,validator,recheck)
                else:
                    from runtime.behavior_conversion.stage_readiness import testing_gate
                    with testing_gate(tasks,bundle):outcome=validator(bundle,cached=False)
            except VerificationIncomplete:raise
            except VerificationFailure as error:
                if error.verification_feedback.get('stage') in {'boundary','thin_path_boundary'}:raise ProductionCorrection(error) from error
                raise
            except ValueError as error:
                from runtime.component_conversion.format_chain_tests import assertion_regression
                regression=assertion_regression(error,payload)
                if regression:
                    state.retain(conn,config.run_id,identity,revision,'regression_tests',value.model_dump(mode='json'),stable_id(value.model_dump(mode='json')))
                    raise ProductionCorrection(VerificationFailure(regression)) from error
                raise
            finally:
                latest=getattr(validator,'last',None)
                proof=outcome if isinstance(outcome,dict) else latest if latest is not previous else None
                if proof:state.retain_passing_tests(conn,config.run_id,identity,revision,value.model_dump(mode='json'),test_context,proof.get('build_validation'))
            context['bundle']=bundle
        try:
            retained=state.passing_tests(conn,config.run_id,identity,revision,eligibility)
            reused=False
            supplied=getattr(validator,'frozen_tests',None)
            regression=state.read(conn,config.run_id,identity,revision,'regression_tests')
            if supplied is None and regression['artifact_json']:
                import json
                supplied=NativeTestBundle.model_validate_json(regression['artifact_json'])
                if stable_id(supplied.model_dump(mode='json'))!=regression['artifact_hash']:raise ValueError('Retained chain regression tests changed')
            if supplied is not None:
                check_tests(NativeTestBundle.model_validate(supplied.model_dump(mode='json')))
                reused=True
            elif retained:
                try:
                    if retained['context']['selected_boundary']!=test_context['selected_boundary']:raise ValueError('Selected API changed; repair retained tests against current parsed APIs')
                    check_tests(NativeTestBundle.model_validate(retained['tests']));reused=True
                except (VerificationFailure,ProductionCorrection):raise
                except ValueError as error:
                    correction=getattr(error,'compiler_correction',None)
                    if correction and any(not d.get('file','').startswith('src/test/java/') for d in correction.get('diagnostics',[])):raise
                    test_request.update(retained_test_bundle=retained['tests'],retained_test_revalidation_error=str(error))
                    if correction:test_request['compiler_correction']=correction
                    if getattr(error,'test_correction',None):test_request['test_correction']=error.test_correction
            if not reused:ask('tests',test_request,TESTS_ONLY,NativeTestBundle,check_tests)
            return _complete(conn,config,category,identity,revision,context['bundle'],parent)
        except VerificationIncomplete:raise
        except (ProductionCorrection,CompilerCorrectionError) as error:
            from runtime.behavior_conversion.frozen_implementation import refuse_production_change
            refuse_production_change(validator,error)
            if isinstance(error,CompilerCorrectionError) and all(d.get('file','').startswith('src/test/java/') for d in error.compiler_correction.get('diagnostics',[])):raise
            feedback=dict(error=str(error),details=getattr(error,'verification_feedback',None) or error.compiler_correction,
                previous_implementation=production.model_dump(mode='json'))
            if executable_mode(profile):
                from runtime.behavior_conversion.failure_routing import record_correction
                record_correction(tasks,'implementation',feedback)
            state.retain(conn,config.run_id,identity,revision,'feedback',feedback,stable_id(feedback))


def _complete(conn,config,category,identity,revision,bundle,parent):
    """Save only after the original owning validator has passed all its required checks."""
    from tools.state_store_tools.behavior_units import save
    fingerprint=stable_id(PIPELINE_VERSION,revision,bundle.model_dump(mode='json'))
    from runtime.behavior_conversion.stage_scope import verify_parent
    binding=verify_parent(*parent)
    if binding:
        from runtime.scoped_native.results import record_result
        record_result(binding,conn,config,parent[2],category,identity,fingerprint,bundle.model_dump(mode='json'))
    state.retain(conn,config.run_id,identity,revision,'complete',bundle.model_dump(mode='json'),fingerprint)
    save(conn,config.run_id,category,identity,fingerprint,bundle.model_dump(mode='json'))
    state.retain_task_request(conn,config.run_id,identity,revision,category,parent[-1],fingerprint)
    return bundle,fingerprint


def _tests_only(conn,config,identity,revision,payload,validator,ask,parent):
    """Route scenarios cannot regenerate production or operation contracts."""
    result={}
    def check(value):
        from tools.state_store_tools import staged_conversion_state as state
        state.invalidate_readiness(conn,config.run_id,identity,revision,'tests')
        if value.unresolved_questions or any(not f.path.startswith('src/test/java/') for f in value.files):raise ValueError('Route-test stage may return tests only')
        bundle=NativeUnitBundle(files=value.files,coverage=value.coverage)
        validator(bundle,cached=False);result['bundle']=bundle
    ask('tests',dict(payload,task_kind='route_tests'),TESTS_ONLY,NativeTestBundle,check)
    return _complete(conn,config,'route_scenario_test',identity,revision,result['bundle'],parent)
