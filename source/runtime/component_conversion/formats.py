"""Retain configured format identity and ordered tree evidence beneath existing unit boundaries."""
from tools.state_store_tools.component_configuration import configuration_group


def format_group(plan, group):
    """Admit wrapper implementations and complete formats; configured nodes remain evidence only."""
    if len(group.members) == 1 and plan.components[group.members[0]].kind == 'format_composition': return True
    return all(plan.components[key].kind == 'java_implementation' and not (set(plan.components[key].roles) -
               {'utility','format_leaf','decorator','format_wrapper'}) for key in group.members)


def configured_format(plan, group, units):
    """Check the original whole-format identity and preserve its complete configured structure."""
    if len(group.members) != 1 or plan.components[group.members[0]].kind != 'format_composition': return None
    key=group.members[0]; node=plan.components[key]
    if len(node.unit_ids)!=1 or node.unit_ids[0] not in units: raise ValueError('Format requires one original selected unit')
    unit=units[node.unit_ids[0]]
    if unit['kind'] not in {'request_unformat','response_format'} or plan.unit_roots.get(unit['unit_id'])!=key or any(
            unit[name]!=node.provenance[field] for name,field in (('fingerprint','unit_fingerprint'),
            ('operation_identity','operation_identity'),('source_definition_id','source_definition_id'))):
        raise ValueError('Configured format source/identity changed')
    if node.configuration!=dict(direction=unit['kind'],configuration_xml=unit['configuration_xml']):
        raise ValueError('Configured format direction/XML changed')
    return {name:unit[name] for name in ('unit_id','kind','logical_id','fingerprint','operation_identity','occurrence_id',
        'source_definition_id','configuration_xml','effective_configuration','referenced_definitions')}


def format_source_bindings(plan, group, units):
    """Use the existing resolved format-body rule and qualified graph, never another source search."""
    configured=configured_format(plan,group,units)
    if configured is None: return {}
    from tools.behavior_verification.boundary_contracts import _format_entry
    name=_format_entry(configured); pending=list(plan.components[group.members[0]].dependencies); seen=set(); matches=[]
    while pending:
        key=pending.pop()
        if key in seen: continue
        seen.add(key); node=plan.components[key]
        if node.kind=='format_node': pending.extend(node.dependencies)
        elif node.kind=='java_implementation' and node.label==name: matches.append(key)
    if not matches:
        from tools.framework_boundaries.inventory import owner
        if owner(name): return {}
    if len(matches)!=1: raise ValueError('Format needs one qualified body implementation')
    return {group.members[0]:matches[0]}


def current_format_boundary(unit,boundaries):
    """Reject stale parser/source/configuration revisions before requesting composition."""
    from tools.behavior_verification.boundary_contracts import boundary_contract
    current=boundary_contract(unit); boundary=boundaries['boundaries'].get(unit['unit_id'])
    if boundary is None or any(boundary[name]!=getattr(current,name) for name in (
            'unit_id','unit_fingerprint','source_manifest_hash','configuration_hash')):
        raise ValueError('Format parser boundary no longer matches original source/configuration')
    return boundary


def native_format_prerequisites(plan, group):
    """Flatten only configuration edges; Java helper edges remain transitive build dependencies."""
    groups={item.group_id:item for item in plan.groups}; pending=list(group.dependencies); found=set(); seen=set()
    while pending:
        key=pending.pop()
        if key in seen: continue
        seen.add(key)
        if configuration_group(plan,groups[key]): pending.extend(groups[key].dependencies)
        else: found.add(key)
    return found
