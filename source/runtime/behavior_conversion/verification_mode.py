"""Select an explicit verification policy without altering legacy receipt meanings."""


def executable_mode(profile):
    """Only the explicitly selected alternative may omit AI checklist citations."""
    return profile.executable_verification.mode=='executable_boundary_v1'


def conversion_mode(profile):
    """Conversion readiness requires mappings/build/JUnit, without paired execution."""
    return getattr(getattr(profile,'executable_verification',None),'mode',None) in {'conversion_checklist_v1','test_based_v1'}


def test_based_mode(profile_or_settings):
    """Identify supported fact-free conversion without promoting historical experiments."""
    settings = getattr(profile_or_settings, 'executable_verification', profile_or_settings)
    return getattr(settings, 'mode', None) == 'test_based_v1'


def experimental_mode(profile_or_settings):
    """Preserve the explicit historical facts-disabled experiment boundary."""
    settings = getattr(profile_or_settings, 'executable_verification', profile_or_settings)
    return getattr(settings, 'mode', None) == 'conversion_checklist_v1' and bool(getattr(settings, 'experimental_disable_facts', False))


def facts_disabled(profile_or_settings):
    """Omit facts only for supported test-based conversion or explicit experiments."""
    settings = getattr(profile_or_settings, 'executable_verification', profile_or_settings)
    return test_based_mode(settings) or experimental_mode(settings)


def conversion_version(profile):
    """Experimental build results cannot satisfy normal conversion-ready receipts."""
    if test_based_mode(profile):
        return 'test-based-conversion-v1'
    return 'conversion-facts-experiment-v1' if experimental_mode(profile) else 'conversion-checklist-v1'


def policy_payload(profile):
    """Bind requests, cached stages and reuse to the complete verification policy."""
    data=profile.executable_verification.model_dump(mode='json')
    data.pop('experimental_disable_facts',None)
    if test_based_mode(profile):
        return dict(mode='test_based_v1', schema_version='test-based-conversion-v1',
                    equivalence='not_assessed', fact_collection=False, fact_validation_blocking=False,
                    checklist_mapping='disabled', executed_tests_required=True)
    if conversion_mode(profile):
        if facts_disabled(profile):
            return dict(mode='conversion_checklist_v1', schema_version='conversion-facts-experiment-v1',
                        experimental_only=True, equivalence='not_assessed', checklist_mapping='disabled_for_test',
                        fact_collection=False, fact_validation_blocking=False)
        return dict(mode='conversion_checklist_v1',schema_version='conversion-checklist-policy-v1',
            equivalence='not_assessed',checklist_mapping='bounded-required-v1')
    if executable_mode(profile):
        import hashlib
        import json
        # Independent verification inputs are retained on the trusted side, not
        # exposed as examples the implementation model could memorize.
        for name in ('fixtures','replays'):
            value=data.pop(name)
            data[name+'_hash']=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
        from runtime.behavior_conversion.deterministic_contracts import VERSION
        data['contract_derivation_version']=VERSION
        from runtime.behavior_conversion.executable_adapters import VERSION as ADAPTER_VERSION
        data['adapter_version']=ADAPTER_VERSION
        from tools.behavior_verification.structured_inputs import VERSION as INPUT_VERSION
        data['input_generation_version']=INPUT_VERSION
        from tools.behavior_verification.independent_comparison import VERSION as COMPARISON_VERSION
        data['comparison_policy']=COMPARISON_VERSION
        from tools.behavior_verification.coverage_expansion import VERSION as COVERAGE_VERSION
        data['coverage_expansion_version']=COVERAGE_VERSION
        from tools.behavior_verification.comparison_mutations import VERSION as MUTATION_VERSION
        data['comparison_mutation_version']=MUTATION_VERSION
        from runtime.behavior_conversion.failure_routing import VERSION as ROUTING_VERSION
        data['failure_routing_version']=ROUTING_VERSION
    return data
