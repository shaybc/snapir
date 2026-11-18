"""Extract one source member's observable behaviors and account for its indexed facts."""
from comparator.models import digest
from comparator.stage_contracts import BASE, text, references

PROMPT = BASE + """Identify original behavior in ONE member, using its enclosing fields and supplied callees.
Do not inspect or anticipate generated code. List conditions, returned results, exceptions and
context/state effects. Respect Java dispatch and caller responsibility; a helper is not necessarily
an independently invoked entry point. Account for every indexed fact of the primary member through
covered_facts or ignored_facts with a specific reason. Prefer a few coherent behaviors rather than
one per syntax node. Return:
{"behaviors":[{"description":"...","conditions":"...","result":"...",
"exceptions":"...","context_effects":"...","state_fields":[],"covered_facts":["fact id"]}],
"ignored_facts":[{"id":"fact id","reason":"..."}],"no_behavior_reason":"only when behaviors is empty"}.
state_fields may name only provided fields/variables; use [] for stateless behavior.
"""


def inventory(tasks, evidence, identity, scope):
    """Return deterministic behavior IDs with validated source coverage."""
    chunk=evidence.chunks[identity];capsule=evidence.capsule([identity],scope)
    facts={fact['id'] for fact in chunk['facts']}
    fields=set(chunk['variables']) | {key for item in capsule.values()
        for key in evidence.classes.get(item['side']+'::'+item['owner'],{}).get('fields',{})}
    def validate(value):
        if not isinstance(value.get('behaviors'),list) or len(value['behaviors'])>24: raise ValueError('Return at most 24 behaviors')
        covered=set()
        for behavior in value['behaviors']:
            if not isinstance(behavior,dict): raise ValueError('Behavior must be an object')
            for key in ('description','conditions','result','exceptions','context_effects'): text(behavior,key)
            references(behavior,'covered_facts',facts);references(behavior,'state_fields',fields)
            covered.update(behavior['covered_facts'])
        ignored=value.get('ignored_facts')
        if not isinstance(ignored,list): raise ValueError('ignored_facts must list explained exclusions')
        for item in ignored:
            if not isinstance(item,dict) or item.get('id') not in facts: raise ValueError('Unknown ignored fact')
            text(item,'reason');covered.add(item['id'])
        if covered!=facts: raise ValueError('Every indexed primary-member fact needs behavior coverage or an explained exclusion')
        if facts and chunk['kind']!='type' and not value['behaviors']:
            raise ValueError('A member with indexed executable facts needs at least one behavior; do not erase its logic through exclusions')
        if not value['behaviors']: text(value,'no_behavior_reason')
    result=tasks.call('inventory',PROMPT,dict(primary=identity,evidence=capsule,state_fields=sorted(fields),
        related_scope_gaps=scope['gaps']),validate,evidence.references(scope))
    return [dict(behavior,id='behavior-'+digest([identity,index,behavior])[:20],source=identity)
            for index,behavior in enumerate(result['behaviors'])],result
