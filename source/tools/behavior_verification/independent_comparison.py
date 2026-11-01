"""Classify independently observed differences without treating missing observations as defects."""
from collections import Counter
from tools.behavior_verification.thin_path_observations import compare_observable_case
from tools.behavior_verification.boundary_comparison import boundary_field_results,_diff
from tools.behavior_verification.boundary_logging import compare_logging

VERSION='independent-observations-v1'


def compare_case(case_id,legacy,native,binding=None,*,xml_output=False):
    """Retain raw observations externally; filter only explicitly unobservable state here."""
    limitations=[];logging=[]
    if legacy.case_id!=case_id or native.case_id!=case_id:
        limitations.append(dict(kind='observation_identity_mismatch',expected_case_id=case_id,
            legacy_case_id=legacy.case_id,native_case_id=native.case_id))
    if legacy.status!='completed' or native.status!='completed':
        limitations.append(dict(kind='execution_incomplete',legacy_issues=legacy.issues,native_issues=native.issues))
    for side,value in (('legacy',legacy),('native',native)):
        if value.invocation_completed is False:limitations.append(dict(kind='invocation_not_completed',side=side))
    for side,value in (('legacy',legacy),('native',native)):
        events=[*value.writes,*value.removals]
        malformed=any(not isinstance(event.get('key'),str) or 'value' not in event for event in events)
        malformed=malformed or any(not isinstance(event.get('target'),str) or not isinstance(event.get('arguments'),list) for event in value.external_calls)
        malformed=malformed or value.exception is not None and not isinstance(value.exception.get('type'),str)
        if malformed:limitations.append(dict(kind='malformed_observation',side=side))
    if limitations:
        fields=boundary_field_results(legacy,native,[])
        for field in fields:field['result']='not_compared'
        differences=[]
        # A replay-control failure may occur after the actual adapter call ended.
        # Its completed call trace remains evidence, while other fields stay unknown.
        if (all(item['kind']=='execution_incomplete' for item in limitations)
            and all(value.invocation_completed is True or value.status=='completed' for value in (legacy,native))):
            left,right,log_differences,logging=compare_logging(legacy.external_calls,native.external_calls)
            differences.extend(log_differences);_diff(left,right,'external_calls',differences)
            for field in fields:
                name=field['field']
                if name in {'external_calls','logging'}:
                    field['result']='different' if any(d['path']==name or d['path'].startswith((name+'.',name+'[')) for d in differences) else 'matched'
        return dict(comparison_status='different' if differences else 'incomplete',differences=differences,
            limitations=limitations,logging_diagnostics=logging,field_results=fields)
    mappings=[dict(context_key=p.context_key,path=[p.context_key],status='bound',presence_observable=bool(p.presence_getters))
        for p in binding.context_writes] if binding else []
    left,right=legacy,native;removed=set();trace_unknown=False
    # DTO projections expose final values, not an arbitrary removal/write-event trace.
    # Unknown state remains a blocking limitation, never silently accepted equality.
    if binding and legacy.exception is None:
        removed={event['key'] for event in legacy.removals}
        trace_unknown=any(count>1 for count in Counter(event['key'] for event in legacy.writes).values())
        if removed or trace_unknown:
            left,right=legacy.model_copy(deep=True),native.model_copy(deep=True)
            if removed:
                limitations.append(dict(kind='removals_not_observable',keys=sorted(removed)))
                left.removals=[];right.removals=[]
                for value in (left,right):
                    for key in removed:value.context.pop(key,None)
                    value.writes=[event for event in value.writes if event['key'] not in removed]
            if trace_unknown:
                limitations.append(dict(kind='write_trace_not_observable'))
                left.writes=[];right.writes=[]
    differences,unknown=compare_observable_case(left,right,mappings,xml_output=xml_output,
        logging_diagnostics=logging,partial_state_on_exception=True)
    limitations.extend(unknown)
    fields=boundary_field_results(legacy,native,differences)
    partial=any(item['kind']=='partial_writes_not_compared' for item in limitations)
    presence={item['context_key'] for item in limitations if item['kind']=='presence_not_observable'}
    for field in fields:
        name=field['field']
        key=name[len('context.'):] if name.startswith('context.') else None
        if partial and (key is not None or name in {'output','writes','removals'}):field['result']='not_compared'
        if name=='writes' and (presence or trace_unknown or removed):field['result']='not_compared'
        if name=='removals' and removed:field['result']='not_compared'
        if key in removed:field['result']='not_compared'
        if key in presence:
            field['value_result']=field['result'] if key in legacy.context else 'not_compared'
            field.update(result='not_compared',presence_result='not_compared')
    return dict(comparison_status='different' if differences else 'incomplete' if limitations else 'matched',
        differences=differences,limitations=limitations,logging_diagnostics=logging,field_results=fields)


def summarize(report):
    """Count actual case outcomes; limitation-bearing cases cannot establish acceptance."""
    counts=Counter(case['comparison_status'] for case in report.cases)
    return dict(matched=counts['matched'],different=counts['different'],incomplete=counts['incomplete'],
        cases_with_limitations=sum(bool(case['limitations']) for case in report.cases),unexecuted=len(report.unexecuted_case_ids))


def finish_report(report):
    """Only proven differences request correction; limits always prevent a complete match."""
    summary=summarize(report)
    report.execution_environment['comparison_summary']=summary
    if report.issues:report.status='verification_incomplete'
    elif summary['different']:report.status='differences_found'
    elif summary['cases_with_limitations'] or summary['unexecuted'] or not report.cases:
        report.status='verification_incomplete'
    else:report.status='matched_observed_cases'
