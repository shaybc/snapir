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
    if 'entries' in scope:
        calls={(call['receiver_type'],call['method']) for call in metadata.get('calls',[])}
        if not calls.intersection(tuple(entry) for entry in scope['entries']):
            raise ValueError('Tests must invoke an actual configured native entry: '+str(scope['entries']))
        owners={owner for owner,_ in scope['entries']}
        invalid=[call for call in metadata.get('calls',[]) if call['receiver_type'] in owners and call['method'] in scope['opposite_methods']]
        if invalid:raise ValueError('Tests outside selected configured direction: '+str(invalid))
        for setting in scope.get('native_settings_apis',[]):
            if not any((entry['owner_type'],entry['method_name']) in calls for entry in setting['native_candidates']):
                raise ValueError('Tests must exercise the native runtime settings API: '+setting['original_target'])
        return
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


def conversion_test_scope(unit,inventory,files,settings=()):
    """Select parsed native entries for JUnit without constructing invocation recipes."""
    from runtime.behavior_conversion.java_api_types import public_api_types
    owners={name for file in files for name in public_api_types(file.content)}
    expected={'configured_step':{'execute'},'request_unformat':{'unformat','parse'},'response_format':{'format','serialize'}}
    if unit.get('kind') not in expected:return None
    entries=sorted({(owner,m['name']) for owner in owners for m in inventory['types'].get(owner,{}).get('methods',[])
        if m['name'] in expected[unit['kind']]})
    if not entries:
        from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
        raise ImplementationInterfaceError('Missing configured native entry for '+unit['kind'])
    return dict(kind=unit['kind'],entries=[list(entry) for entry in entries],native_settings_apis=list(settings),
        opposite_methods={'request_unformat':['format','serialize'],'response_format':['unformat','parse']}.get(unit['kind'],[]))
