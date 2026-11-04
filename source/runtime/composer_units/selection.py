"""Select a single configuration using existing qualified Mapper evidence."""
from copy import deepcopy
from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess
from tools.composer_mapper_tools.channel_note_parser import parse_channel_note
from tools.conversion_tools.scoped_closure.formats import FormatResolver
from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence
from tools.behavior_verification.boundary_contracts import digest


def select_format(conn,run_id,channel,operation,definition,root):
    """Read a qualified format closure without creating or changing conversion state."""
    access=ScopedVaultAccess(conn,run_id);context=access.operation(channel,operation)
    evidence=SourceEvidence(root);issues=[]
    channel_evidence=access.channel_evidence(context)
    mappings={tag:owner for tag,owner,_ in parse_channel_note(channel_evidence['markdown'],channel)}
    resolver=FormatResolver(access,context,evidence,mappings,lambda entity,detail,*_:issues.append(entity+': '+detail))
    identity=resolver.resolve_format(definition)
    if issues:raise ValueError('; '.join(issues))
    node=resolver.nodes[identity].model_dump(mode='json')
    return dict(unit_id=identity,fingerprint=digest(node),channel=channel,operation_identity=context.operation_identity,kind='response_format',
        effective_configuration=node,configuration_xml='',referenced_definitions=[n.model_dump(mode='json') for key,n in resolver.nodes.items() if key!=identity],
        configuration_revisions={str(evidence.path(p)):h for p,h in evidence.used.items()},mapping_evidence=channel_evidence,sources=[])


def standalone(owner,attributes=None):
    """Build an explicitly selected basic element; dependencies are discovered later."""
    node=dict(java_class=owner,attributes=attributes or {},children=[],decorators=[])
    return dict(unit_id='standalone-'+digest(node)[:24],fingerprint=digest(node),operation_identity='standalone',kind='response_format',
        effective_configuration=node,configuration_xml='',referenced_definitions=[],sources=[])


def select_element(unit,selector):
    """Select an exact configured occurrence, including a standalone decorator."""
    matches=[]
    def visit(node):
        if selector in [node.get('occurrence_id'),node.get('source_selector')]:matches.append(node)
        for child in [*node.get('children',[]),*node.get('decorators',[])]:visit(child)
    for node in [unit['effective_configuration'],*unit.get('referenced_definitions',[])]:visit(node)
    if len(matches)!=1:raise ValueError('Configured element selector is missing or ambiguous')
    result=deepcopy(unit);result['effective_configuration']=deepcopy(matches[0]);result['unit_id']=matches[0].get('occurrence_id',selector)
    return result
