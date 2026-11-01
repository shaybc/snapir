"""Orchestrate narrow implementation, binding and test requests with deterministic metadata."""
from copy import deepcopy
import json
from pathlib import Path
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.native_mapping_selection import NativeMappingSelection
from models.native_dependency_proposal import NativeDependencyProposal
from models.native_unit_bundle import NativeUnitBundle
from models.operation_data_contract import UnitContract
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.native_test_scope import test_scope, validate_test_scope
from runtime.behavior_conversion.native_metadata import inspect_native, resolve_dependencies
from runtime.behavior_conversion.native_binding_builder import build_binding, validate_parsed_binding, BindingAmbiguous
from runtime.behavior_conversion.typed_boundaries import attach_typed_boundary, validate_typed_boundary, TypedBoundaryError
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from runtime.behavior_conversion.compiler_feedback import CompilerCorrectionError
from runtime.behavior_conversion.test_feedback import TestCorrectionError
from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
from runtime.behavior_conversion.testing_contract import validate_testing_contract
from agents.behavior_conversion.staged_instructions import IMPLEMENTATION, TESTS, MAPPING, DEPENDENCIES
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import staged_conversion_state as state
from tools.behavior_verification.java_tool import default_tool_path
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest


class ImplementationCorrection(ValueError):
    """A boundary mismatch belongs to production repair, never repeated test generation."""
    staged_retry_owner = 'implementation'
    def __init__(self,error):
        super().__init__(str(error))
        self.verification_feedback=getattr(error,'verification_feedback',{})


