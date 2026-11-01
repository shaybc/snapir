"""Bound deterministic coverage exploration without changing production or comparison policy."""
import time
from tools.behavior_verification.coverage_inputs import proposals,input_identity
from models.boundary_case import BoundaryCase

VERSION='bounded-coverage-expansion-v1'


class CoverageExpansion:
    """Keep one run's case, round, elapsed-time and no-progress limits explicit."""
    def __init__(self,unit,boundary,settings,legacy_binding,*,clock=time.monotonic):
        self.unit,self.boundary,self.settings,self.binding=unit,boundary,settings,legacy_binding
        self.clock=clock;self.started=None;self.ids=set();self.seen=set();self.previous=None
        self.rounds=[];self.reason=None;self.unsupported={};self.planned=[]

    @property
    def deadline(self):return None if self.started is None else self.started+self.settings.coverage_expansion_seconds

    def owns(self,case):return case.case_id in self.ids

    def expired(self):return self.deadline is not None and self.clock()>=self.deadline

    def propose(self,report):
        """Prefer reached branches, retaining the successful inputs that reached nested guards."""
        gaps=[branch for branch in report.coverage.get('branches',[]) if branch['unexercised_outcomes']]
        seen={(branch['checklist_id'],outcome) for branch in report.coverage.get('branches',[]) for outcome in branch['observed_outcomes']}
        if not gaps:self.reason='coverage_complete';return []
        if any(case.get('comparison_status')!='matched' for case in report.cases) or report.issues:
            self.reason='comparison_not_complete';return []
        if not self.settings.coverage_expansion_rounds or not self.settings.coverage_expansion_cases:
            self.reason='disabled';return []
        if self.started is None:self.started=self.clock()
        if self.expired():self.reason='time_budget';return []
        if self.previous is not None and seen<=self.previous:self.reason='no_progress';return []
        if len(self.rounds)>=self.settings.coverage_expansion_rounds:self.reason='round_budget';return []
        remaining=min(self.settings.coverage_expansion_cases-len(self.ids),self.settings.max_cases-len(report.cases))
        if remaining<=0:self.reason='case_budget';return []
        self.seen.update(input_identity(BoundaryCase.model_validate(case['case'])) for case in report.cases)
        items={item.id:item for item in self.boundary.parser_checklist.items if item.kind=='branch'}
        result=[]
        for gap in sorted(gaps,key=lambda item:(not bool(item['observed_outcomes']),item['checklist_id'])):
            if self.expired():self.reason='time_budget';break
            branch=items[gap['checklist_id']]
            successful=[case for case in report.cases if case['legacy']['exception'] is None]
            reached=[case for case in successful if any(p['id']==branch.id for p in case['legacy']['probes'])]
            if not successful:self.unsupported[branch.id]='no_successful_reference_input';continue
            baseline=BoundaryCase.model_validate((reached or successful)[0]['case'])
            candidates,reason=proposals(self.unit,self.boundary,branch,baseline,self.binding)
            if reason:self.unsupported[branch.id]=reason;continue
            for case in candidates:
                if self.expired():self.reason='time_budget';break
                identity=input_identity(case)
                if identity in self.seen or len(case.model_dump_json())>self.settings.max_case_chars:continue
                self.seen.add(identity);self.ids.add(case.case_id);result.append(case)
                if len(result)>=min(remaining,self.settings.coverage_expansion_batch_size):break
            if self.expired() or len(result)>=min(remaining,self.settings.coverage_expansion_batch_size):break
        self.previous=seen
        if result:
            self.rounds.append(dict(round=len(self.rounds)+1,case_ids=[case.case_id for case in result],target_gaps=[g['checklist_id'] for g in gaps]))
            self.planned.extend(case.model_copy(deep=True) for case in result)
        else:self.reason=self.reason or 'no_new_supported_inputs'
        return result

    def record(self,report):
        """Report actual exploration separately from the unchanged coverage acceptance rule."""
        gaps=[b for b in report.coverage.get('branches',[]) if b['unexercised_outcomes']]
        return dict(version=VERSION,stop_reason=self.reason or ('coverage_complete' if not gaps else 'not_started'),
            rounds=self.rounds,additional_cases=len(self.ids),executed_additional_cases=sum(c['case']['case_id'] in self.ids for c in report.cases),
            remaining_gaps=gaps,unsupported_conditions=self.unsupported,
            elapsed_seconds=round(self.clock()-self.started,3) if self.started is not None else 0,
            coverage_gaps_block=self.settings.require_branch_coverage,exhaustive=False)
