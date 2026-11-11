"""Bind one configured step to its qualified implementation and occurrence-specific call evidence."""


def step_group(plan, group):
    """Admit reusable step implementations or one configured occurrence; never format composition."""
    nodes = [plan.components[key] for key in group.members]
    if len(nodes) == 1 and nodes[0].kind == 'configured_step':
        return True
    return all(node.kind == 'java_implementation' and
        not (set(node.roles) - {'utility', 'format_leaf', 'decorator', 'step_implementation'}) for node in nodes)


def source_bindings(plan, group):
    """Use the resolved original implementing class as evidence for an occurrence wrapper."""
    if len(group.members) != 1 or plan.components[group.members[0]].kind != 'configured_step':
        return {}
    key = group.members[0]; node = plan.components[key]
    candidates = [target for target in node.dependencies if plan.components[target].kind == 'java_implementation'
                  and plan.components[target].label == node.provenance.get('resolved_implementation')]
    if not candidates:
        from tools.framework_boundaries.inventory import owner
        if owner(node.provenance.get('resolved_implementation')): return {key: key}
    if len(candidates) != 1:
        raise ValueError('Configured step requires exactly one qualified implementing class')
    return {key: candidates[0]}


def default_step_mappings(plan):
    """Pass qualified channel defaults to existing parser analysis without searching for classes."""
    result = {}
    for node in plan.components.values():
        if node.kind != 'configured_step' or node.configuration.get('attributes', {}).get('implClass'):
            continue
        implementation = node.provenance.get('resolved_implementation')
        if not implementation: continue
        for operation in node.operations:
            mapping = result.setdefault(operation, {})
            key = node.configuration.get('implementation_mapping_key', 'opStep')
            if mapping.get(key, implementation) != implementation:
                raise ValueError('Operation has conflicting qualified default step implementations')
            mapping[key] = implementation
    return result


def configured_step(plan, group, units):
    """Retain exact source XML, occurrence configuration and resolved calls without sibling sources."""
    bindings = source_bindings(plan, group)
    if not bindings:
        return None
    key = group.members[0]; node = plan.components[key]
    if len(node.unit_ids) != 1 or node.unit_ids[0] not in units:
        raise ValueError('Configured step must belong to one selected original unit')
    unit = units[node.unit_ids[0]]
    if unit['kind'] != 'configured_step' or unit['effective_configuration'] != node.configuration:
        raise ValueError('Configured step occurrence disagrees with the source plan')
    if plan.unit_roots.get(unit['unit_id']) != key or any(unit[name] != node.provenance[field] for name,field in (
            ('fingerprint','unit_fingerprint'),('operation_identity','operation_identity'),('source_definition_id','source_definition_id'),
            ('occurrence_id','source_definition_id'))):
        raise ValueError('Configured step source/occurrence identity changed')
    result = {name: unit[name] for name in ('unit_id', 'kind', 'logical_id', 'fingerprint', 'operation_identity',
        'occurrence_id', 'source_definition_id', 'configuration_xml', 'effective_configuration')}
    result['consumers'] = list(unit.get('consumers', node.operations))
    result['resolved_implementation'] = node.provenance['resolved_implementation'] if bindings[key]==key else plan.components[bindings[key]].label
    result['operation_calls'] = list(unit.get('operation_calls', []))
    result['service_connections'] = list(unit.get('service_connections', []))
    for call in result['operation_calls']:
        if call.get('occurrence_id') != unit['occurrence_id'] or not call.get('callee'):
            raise ValueError('Operation call must target this exact step occurrence')
        contract = call.get('service_contract') or {}
        if not all(contract.get(name) for name in ('fingerprint', 'method', 'path', 'base_url_property')):
            raise ValueError('Complex step is missing its resolved native operation contract')
    if any(record.get('issues') for record in result['service_connections']):
        raise ValueError('External step resource evidence is unresolved')
    return result


def verify_step_resources(conn, config, profile, step):
    """Use existing freshness checks for current target contracts and channel resource mappings."""
    if step is None: return
    from runtime.behavior_conversion.operation_calls import verify_operation_contracts
    from runtime.behavior_conversion.service_connection_freshness import verify_connection_sources
    verify_operation_contracts(conn, config, step['operation_calls'], profile)
    verify_connection_sources(config, profile, step['service_connections'])


def validate_step_candidate(bundle, request, dependency_files):
    """Require an integer entry contract and reuse the canonical native-client safeguards."""
    step = request.get('configured_unit')
    if step is None: return
    from runtime.behavior_conversion.method_contracts import _signature
    for contract in bundle.contracts.values():
        signatures = [_signature(method, lambda name:name.strip()) for api in contract.apis for method in api.method_signatures]
        if not any(signature and signature[:2] == ('execute','int') for signature in signatures):
            from models.native_unit_bundle import NativeSourceFile
            from runtime.behavior_conversion.native_metadata import inspect_native
            from runtime.behavior_conversion.interface_feedback import ImplementationInterfaceError
            files={**dependency_files,**{f.path:f.content for f in bundle.files if f.path.startswith('src/main/java/')}}
            inventory=inspect_native([NativeSourceFile(path=p,content=t) for p,t in files.items() if p.startswith('src/main/java/')])
            methods=[m for api in contract.apis for m in inventory['types'].get(api.type_name,{}).get('methods',[])]
            if not any(m['name']=='execute' and m.get('returns')=='int' for m in methods):
                raise ImplementationInterfaceError('Configured step implementation must expose an int execute entry method; metadata cannot add a missing method')
            raise ValueError('Configured step metadata must expose its existing int execute entry method, including inherited methods from parsed_apis')
    if step['operation_calls']:
        from models.native_unit_bundle import NativeUnitBundle, NativeSourceFile
        from runtime.behavior_conversion.operation_calls import validate_operation_clients
        files = [NativeSourceFile(path=path, content=content) for path, content in dependency_files.items()]
        validate_operation_clients(NativeUnitBundle(files=[*bundle.files, *files], unresolved_questions=bundle.unresolved_questions),
                                   step['operation_calls'])
