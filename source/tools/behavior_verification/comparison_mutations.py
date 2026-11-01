"""Measure differential-test strength in disposable copies, without accepting or repairing code."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.independent_comparison import VERSION as COMPARISON_VERSION
from tools.behavior_verification.comparison_mutation_sources import generate_mutations

VERSION='comparison-mutations-v1'


def save_measurement(directory,report):
    """Atomically preserve partial counters before another bounded mutation starts."""
    temporary=directory/'comparison-strength.json.tmp'
    temporary.write_text(json.dumps(report,indent=2),encoding='utf-8')
    temporary.replace(directory/'comparison-strength.json')


def classify_mutation(report,identity):
    """Distinguish executed sites from survivors and infrastructure-limited comparisons."""
    touched=any(probe['id']==identity for case in report.cases for probe in case['native']['probes'])
    if report.issues:
        # Only javac's own diagnostic establishes an invalid source mutation.
        if any('error:' in issue and '.java:' in issue for issue in report.issues):return 'invalid'
        return 'tool_failure'
    if not touched:return 'uncovered' if report.status=='matched_observed_cases' else 'tool_failure'
    if report.status=='differences_found':return 'detected'
    if report.status=='matched_observed_cases':return 'survived'
    return 'tool_failure'


def measure(job,directory):
    """Recheck the untouched baseline, then compare each bounded single-site mutant."""
    boundary=UnitVerificationBoundary.model_validate(job['boundary'])
    legacy=BoundaryHarnessBinding.model_validate(job['legacy']);native=BoundaryHarnessBinding.model_validate(job['native'])
    cases=[BoundaryCase.model_validate(case) for case in job['cases']]
    tool=Path(job['tool'])
    report=dict(schema_version=VERSION,status='running',advisory=True,affects_acceptance=False,exhaustive=False,
        baseline_status='pending',mutations=[],counts={name:0 for name in ('detected','survived','uncovered','invalid','tool_failure')},
        max_mutants=job['max_mutants'],case_count=len(cases),candidate_sources=job['candidate_sources'])
    save_measurement(directory,report)
    from tools.behavior_verification.mutation_baseline import reusable_baseline
    baseline,reason=reusable_baseline(job,boundary,legacy,native,cases,tool)
    report.update(baseline_reused=baseline is not None,baseline_reuse_reason=reason)
    if baseline is None:
        baseline=verify_boundary(job['unit'],boundary,legacy,native,cases,directory/'baseline',tool=tool,
            candidate_label='unchanged_mutation_baseline',comparison_policy=COMPARISON_VERSION)
    report['baseline_status']=baseline.status
    if baseline.status!='matched_observed_cases':
        report.update(status='baseline_not_verified',issues=baseline.issues);save_measurement(directory,report);return report
    save_measurement(directory,report)
    plans=generate_mutations(native,tool,directory,job['max_mutants'],job.get('owned_paths'))
    report['planned_mutants']=len(plans)
    for plan in plans:
        entry={key:value for key,value in plan.items() if key!='content'};entry['status']='running'
        report['mutations'].append(entry);save_measurement(directory,report)
        changed=native.model_copy(deep=True)
        for file in changed.sources:
            if file.path==plan['path']:file.content=plan['content']
        result=verify_boundary(job['unit'],boundary,legacy,changed,cases,directory/plan['id'],tool=tool,
            candidate_label=plan['id'],comparison_policy=COMPARISON_VERSION,stop_after_difference=True)
        entry.update(status=classify_mutation(result,plan['id']),comparison_status=result.status,
            executed_cases=len(result.cases),unexecuted_cases=len(result.unexecuted_case_ids),
            evidence=str(directory/plan['id']/'boundary-comparison.json'))
        report['counts'][entry['status']]+=1;save_measurement(directory,report)
    report['status']='completed' if plans else 'no_supported_mutations'
    denominator=report['counts']['detected']+report['counts']['survived']
    report['executed_valid_mutants']=denominator
    report['detection_rate']=report['counts']['detected']/denominator if denominator else None
    report['selection_truncated_possible']=len(plans)==job['max_mutants']
    report['recommendations']=['Investigate surviving or uncovered sites; they do not prove a production defect.']
    save_measurement(directory,report)
    return report


if __name__=='__main__':
    path=Path(sys.argv[1]);job=json.loads(path.read_text(encoding='utf-8'))
    if job.get('execution_cwd'):os.chdir(job['execution_cwd'])
    with java_scope(SimpleNamespace(java_version=job['java_version'],java_home=job.get('java_home'))):
        measure(job,path.parent)
