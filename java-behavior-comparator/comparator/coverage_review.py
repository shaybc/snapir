"""Reverse coverage and bounded interaction selection expose omissions and invented behavior."""
from comparator.stage_contracts import BASE, text, references

PROMPT=BASE+"""Review ONE generated member against the listed original behaviors and their source evidence.
Classify it as accounted (name matching behavior IDs), scaffolding (representation/API machinery
without a new business effect), uncertain, or extra_suspected. A suspicion is not a confirmed defect.
This is one catalog page; do not infer absence from missing behaviors on this page.
Return {"status":"accounted|scaffolding|uncertain|extra_suspected","behaviors":[],"reason":"..."}.
"""


def reverse(tasks,evidence,identity,behaviors,original,generated):
    """Require every generated scoped member to receive a source-based accounting."""
    size=tasks.settings['catalog_page_size'];last=None
    pages=[behaviors[start:start+size] for start in range(0,len(behaviors),size)] or [[]]
    for page in pages:
        ids={b['id'] for b in page}
        def validate(value):
            if value.get('status') not in {'accounted','scaffolding','uncertain','extra_suspected'}: raise ValueError('Invalid coverage status')
            references(value,'behaviors',ids,required=value['status']=='accounted');text(value,'reason')
        value=tasks.call('coverage',PROMPT,dict(generated_evidence=evidence.capsule([identity],generated),
            original_behaviors=page,original_evidence=evidence.capsule(sorted({b['source'] for b in page}),original)),
            validate,evidence.references(original)|evidence.references(generated))
        if value['status'] in {'accounted','scaffolding'}: return value
        last=value
    return last


def interaction_pairs(behaviors,scope):
    """Select related behaviors by shared source member, direct calls, or declared state access."""
    for index,first in enumerate(behaviors):
        for second in behaviors[index+1:]:
            if first['source']==second['source'] or second['source'] in scope['edges'].get(first['source'],[])                 or first['source'] in scope['edges'].get(second['source'],[])                 or set(first['state_fields']) & set(second['state_fields']):
                yield first,second
