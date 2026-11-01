"""Technical check-ladder feedback, separate from optional AI opinions."""
import json


class VerificationFailure(ValueError):
    """A concrete candidate mismatch can be corrected using exact item IDs and inputs."""
    def __init__(self, report):
        self.verification_feedback = report
        super().__init__('Unit verification failed: ' + json.dumps(report, ensure_ascii=True))


class VerificationIncomplete(VerificationFailure):
    """Missing execution capability is never acceptance or an unlimited model retry."""


def comparison_feedback(report):
    """Keep failing controls/inputs intact, without repeating successful observations."""
    if report.execution_environment.get('comparison_policy'):
        failed=[case for case in report.cases if case.get('differences')] if not report.issues else []
        incomplete=[dict(case_id=case['case']['case_id'],limitations=case.get('limitations',[]))
            for case in report.cases if case.get('limitations')]
        feedback=dict(status=report.status,issues=report.issues,comparison_summary=report.execution_environment.get('comparison_summary',{}),
            failing_cases=[dict(case=case['case'],differences=[{key:value for key,value in delta.items() if key!='related_checklist_ids'}
                for delta in case['differences']]) for case in failed],
            omitted_failing_case_count=0,unexecuted_case_ids=report.unexecuted_case_ids)
        if report.status=='differences_found':feedback['correction_scope']='compared_observable_differences_only'
        else:feedback.update(incomplete_cases=incomplete[:8],omitted_incomplete_case_count=max(0,len(incomplete)-8))
        return feedback
    failed = [item for item in report.cases if item['differences']]
    return dict(status=report.status, issues=report.issues,
        failing_cases=[dict(case=item['case'], differences=item['differences'], legacy=item['legacy'], native=item['native'])
                       for item in failed[:8]], omitted_failing_case_count=max(0, len(failed) - 8),
        unexecuted_case_ids=report.unexecuted_case_ids)
