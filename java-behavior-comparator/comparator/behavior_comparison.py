"""Compare one behavior or connected pair and independently recheck claimed differences."""
from comparator.stage_contracts import BASE, comparison_schema

PROMPT = BASE + """Compare only the supplied behavior(s) across the original and generated code.
Check trigger conditions, return value/type, exceptions, mutation/aliasing and context effects.
For a connected pair also check ordering and effects that cross their boundary. A direct native
map write may reproduce mutation of an original context-held object. Do not assume extra behavior
from different syntax. Report a difference only with a concrete distinguishing input and source
citations on both sides. Missing evidence means inconclusive, not a defect.
Return {"verdict":"consistent|difference|inconclusive","explanation":"...",
"original_outcome":"...","generated_outcome":"...","counterexample":"when different",
"suggested_action":"...","original_evidence":["chunk id"],"generated_evidence":["chunk id"]}.
"""


def compare(tasks,evidence,behaviors,candidates,original,generated,boundary):
    """Return a source-backed review; disagreements in the second pass stay inconclusive."""
    payload=dict(behaviors=behaviors,api_mapping=boundary,
        original_evidence=evidence.capsule(sorted({b['source'] for b in behaviors}),original),
        generated_evidence=evidence.capsule(candidates,generated),
        original_scope_gaps=original['gaps'],generated_scope_gaps=generated['gaps'])
    def validate(value): comparison_schema(value,evidence.references(original),evidence.references(generated))
    value=tasks.call('compare' if len(behaviors)==1 else 'interaction',PROMPT,payload,validate,
                     evidence.references(original)|evidence.references(generated))
    if value['verdict']=='difference':
        second=tasks.call('review_difference',PROMPT+'\nIndependently challenge the proposed difference. Trace the exact branches; do not merely agree.',
                         dict(payload,proposed_difference=value),validate,evidence.references(original)|evidence.references(generated))
        if second['verdict']!='difference':
            return dict(value,verdict='inconclusive',explanation='Difference review did not agree: '+second['explanation'])
        value=dict(second,adjudicated=True)
    return value
