"""Select an explicit verification policy without altering legacy receipt meanings."""


def executable_mode(profile):
    """Only the explicitly selected alternative may omit AI checklist citations."""
    return profile.executable_verification.mode=='executable_boundary_v1'


def policy_payload(profile):
    """Bind requests, cached stages and reuse to the complete verification policy."""
    data=profile.executable_verification.model_dump(mode='json')
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
