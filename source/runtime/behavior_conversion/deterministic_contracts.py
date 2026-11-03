"""Assign source-owned public APIs without asking a model to copy declarations or identities."""
import re
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.method_contracts import java_type_resolver
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete

VERSION='native-contract-derivation-v1'


INSTRUCTION='''Return only the supplied details schema for frozen compiled production code.
The application derives API declarations, ownership, identities, hashes, requirements and
known dependencies. Do not return contracts, unit_contract, api_types or api_members.
Describe only requested runtime/configuration semantics and actual invocation bindings.
Bindings must call existing methods; do not change production code, tests or expected outputs.
Leave verification_binding null when wiring needs the separate adapter task.
An ambiguous binding remains unresolved. No checklist mapping is requested.'''


def enabled(payload,schema):
    """Apply only to configured units and component contracts in the explicit new mode."""
    return (payload.get('executable_verification',{}).get('mode') in {'executable_boundary_v1','conversion_checklist_v1'}
        and ('contracts' in schema.model_fields or payload.get('kind') in
             {'request_unformat','response_format','configured_step'}))


def derive(value,payload,inventory,production):
    """Choose a unique owned entry and its public type closure; never guess SCC ownership."""
    data=value.model_dump(mode='json')
    expected=payload.get('expected_contract_fields',{})
    if 'component_details' in data and len(expected)!=1:
        raise VerificationIncomplete(dict(stage='contract_ownership',errors=[
            'Automatic ownership requires exactly one assigned component; multi-component ownership is not inferred']))
    owned={name for f in production.files for name in public_api_types(f.content)}
    apis={api['type_name']:api for api in inventory['apis'] if api['type_name'] in owned}
    binding=data.get('verification_binding') or {}
    root=binding.get('owner_type') or data.pop('entry_type',None)
    if root:
        if root not in apis:raise ValueError('Boundary binding owner must be a parsed, owned public type')
    elif 'component_details' in data:
        if not apis:raise ValueError('Assigned component has no parsed owned public API')
        # One source-bound assignment owns its complete generated artifact;
        # prerequisite sources were excluded above and cannot be re-exported.
        selection=dict(api_types=sorted(apis),api_members={})
        data['contracts']={next(iter(expected)):{**data.pop('component_details'),**selection}}
        return data
    elif len(apis)==1:root=next(iter(apis))
    else:
        raise VerificationIncomplete(dict(stage='contract_ownership',errors=[
            'No unique owned public entry type; an explicit selected boundary is required'],candidates=sorted(apis)))
    selected={root};pending=[root]
    while pending:
        owner=pending.pop()
        declarations=inventory['types'][owner]
        references=[m.get('returns','') for m in declarations['methods']]
        references.extend(p['type'] for m in [*declarations['methods'],*declarations['constructors']]
                          for p in m['parameters'])
        references.extend(p['type'] for p in declarations.get('parents',[]))
        source=next(f.content for f in production.files if owner in public_api_types(f.content))
        resolve=java_type_resolver(source,list(inventory['types']),type_variables=declarations.get('type_parameters',[]))
        # Invocation types are erased by the existing inspector. Preserve DTOs
        # inside generics using the parser's original signatures and import resolver.
        references.extend(resolve(token) for signature in apis[owner]['method_signatures']
                          for token in _generic_types(signature))
        text=' '.join(references)
        for name in sorted(apis):
            if name not in selected and re.search(r'(?<![\w$])'+re.escape(name)+r'(?![\w$])',text):
                selected.add(name);pending.append(name)
    selection=dict(api_types=sorted(selected),api_members={})
    if 'component_details' in data:
        data['contracts']={next(iter(expected)):{**data.pop('component_details'),**selection}}
    else:
        data['unit_contract']=selection
    return data


def _generic_types(signature):
    """Read only type-argument regions, excluding ordinary method/parameter names."""
    depth=0;content=[]
    for character in signature:
        if character=='<':depth+=1
        elif character=='>':
            depth-=1
            if depth==0:
                yield from re.findall(r'[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*',''.join(content))
                content=[]
        elif depth:content.append(character)
