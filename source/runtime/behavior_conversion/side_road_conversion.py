"""Recover a failed whole unit through an isolated baseline and checked simplification."""
from copy import deepcopy
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.side_road_state import load, reserve_attempt, record
from runtime.behavior_conversion.side_road_policy import side_road_stage
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.behavior_conversion.bundle_output import validate_bundle
from agents.behavior_conversion.side_road_instructions import BASELINE, SIMPLIFY


def recover_unit(conn, config, profile, category, identity, payload, schema, validator, model_call, failure,
                 *, generate_stage, require_coverage=True):
    """Use existing generation/build/comparison flows; never accept an unsimplified fallback."""
    if not callable(getattr(validator, 'side_road_validate', None)):
        raise VerificationIncomplete(dict(stage='side_road',issues=[
            'This validator has no isolated whole-unit baseline comparison adapter; normal gates remain required.']))
    if not payload.get('sources') or payload.get('source_summaries'):
        raise VerificationIncomplete(dict(stage='side_road',issues=['Complete original implementing sources are required']))
    # Exclude candidate/correction text: a rewritten request must not reset stage budgets.
    original = {key:value for key,value in payload.items() if key not in {
        'previous_model_response','correction_feedback','verification_feedback','saved_candidate'}}
    revision = stable_id('side-road-v1', {key:original.get(key) for key in (
        'unit_id','kind','fingerprint','selected_unit','unit','sources','configuration_xml',
        'effective_configuration','referenced_definitions','runtime_controls',
        'converted_dependency_apis','managed_dependencies','testing_contract')},
        {key:profile.model_dump(mode='json')[key] for key in ('java_version','behavior_context_chars',
         'allowed_ibm_classes','allowed_ibm_artifacts','unit_verification_policy')})
    state = load(conn,config.run_id,identity,revision)
    from runtime.model_execution.adk_executor import AdkExecutor
    call = model_call or AdkExecutor(profile).execute
    baseline = schema.model_validate_json(state['baseline_json']) if state['baseline_json'] else None
    baseline_verified = False
    latest_receipt = None

    def validate(candidate, stage, cached=False):
        nonlocal latest_receipt
        if candidate.unit_contract is None:
            raise ValueError('Side-road candidate must declare its typed public unit contract')
        if any(item.group_id.lower().startswith('com.ibm') or
               any(name.startswith('com.ibm.') for name in item.required_classes) for item in candidate.dependencies):
            raise ValueError('Side-road candidates cannot retain IBM runtime dependencies')
        if stage=='simplify' and (candidate.unit_contract.apis != baseline.unit_contract.apis or
                                 candidate.verification_binding != baseline.verification_binding):
            raise ValueError('Simplification must preserve verified public APIs and verification binding')
        with side_road_stage(stage):
            validate_bundle(candidate, candidate.unit_contract.apis if candidate.unit_contract else (),
                payload.get('requirements',{}), [*payload.get('evidence_ids',[]),
                    *[source['identity'] for source in payload['sources']]], ())
            receipt = validator.side_road_validate(candidate,stage)
        build = receipt.get('build_validation',{})
        if receipt.get('status')!='matched_observed_cases' or not receipt.get('observed_cases') or not (
                build.get('build_passed') and build.get('tests_passed')):
            raise VerificationIncomplete(dict(stage='side_road',issues=['Missing verified build/test/comparison receipt']))
        latest_receipt = receipt
        return receipt

    def stage_call(stage, instruction, request, maximum):
        current = load(conn,config.run_id,identity,revision)
        remaining = maximum-current[stage+'_attempts']
        def counted_call(instruction,encoded):
            reserve_attempt(conn,config.run_id,identity,revision,stage,maximum)
            return call(instruction,encoded)
        def checked(candidate,cached=False):
            checked.last=validate(candidate,stage,cached)
            return checked.last
        settings = profile.model_copy(update=dict(max_agent_task_retries=max(1,remaining),side_road_conversion=False))
        if profile.staged_unit_conversion:
            from runtime.behavior_conversion.generation import generate as staged_task
            from runtime.behavior_conversion.stage_scope import authorized_recovery,verify_parent
            settings.max_agent_task_retries=maximum
            checked.compile_implementation=validator.compile_implementation
            checked.fresh=getattr(validator,'fresh',lambda:None)
            checked.tool=getattr(validator,'tool',None)
            checked.stage_prerequisites=getattr(validator,'stage_prerequisites',{})
            checked.implementation_attempt=lambda:reserve_attempt(conn,config.run_id,identity,revision,stage,maximum)
            settings.staged_unit_conversion=True
            with side_road_stage(stage),authorized_recovery(conn,config,settings,'side_road_'+stage,identity+':'+revision,
                    lambda:verify_parent(conn,config,profile,category,identity,payload)):
                return staged_task(conn,config,settings,'side_road_'+stage,identity+':'+revision,instruction,request,
                    schema,validator=checked,model_call=call,label='Side road '+stage+': '+identity,require_coverage=require_coverage)
        # A distinct task category records stage attempts without accepting the parent unit.
        with side_road_stage(stage):
            return generate_stage(conn,config,settings,'side_road_'+stage,identity+':'+revision,
                instruction,request,schema,validator=checked,model_call=counted_call,
                label='Side road '+stage+': '+identity,require_coverage=require_coverage)

    try:
        if baseline is None:
            request = deepcopy(original)
            request['side_road_origin'] = dict(category=category,identity=identity,revision=revision,
                                              failure=str(failure),stage='baseline')
            baseline,_ = stage_call('baseline',BASELINE,request,profile.side_road_baseline_attempts)
            record(conn,config.run_id,identity,revision,'baseline_verified',baseline=baseline,receipt=latest_receipt)
        else:
            # Rebuild and compare again; persisted flags alone cannot justify reuse.
            validate(baseline,'baseline',True)
        baseline_verified = True
        request = deepcopy(original)
        request.update(verified_baseline=baseline.model_dump(mode='json'),
            side_road_origin=dict(category=category,identity=identity,revision=revision,stage='simplify'))
        output,fingerprint = stage_call('simplify',SIMPLIFY,request,profile.side_road_simplify_attempts)
        # Return to ordinary parent validation only after strict simplified validation succeeds.
        validator(output,cached=False)
        from tools.state_store_tools.behavior_units import save
        save(conn,config.run_id,category,identity,fingerprint,output.model_dump(mode='json'))
        record(conn,config.run_id,identity,revision,'simplified_verified')
        return output,fingerprint
    except Exception as error:
        status = 'baseline_available' if baseline_verified else 'baseline_retained_unverified' if baseline else 'blocked'
        record(conn,config.run_id,identity,revision,status,error=str(error))
        raise
