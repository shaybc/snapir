"""Review eligible interactions without spending pair allowances on missing mappings."""
from comparator.coverage_review import interaction_pairs
from comparator.behavior_comparison import compare
from comparator.models import Incomplete
from comparator.review_limits import LimitReached


def review(tasks,evidence,behaviors,mappings,mapping_causes,original,generated,boundary,pair,issues,results):
    """Keep mapped-pair ordering and cached payloads; incomplete prerequisites remain root causes."""
    eligible=[]
    stats=dict(target=pair,unmapped_behaviors=0,eligible_considered=0,attempted=0,reviewed=0,
               limit=tasks.settings['max_interaction_pairs'],limit_exhausted=False,deferred=False)
    for behavior in behaviors:
        if mappings.get(behavior['id']):
            eligible.append(behavior)
        else:
            stats['unmapped_behaviors']+=1
            issues.block_behavior(mapping_causes[behavior['id']])
    for first,second in interaction_pairs(eligible,original):
        stats['eligible_considered']+=1
        reference=first['id']+' / '+second['id']
        if stats['attempted']>=stats['limit']:
            issues.failure(LimitReached('max_interaction_pairs',stats['attempted'],stats['limit'],'interaction'),
                           reference=pair['original_class']+' -> '+pair['generated_class'])
            stats['limit_exhausted']=stats['deferred']=True
            break
        before=tasks.calls,len(tasks.cached_receipts)
        try:
            candidates=sorted(set(mappings[first['id']]+mappings[second['id']]))
            value=compare(tasks,evidence,[first,second],candidates,original,generated,boundary)
            if boundary['uncertainties'] and value['verdict']=='difference':
                value=dict(value,verdict='inconclusive',explanation='Input/API mapping is unresolved: '+value['explanation'])
            results.append(dict(value,behaviors=[first['id'],second['id']],target=pair))
            stats['attempted']+=1;stats['reviewed']+=1
        except Incomplete as error:
            # A rejected new call consumes no pair allowance; real attempts/cached partial checks do.
            if before!=(tasks.calls,len(tasks.cached_receipts)): stats['attempted']+=1
            issues.failure(error,stage='interaction',reference=reference)
            if isinstance(error,LimitReached) and error.setting in {'max_model_calls','max_run_seconds'}:
                stats['deferred']=True
                break
    return stats