def staged_generate(conn,config,profile,category,identity,instruction,payload,schema,validator=None,
                    model_call=None,label='',require_coverage=True,implementation_attempt=None):
    """Build complete bundles locally; all AI calls have a single response responsibility."""
    from runtime.behavior_conversion.generation import _generate
    from runtime.model_execution.adk_executor import AdkExecutor
    if not callable(getattr(validator,'compile_implementation',None)):
        raise VerificationIncomplete(dict(stage='staged',issues=['Isolated compile/comparison adapter required']))
    fresh=getattr(validator,'fresh',lambda:None)
    fresh()
    unit=payload.get('selected_unit',payload.get('unit',payload))
    if not payload.get('sources') or payload.get('source_summaries'):
        raise VerificationIncomplete(dict(stage='staged',issues=['Complete original Java evidence required']))
    jar=Path(getattr(validator,'tool',None) or default_tool_path())
    if not jar.is_file():raise VerificationIncomplete(dict(stage='staged',issues=['Build the JavaParser inspection tool first']))
    revision=stable_id('staged-v1',unit,payload['sources'],payload.get('converted_dependency_apis',[]),
        payload.get('runtime_controls',[]),payload.get('side_road_origin',{}).get('stage'),
        profile.java_version,payload.get('known_dependencies',[]))
    maximum=profile.max_agent_task_retries
    call=model_call or AdkExecutor(profile).execute
    settings=profile.model_copy(update=dict(staged_unit_conversion=False,side_road_conversion=False))
    requirements=payload.get('requirements',{})
    evidence=[source['identity'] for source in payload['sources']]
    from runtime.behavior_conversion.stage_tasks import StageTasks
    tasks=StageTasks(conn,config,profile,identity,revision,model_call,validator,label,implementation_attempt)
    ask=tasks.ask

    def contract(metadata):
        return UnitContract(unit_id=unit['unit_id'],apis=metadata['apis'],requirements=requirements,evidence_ids=evidence,
            dependency_units=[item['unit_id'] for item in payload.get('converted_dependency_apis',[])])

    retained_feedback=state.read(conn,config.run_id,identity,revision,'feedback').get('artifact_json')
    feedback=json.loads(retained_feedback) if retained_feedback else None
    while True:
        context={}
        # Production prompt excludes testing/binding/coverage templates and full bundle schemas.
        request={key:deepcopy(payload[key]) for key in ('selected_unit','unit','sources','runtime_controls',
            'converted_dependency_apis','known_dependencies','native_package','verified_baseline') if key in payload}
        if unit is payload:request['unit']=deepcopy(unit)
        attach_typed_boundary(request)
        request['typed_boundary_contract'].pop('accepted_native_apis',None)
        if feedback:request['implementation_feedback']=feedback
        phase=payload.get('side_road_origin',{}).get('stage')
        request['conversion_phase']=phase or 'native'
        prompt=IMPLEMENTATION
        if phase=='baseline':prompt+='\nTemporary internal original-like helper structure is allowed; the caller-facing boundary remains typed.'
        if phase=='simplify':prompt+='\nSimplify verified_baseline while preserving its public boundary APIs and behavior; remove framework plumbing.'
        def implementation_check(output):
            state.invalidate_readiness(conn,config.run_id,identity,revision,'implementation')
            if any(not f.path.startswith('src/main/java/') for f in output.files):
                raise ValueError('Implementation stage returns production Java only')
            preliminary=NativeUnitBundle(files=output.files,unresolved_questions=output.unresolved_questions,evidence_ids=evidence)
            validate_bundle(preliminary,evidence_ids=evidence)
            tool_hash=file_digest(jar)
            from models.native_unit_bundle import NativeSourceFile
            prerequisite_files=[NativeSourceFile.model_validate(file) for item in payload.get('converted_dependency_apis',[])
                                for file in item['files']]
            metadata=inspect_native([*output.files,*prerequisite_files],jar,payload['sources'])
            from runtime.behavior_conversion.java_api_types import public_api_types
            owned={name for file in output.files for name in public_api_types(file.content)}
            metadata['owned_types']=sorted(owned)
            metadata['apis']=[api for api in metadata['apis'] if api['type_name'] in owned]
            if file_digest(jar)!=tool_hash:raise VerificationIncomplete(dict(stage='parser',issues=['Inspection tool changed']))
            from tools.behavior_verification.thin_path_binding import configured_fields
            metadata['context_keys'] += [dict(name=item['context_key'],source='configuration') for item in configured_fields(unit)]
            dependencies,unknown=resolve_dependencies(metadata,payload.get('known_dependencies',[]))
            if unknown:
                proposal_request=dict(unresolved_imports=unknown,known_dependencies=payload.get('known_dependencies',[]))
                def proposals(value):
                    _,remaining=resolve_dependencies(metadata,payload.get('known_dependencies',[]),
                        [p.model_dump(mode='json') for p in value.dependencies])
                    if remaining:raise ValueError('Unresolved imports remain: '+str(remaining))
                proposal=ask('dependencies',proposal_request,DEPENDENCIES,NativeDependencyProposal,proposals)
                dependencies,unknown=resolve_dependencies(metadata,payload.get('known_dependencies',[]),
                    [p.model_dump(mode='json') for p in proposal.dependencies])
            preliminary.unit_contract=contract(metadata);preliminary.dependencies=dependencies
            from runtime.behavior_conversion.verification_binding import SCALARS
            entry_names={'request_unformat':{'unformat','parse'},'response_format':{'format','serialize'},'configured_step':{'execute'}}
            entries=[(owner,m) for owner,t in metadata['types'].items() if owner in metadata['owned_types']
                     for m in t['methods'] if m['name'] in entry_names.get(unit['kind'],set())]
            interface_errors=[];typed_entries=0
            for owner,entry in entries:
                unsupported=[p['type'] for p in entry['parameters'] if p['type'] not in SCALARS and p['type'] not in metadata['types']]
                if unsupported:
                    interface_errors.append('Use scalar/native DTO boundary inputs; expose runtime settings through native configuration APIs. Unsupported: '+str(unsupported))
                    continue
                boundary_copy=preliminary.model_copy(deep=True)
                boundary_copy.unit_contract.apis=[api for api in preliminary.unit_contract.apis if api.type_name==owner]
                from runtime.behavior_conversion.method_contracts import _signature,java_type_resolver
                source=next(file.content for file in output.files if owner in public_api_types(file.content))
                resolve=java_type_resolver(source,metadata['types'])
                selection={(owner,sig) for api in boundary_copy.unit_contract.apis for text in api.method_signatures
                           if (sig:=_signature(text,resolve)) and sig[0]==entry['name'] and
                           sig[2]==tuple(p['type'] for p in entry['parameters']) and sig[3]==(entry.get('static')=='true')}
                policy=dict(payload);attach_typed_boundary(policy)
                try:
                    validate_typed_boundary(boundary_copy,policy.get('typed_boundary_contract'),selection=selection)
                    typed_entries+=1
                except TypedBoundaryError as error:
                    interface_errors.append(str(error))
            if entries and not typed_entries:
                raise TypedBoundaryError('No supported typed formatter/step entry: '+'; '.join(interface_errors))
            receipt=validator.compile_implementation(preliminary)
            if not receipt.get('build_passed'):raise VerificationIncomplete(dict(stage='compile',issues=['No successful compile receipt']))
            proof=dict(production_hash=stable_id(output.model_dump(mode='json')),validation=receipt,
                       dependencies=[d.model_dump(mode='json') for d in dependencies],acceptance=False)
            state.retain(conn,config.run_id,identity,revision,'compile',proof,stable_id(proof))
            context.update(metadata=metadata,dependencies=dependencies,production=output)
        production=ask('implementation',request,prompt,NativeImplementation,implementation_check)
        metadata=context['metadata'];dependencies=context['dependencies']
        assembled=NativeUnitBundle(files=production.files,dependencies=dependencies,evidence_ids=evidence,unit_contract=contract(metadata))
        controls=payload.get('runtime_controls',[])
        extra_types=[name for name in metadata['types'] if name not in metadata.get('owned_types',metadata['types'])]
        try:
            binding=build_binding(unit,metadata,controls)
            assembled.verification_binding=binding
            validate_binding(assembled,extra_types)
        except (BindingAmbiguous,VerificationFailure,ValueError) as ambiguity:
            mapping_request=dict(unit_id=unit['unit_id'],kind=unit['kind'],configuration_xml=unit.get('configuration_xml'),
                parsed_apis=metadata, runtime_controls=controls,ambiguity=str(ambiguity),
                settings_example={'original.Owner.configure':{'class':'native.Settings','method':'configure'}})
            def mapping_check(value):
                assembled.verification_binding=value.binding
                validate_binding(assembled,extra_types)
                validate_parsed_binding(value.binding,metadata,controls)
            binding=ask('mapping',mapping_request,MAPPING,NativeMappingSelection,mapping_check).binding
        assembled.verification_binding=binding
        # Temporary internal helpers are not exported boundary APIs.
        exported={binding.owner_type}
        def export(value):
            if value.type_name in metadata['types']:exported.add(value.type_name)
            for child in [*value.arguments,*value.properties.values()]:export(child)
        for argument in binding.arguments:export(argument)
        entry=next(m for m in metadata['types'][binding.owner_type]['methods'] if m['name']==binding.method_name and
            [p['type'] for p in m['parameters']]==[a.type_name for a in binding.arguments])
        if entry['returns'] in metadata['types']:exported.add(entry['returns'])
        assembled.unit_contract.apis=[api for api in assembled.unit_contract.apis if api.type_name in exported]
        typed=dict(payload);attach_typed_boundary(typed)
        try:
            validate_typed_boundary(assembled,typed.get('typed_boundary_contract'))
        except TypedBoundaryError as error:
            feedback=dict(stage='typed_boundary',error=str(error),previous_implementation=production.model_dump(mode='json'))
            state.retain(conn,config.run_id,identity,revision,'feedback',feedback,stable_id(feedback))
            continue
        from runtime.behavior_conversion.metadata_checklist import mapping_enabled,map_checklist
        if mapping_enabled(tasks,payload):
            mapped=map_checklist(tasks,payload,production,metadata)
            if mapped.get('checklist_answers'):
                from models.unit_checklist_answers import UnitChecklistAnswers
                assembled.checklist_answers=UnitChecklistAnswers.model_validate(mapped['checklist_answers'])
        from runtime.behavior_conversion.stage_readiness import prepare_metadata
        try:
            prepare_metadata(tasks,payload,production,metadata,assembled,
                lambda candidate: getattr(validator,'validate_metadata',lambda value:None)(candidate))
        except ImplementationInterfaceError as error:
            from runtime.behavior_conversion.frozen_implementation import refuse_production_change
            refuse_production_change(validator,error)
            feedback=dict(stage='implementation_interface',error=str(error),previous_implementation=production.model_dump(mode='json'))
            state.retain(conn,config.run_id,identity,revision,'feedback',feedback,stable_id(feedback))
            continue
        binding=assembled.verification_binding
        testing_request=dict(original_unit=deepcopy(unit),original_sources=deepcopy(payload['sources']),
            production_files=[f.model_dump(mode='json') for f in production.files],parsed_apis=metadata,
            selected_boundary=test_scope(unit,binding,controls),
            requirements=requirements,testing_contract=payload.get('testing_contract'),
            known_dependencies=payload.get('known_dependencies',[]))
        if not testing_request.get('testing_contract'):testing_request.pop('testing_contract',None)
        eligibility=stable_id(revision,requirements,payload.get('testing_contract'),
            profile.unit_verification_policy.model_dump(mode='json'),profile.allowed_ibm_classes,TESTS)
        test_context=dict(revision=revision,eligibility_hash=eligibility,unit_id=unit['unit_id'],
            source_hash=stable_id(payload['sources']),configuration_hash=stable_id(unit.get('configuration_xml'),unit.get('effective_configuration')),
            production_hash=stable_id(production.model_dump(mode='json')),selected_boundary=testing_request['selected_boundary'],
            binding=binding.model_dump(mode='json'))
        def test_check(value):
            state.invalidate_readiness(conn,config.run_id,identity,revision,'tests')
            if value.unresolved_questions:raise ValueError('Unresolved test behavior: '+str(value.unresolved_questions))
            if any(not f.path.startswith('src/test/java/') for f in value.files):raise ValueError('Test stage cannot change production code')
            assembled.files=[*production.files,*value.files];assembled.coverage=value.coverage
            test_metadata=inspect_native(value.files,jar)
            validate_test_scope(test_metadata,testing_request['selected_boundary'])
            test_metadata['types']={**metadata['types'],**test_metadata['types']}
            test_dependencies,unknown=resolve_dependencies(test_metadata,payload.get('known_dependencies',[]),
                [p.model_dump(mode='json') for p in dependencies])
            if unknown:raise ValueError('Tests must use supplied libraries/native APIs: '+str(unknown))
            pins={(d.group_id,d.artifact_id):d for d in [*dependencies,*test_dependencies]}
            assembled.dependencies=list(pins.values())
            validate_bundle(assembled,assembled.unit_contract.apis,requirements,evidence)
            if payload.get('testing_contract'):validate_testing_contract(assembled,payload['testing_contract'])
            previous_receipt=getattr(validator,'last',None)
            outcome=None
            try:
                from runtime.behavior_conversion.stage_readiness import testing_gate
                with testing_gate(tasks,assembled):outcome=validator(assembled,cached=False)
            except VerificationFailure as error:
                if error.verification_feedback.get('stage')=='thin_path_boundary':
                    raise ImplementationCorrection(error) from error
                raise
            finally:
                latest=getattr(validator,'last',None)
                receipt=outcome if isinstance(outcome,dict) else latest if latest is not previous_receipt else None
                if receipt:
                    state.retain_passing_tests(conn,config.run_id,identity,revision,value.model_dump(mode='json'),
                        test_context,receipt.get('build_validation'))
        try:
            retained=state.passing_tests(conn,config.run_id,identity,revision,eligibility)
            reused=False
            if retained:
                try:
                    if retained['context']['selected_boundary']!=test_context['selected_boundary']:
                        raise ValueError('Selected API changed; adapt retained tests to the current selected boundary without weakening expectations')
                    test_check(NativeTestBundle.model_validate(retained['tests']))
                    reused=True
                except (VerificationFailure,ImplementationCorrection):
                    raise
                except (ValueError,CompilerCorrectionError,TestCorrectionError) as error:
                    correction=getattr(error,'compiler_correction',None)
                    if correction and any(not d.get('file','').startswith('src/test/java/') for d in correction.get('diagnostics',[])):
                        raise
                    testing_request.update(retained_test_bundle=retained['tests'],retained_test_revalidation_error=str(error))
                    if correction:testing_request['compiler_correction']=correction
                    if getattr(error,'test_correction',None):testing_request['test_correction']=error.test_correction
                    if state.read(conn,config.run_id,identity,revision,'tests')['attempts']>=maximum:
                        raise ValueError('Staged tests attempt budget exhausted after retained test revalidation: '+str(error)) from error
            if not reused:ask('tests',testing_request,TESTS,NativeTestBundle,test_check)
            fingerprint=stable_id(revision,assembled.model_dump(mode='json'))
            state.retain(conn,config.run_id,identity,revision,'complete',assembled.model_dump(mode='json'),fingerprint)
            from tools.state_store_tools.behavior_units import save
            save(conn,config.run_id,category,identity,fingerprint,assembled.model_dump(mode='json'))
            return assembled,fingerprint
        except VerificationIncomplete:
            raise
        except Exception as error:
            # Concrete boundary differences or production compiler failures require implementation repair.
            if not isinstance(error,(ImplementationCorrection,VerificationFailure)) and not getattr(error,'compiler_correction',None):raise
            details=getattr(error,'verification_feedback',None) or getattr(error,'compiler_correction',None)
            if isinstance(error,VerificationFailure) and details.get('stage')!='thin_path_boundary':raise
            feedback=dict(error=str(error),details=details,previous_implementation=production.model_dump(mode='json'))
            state.retain(conn,config.run_id,identity,revision,'feedback',feedback,stable_id(feedback))
