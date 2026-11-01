"""Describe selected test direction and reject parsed direct reverse-boundary calls."""


def test_scope(unit,binding,controls):
    """Send the real selected API rather than asking tests to cover every public helper."""
    return dict(kind=unit['kind'],owner_type=binding.owner_type,method_name=binding.method_name,
        argument_types=[a.type_name for a in binding.arguments],runtime_controls=controls,
        settings_bindings=binding.settings_bindings,
        opposite_methods={'response_format':['unformat'],'request_unformat':['format']}.get(unit['kind'],[]))


def validate_test_scope(metadata,scope):
    """Check selected direction and calls to the prepared native settings targets.

    These are narrow scope guards, not a call-graph proof. Unresolved receivers and other
    helper classes remain subject to compilation and the existing behavior checks.
    """
    invalid=[call for call in metadata.get('calls',[]) if call['receiver_type']==scope['owner_type']
             and call['method'] in scope['opposite_methods'] and call['method']!=scope['method_name']]
    if invalid:
        raise ValueError('Tests outside selected boundary; retain source-derived expectations, generate only '
                         +scope['owner_type']+'.'+scope['method_name']+' tests. Direct reverse calls: '+str(invalid))
    calls={(call['receiver_type'],call['method']) for call in metadata.get('calls',[])}
    missing=[target for target in scope.get('settings_bindings',{}).values()
             if (target['class'],target['method']) not in calls]
    if missing:
        raise ValueError('Tests must exercise the prepared native runtime settings APIs: '+str(missing))
