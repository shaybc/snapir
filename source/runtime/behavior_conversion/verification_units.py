"""Scoped unit generation accepts technical evidence; AI review is no longer a gate."""
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.review import BehaviorReview
from runtime.behavior_conversion.verification_request import attach_verification, CHECKLIST_INSTRUCTION
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession, verification_session
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.behavior_conversion.verification_state import record_verification


def generate_verified_unit(conn, config, profile, identity, instruction, payload, validator, model_call=None, label='', *, bundle_generator=None):
    """Reuse the existing durable generation/retry mechanism, replacing only its unit check ladder."""
    from runtime.behavior_conversion.verification_mode import executable_mode,conversion_mode,policy_payload,facts_disabled,conversion_version
    request, boundary, original = attach_verification(payload,collect_facts=not facts_disabled(profile))
    if executable_mode(profile) or conversion_mode(profile):
        request['executable_verification']=policy_payload(profile)
        request['verification_version']=conversion_version(profile) if conversion_mode(profile) else 'executable-boundary-v1'
    from tools.behavior_verification.boundary_contracts import digest
    policy = profile.unit_verification_policy
    authorizations = [item for item in profile.unit_verification_authorizations if item.unit_id == identity]
    request['verification_policy_hash'] = digest(policy.model_dump(mode='json'))
    request['verification_authorizations_hash'] = digest([item.model_dump(mode='json') for item in authorizations])
    request['approved_exclusions'] = [dict(approval_id=item.approval_id, checklist_id=item.checklist_id,
        candidate_hash=item.candidate_hash) for item in authorizations]
    extra_types = [api['type_name'] for dependency in payload.get('converted_dependency_apis', [])
                   for api in dependency.get('planned_apis', [])]
    session = UnitVerificationSession(config, original, boundary, extra_types=extra_types, policy=policy, authorizations=authorizations,
                                      mutation_settings=profile.unit_mutation_testing,executable_settings=profile.executable_verification)
    try:
        with verification_session(session):
            if bundle_generator is None:
                checklist_instruction = (CHECKLIST_INSTRUCTION.split('Return verification_binding',1)[0] +
                    'Do not return comparison bindings, adapters, invocation recipes or comparison inputs; equivalence is not assessed.'
                    if conversion_mode(profile) else CHECKLIST_INSTRUCTION)
                if facts_disabled(profile):
                    checklist_instruction = 'Experimental test only: do not create or map checklist facts. Preserve source behavior, configuration, APIs and build/JUnit requirements. This is not normal conversion acceptance.'
                bundle, fingerprint = generate(conn, config, profile, 'unit', identity,
                    instruction + ('\nPreserve the selected executable boundary; no AI checklist citations are required.' if executable_mode(profile) else '\n' + checklist_instruction), request, NativeUnitBundle, validator, model_call, label)
            else:
                bundle, fingerprint = bundle_generator(request)
    except ValueError as error:
        if 'context budget' in str(error):
            raise VerificationIncomplete(dict(stage='request_budget', errors=[str(error)])) from error
        raise
    if session.last_report is None:
        raise VerificationIncomplete(dict(stage='boundary', errors=['No pre-publication boundary evidence was produced']))
    receipt = record_verification(conn, config, identity, 'accepted', session.last_report)
    from runtime.behavior_conversion.verification_test_strength import measure_accepted_unit
    from tools.state_store_tools.behavior_units import save
    if not conversion_mode(profile):
        try:
            strength = measure_accepted_unit(session, profile, receipt)
            save(conn, config.run_id, 'unit_test_strength', identity, digest(strength), strength, strength['status'])
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Advisory test-strength reporting failed for accepted unit %s', identity)
    if getattr(profile, 'behavior_triage_enabled', False):
        from runtime.behavior_conversion.review import review_behavior
        import logging
        try:
            review_behavior(conn, config, profile, identity, dict(unit=request,
                sources=[dict(identity=source['identity'], content_hash=source['fragment_hash'], content=source['content'])
                         for source in request['slice_sources']],
                generated_bundle=bundle.model_dump(mode='json'), technical_verification=session.last_report), model_call)
        except Exception as error:
            logging.getLogger(__name__).warning('Optional behavior triage could not finish for %s: %s', identity, error)
    review = BehaviorReview(approved=True)
    return bundle, fingerprint, review, receipt['candidate_hash']
