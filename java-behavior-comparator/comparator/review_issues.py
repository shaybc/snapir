"""Group incomplete review work by root cause while retaining affected evidence and dependent counts."""
from comparator.models import digest
from comparator.review_limits import LimitReached

ACTIONS = dict(source_gap='Supply the missing source/dependency bodies or resolve the indicated dispatch.',
    boundary_uncertainty='Clarify the original/native input, null and context mapping using source evidence.',
    unmapped_behavior='Identify and validate the generated counterpart, or confirm a missing implementation from source.',
    generated_coverage='Trace this generated behavior against the original source before changing code.',
    task_incomplete='Inspect the saved task request, response and source evidence; resolve the stated uncertainty.')


class ReviewIssues:
    """Keep one actionable root record instead of repeating it for every blocked downstream pair."""
    def __init__(self):
        self.details = []
        self.causes = {}

    def add(self, message, *, category='task_incomplete', stage='', reference='', source='', side='original'):
        """Record unresolved evidence without labelling it as a budget failure."""
        key = digest([category,str(message),reference if category=='unmapped_behavior' else ''])[:20]
        cause = self.causes.setdefault(key,dict(id='cause-'+key,category=category,message=str(message),
            suggested_action=ACTIONS[category],occurrences=0,affected=[],stages=[],
            **{side+'_evidence':[source] if source else []}))
        if source and source not in cause.setdefault(side+'_evidence',[]): cause[side+'_evidence'].append(source)
        return self._record(cause,stage,reference,str(message))

    def failure(self, error, *, stage='', reference='', source=''):
        """Distinguish exact limit failures from mapping/schema/evidence failures."""
        if not isinstance(error,LimitReached):
            return self.add(str(error),stage=stage,reference=reference,source=source)
        key = 'limit-'+error.setting
        if error.setting == 'max_model_attempts':
            key += '-'+digest([error.stage,error.detail])[:12]
        action = ('Inspect the saved response/error and correct its schema, citations or provider delivery.'
                  if error.setting == 'max_model_attempts' else
                  'Resume the same request/output with a larger '+error.setting+' or reduce the required work without discarding evidence.')
        cause = self.causes.setdefault(key,dict(id=key,category='limit_exhausted',message=str(error),
            suggested_action=action,occurrences=0,affected=[],stages=[],limit=error.record()))
        if error.used >= cause['limit']['used']:
            cause['limit'] = error.record()
        return self._record(cause,error.stage or stage,reference,str(error))

    def _record(self, cause, stage, reference, detail):
        self.details.append(dict(cause=cause['id'],stage=stage,reference=reference,message=detail))
        cause['occurrences'] += 1
        if stage and stage not in cause['stages']: cause['stages'].append(stage)
        if reference and reference not in cause['affected']: cause['affected'].append(reference)
        return cause['id']

    def block_behavior(self, cause_id):
        """Attribute omitted interactions to the missing prerequisite without enumerating dependent pairs."""
        for cause in self.causes.values():
            if cause['id'] == cause_id:
                cause['blocked_behaviors'] = cause.get('blocked_behaviors',0)+1

    def summary(self):
        """Produce stable, actionable remarks with limit failures first and no repeated pair messages."""
        result = []
        for cause in self.causes.values():
            value = dict(cause)
            if 'limit' in value:
                limit = value['limit']
                value['message'] = limit['setting']+' exhausted: '+str(limit['used'])+' used / '+str(limit['limit'])+' limit'
                if limit['detail']: value['message'] += '; '+limit['detail']
            if value['affected']: value['message'] += ' ('+str(len(value['affected']))+' affected review items)'
            if value.get('blocked_behaviors'): value['message'] += '; interactions involving '+str(value['blocked_behaviors'])+' unmapped behaviors were not attempted'
            result.append(value)
        return sorted(result,key=lambda item:(item.get('limit',{}).get('setting') not in
            {'max_model_calls','max_run_seconds','max_interaction_pairs'},item['category']!='limit_exhausted',item['id']))
