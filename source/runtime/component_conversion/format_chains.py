"""Assign reusable basic behavior and source-backed configured decorator compositions."""
import re
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from runtime.component_conversion.format_chain_sources import source_types,reachable_hooks,decorator_scope
from tools.conversion_tools.component_identity import FORMAT_CHAIN_POLICY_VERSION,FORMAT_COMPOSITION_POLICY_VERSION

VERSION=FORMAT_CHAIN_POLICY_VERSION
INSTRUCTION='''
Basic format and decorator classes implement their own value/attribute behavior only. They must
not maintain decorator lists or execute other decorators. Composition owns the configured chain.
Basic format APIs expose undecorated typed value operations, parameterized by their own settings.
Retain each basic element's own literals, validation, defaults, intrinsic encoding/decoding and
database behavior. Expose separate value and intrinsic codec APIs when composition must insert a
decorator between them. Composition owns configured wire structure, child wiring and the ordering
of those API calls; it must not decorate an already rendered element as though it were a field value.
Basic attribute decorators return typed attribute data, preserving actual runtime settings and conditions.
When the selected basic component has role decorator, that decorator is the conversion target;
other decorator sources remain evidence only. composition_obligations is an audit of duties owned
by complete composition, not additional basic-element checklist facts or basic entry points.
For each format_chains entry generate its exact class_name as a concrete typed Java class. Invoke
the accepted basic format and decorator APIs, never duplicate their algorithms. Preserve the
source hook's branch conditions, null/missing behavior and side-effect positions. Format value
decorators run forward; unformat removal runs in the source-proven order BEFORE basic value
unformatting. Extract the wire value before removal and render only after formatting/decoration.
Attribute decorators receive the final value and actual runtime context, produce XML attributes,
and never replace the value. Attach those attributes to this occurrence's element only. Do not
apply hooks absent from the original selected direction. Jackson serializers/deserializers must
invoke these concrete classes. Repeated identical configurations may share a class, but distinct
configuration/order/scope must not share one. Internal Java call order, variable names and call
excerpts are not metadata deliverables. Preserve the configured behavior and cover it with executed
tests; do not reshape legitimate Java merely to satisfy an internal-call description.
When reusing frozen basic APIs, distinguish the logical value operation from its intrinsic XML codec.
Use an accepted value/model API before attribute evaluation and the accepted rendering API afterward.
For unformat codecs, adapt the wire representation around the accepted API without losing empty
versus null, XML text escaping or absent-field semantics. Do not replace a basic API with copied logic.
Configuration/runtime inputs may enter through constructors or explicit methods. Preserve final
values and attribute results. Include JUnit coverage for ordering, value flow, runtime attributes,
missing/null/empty behavior and source-specific conditional invocation. All enabled whole-unit
checklist, source, typed API, settings, compilation and executed JUnit checks remain required.
For partitions, inherited_format_chain_ownership identifies already generated child occurrences.
Reuse the supplied child public APIs at their configured positions. Generate chain classes only
for occurrences not already owned by a child. Do not describe or re-create child internal calls.
'''


def chain_occurrences(tree,definitions):
    """Follow resolved references while retaining occurrence scope and stopping cycles."""
    definitions={item['definition_id']:item for item in definitions};seen=set()
    def visit(node):
        key=node.get('occurrence_id') or node.get('source_selector')
        if key in seen:return
        seen.add(key)
        for child in node.get('children',[]):visit(child)
        reference=node.get('reference_definition_id')
        if reference:
            if reference not in definitions:raise ValueError('Missing chain reference: '+reference)
            visit(definitions[reference])
    visit(tree)
    return seen


def checklist_chain_context(payload):
    """Explain composition ownership without duplicating source excerpts in bounded mapping requests."""
    if not payload.get('format_chain_policy'):return {}
    return dict(format_chain_policy=payload['format_chain_policy'],
        fact_scope='basic_element' if payload.get('basic_format_behavior') else 'complete_unit',
        basic_format_behavior=payload.get('basic_format_behavior'),
        format_chains=[{key:chain[key] for key in ('occurrence_id','class_name','direction','attributes','operations','inactive_decorators')}
            for chain in payload.get('format_chains',[])])


def configured_chains(configured,sources,boundaries=None):
    """Derive chains from resolved occurrence ownership, original APIs and selected direction."""
    types=source_types(sources);result=[];seen=set()
    definitions={item['definition_id']:item for item in configured.get('referenced_definitions',[])}
    direction='unformat' if configured['kind']=='request_unformat' else 'format'
    from tools.framework_boundaries.composition import framework_occurrence
    def visit(node):
        occurrence=node.get('occurrence_id') or node.get('source_selector')
        if occurrence in seen:return
        seen.add(occurrence)
        decorators=node.get('decorators',[])
        if decorators and not framework_occurrence(configured, node, boundaries):
            owner=node.get('java_class');hooks=reachable_hooks(types,owner,direction)
            if boundaries:
                from tools.behavior_verification.format_lifecycle import basic_identity
                boundary = boundaries.get('basic_boundaries', {}).get(basic_identity(configured['unit_id'], owner))
                if boundary and boundary.get('format_lifecycle'):
                    from runtime.component_conversion.format_chain_sources import resolved_lifecycle_hooks
                    hooks.update(resolved_lifecycle_hooks(types,boundary,direction))
            if direction not in hooks:raise ValueError('Configured chain lacks original '+direction+' evidence: '+str(owner))
            value_hook='removeDecorators' if direction=='unformat' else 'applyDecorators'
            value=[];attributes=[]
            for decorator in decorators:
                scope=decorator_scope(types,decorator['java_class'])
                item=dict(decorator,scope=scope)
                if scope=='value' and value_hook in hooks:value.append(item)
                elif scope=='xml_attributes' and ('formatXmlAttributes' in hooks or any('formatXmlAttributes' in h['code'] for h in hooks.values())):attributes.append(item)
            if value:
                body=hooks[value_hook]['code']
                if direction=='unformat':
                    if not re.search(r'\.size\s*\(\s*\)\s*-\s*1',body) or not re.search(r'--\s*\w+|\w+\s*--',body):
                        raise ValueError('Original unformat decorator order is not proven reverse; explicit source analysis required')
                    value.reverse()
                elif not re.search(r'for\s*\([^:]+:\s*\w+\s*\)',body):
                    raise ValueError('Original format decorator order is not proven forward')
            operations=[dict(kind='basic',source_class=owner)]
            transforms=[dict(kind='value',source_class=d['java_class'],occurrence_id=d['occurrence_id'],attributes=d.get('attributes',{})) for d in value]
            operations=transforms+operations if direction=='unformat' else operations+transforms
            operations.extend(dict(kind='xml_attributes',source_class=d['java_class'],occurrence_id=d['occurrence_id'],attributes=d.get('attributes',{})) for d in attributes)
            identity=digest(dict(java_class=owner,attributes=node.get('attributes',{}),direction=direction,operations=operations))
            result.append(dict(occurrence_id=occurrence,class_name='FormatChain'+identity[:16],direction=direction,
                attributes=node.get('attributes',{}),operations=operations,
                source_hooks={name:{key:value for key,value in hook.items() if key!='code'} for name,hook in hooks.items()},
                inactive_decorators=[d['occurrence_id'] for d in decorators if d['occurrence_id'] not in {i.get('occurrence_id') for i in operations}]))
        for child in node.get('children',[]):visit(child)
        reference=node.get('reference_definition_id')
        if reference:
            if reference not in definitions:raise ValueError('Chain references missing format definition: '+reference)
            visit(definitions[reference])
    visit(configured['effective_configuration'])
    return result


def attach_format_chains(request,plan,group,units,*,boundaries=None):
    """Retain delegated obligations explicitly; complete units still check every original ID."""
    roles={role for key in group.members for role in plan.components[key].roles}
    if request.get('configured_format'):
        configured=request['configured_format'];unit=units[configured['unit_id']]
        request['format_chain_policy']=FORMAT_COMPOSITION_POLICY_VERSION
        request['format_chains']=configured_chains(configured,unit['sources'],boundaries)
        for chain in request['format_chains']:
            for operation in chain['operations']:
                matches=[key for key,node in plan.components.items() if node.kind=='java_implementation' and node.label==operation['source_class']]
                if len(matches)!=1:raise ValueError('Chain requires one independent basic component: '+operation['source_class'])
                operation['component_id']=matches[0]
            request['requirements']['chain-'+digest(chain['occurrence_id'])]='Exercise complete configured chain '+chain['occurrence_id']+' in '+chain['direction']+' order, including scope, conditional calls and runtime attributes'
    elif roles.intersection({'format_leaf','format_wrapper','decorator'}):
        request['format_chain_policy']=VERSION
        request['basic_format_behavior']=dict(chaining='owned_by_configured_composition',roles=sorted(roles))
        # The deterministic collector omits chaining facts in basic scope, not in complete formats.
        request.setdefault('composition_obligations',[])
