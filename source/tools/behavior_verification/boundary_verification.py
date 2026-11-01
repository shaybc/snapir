"""Standalone observed-boundary comparison; the existing conversion gates are unchanged."""
import subprocess
from pathlib import Path
from models.boundary_comparison_report import BoundaryComparisonReport
from tools.behavior_verification.boundary_execution import compile_boundary_side, execute_boundary_case, verify_compiled_artifacts
from tools.behavior_verification.boundary_comparison import compare_boundary_observations, boundary_field_results
from tools.behavior_verification.boundary_logging import LOGGING_POLICY
from tools.behavior_verification.boundary_coverage import boundary_coverage
from tools.behavior_verification.boundary_contracts import boundary_contract
from runtime.java_toolchain import java_version


def verify_boundary(unit, boundary, legacy_binding, native_binding, cases, directory, *, tool=None, candidate_label, case_timeout=15, continue_incomplete=False,comparison_policy=None,coverage_expansion=None,stop_after_difference=False):
    """Persist controls, both observations, per-field differences and remaining coverage gaps."""
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=False)
    cases = list(cases)
    report = BoundaryComparisonReport(unit_id=unit['unit_id'], source_manifest_hash=boundary.source_manifest_hash,
                                     configuration_hash=boundary.configuration_hash, logging_comparison_policy=LOGGING_POLICY.copy())
    report.execution_environment = dict(java_version=java_version(), assertions_enabled=True, timezone='UTC', locale='ROOT',
        isolation='fresh_JVM_per_side_per_case', exception_comparison='type_and_post_failure_state',
        numeric_comparison='protocol_numeric_representation_preserved_including_decimal_scale', case_timeout_seconds=case_timeout)
    try:
        from tools.behavior_verification.comparison_environment import runtime_fingerprint
        report.execution_environment.update(runtime_fingerprint=runtime_fingerprint(),working_directory=str(Path.cwd().resolve()))
        if stop_after_difference and (not comparison_policy or coverage_expansion is not None):
            raise ValueError('Mutation early stopping requires independent comparison without coverage expansion')
        if coverage_expansion is not None and not comparison_policy:raise ValueError('Coverage expansion requires independent comparison policy')
        if comparison_policy:
            from tools.behavior_verification.independent_comparison import VERSION
            if comparison_policy!=VERSION:raise ValueError('Unsupported independent comparison policy')
            report.execution_environment['comparison_policy']=comparison_policy
            report.execution_environment.update(exception_comparison='type; partial state remains incomplete until operation policy is defined',
                absence_policy='explicit_presence_required_for_DTO_projections',
                state_event_policy='actual_traces_required; final_DTOs_do_not_prove_removals_or_repeated_writes')
        if boundary.unit_id != unit['unit_id'] or boundary.unit_fingerprint != unit['fingerprint']:
            raise ValueError('Boundary evidence belongs to another unit/revision')
        current = boundary_contract(unit, {'opStep': boundary.implementation_class})
        if current.configuration_hash != boundary.configuration_hash or current.source_manifest_hash != boundary.source_manifest_hash:
            raise ValueError('Boundary source/configuration fingerprint changed')
        if not boundary.reachable_slice or not boundary.parser_checklist or boundary.parser_checklist.status != 'extracted':
            raise ValueError('Boundary needs a validated source graph and extracted checklist')
        if not cases or len({case.case_id for case in cases}) != len(cases): raise ValueError('Boundary cases must have unique identities')
        if any(not case.case_id.replace('-', '').replace('_', '').isalnum() for case in cases): raise ValueError('Unsafe boundary case identity')
        settings = [setting for case in cases for setting in case.settings]
        legacy = compile_boundary_side(unit, boundary, legacy_binding, directory / 'legacy', 'legacy', tool, settings=settings)
        native = compile_boundary_side(unit, boundary, native_binding, directory / 'native', 'native', tool, settings=settings)
        report.artifact_hashes = {**{'legacy:' + key: value for key, value in legacy['hashes'].items()},
                                  **{'native:' + key: value for key, value in native['hashes'].items()}}
        observations = []
        for index, case in enumerate(cases):
            timed=coverage_expansion is not None and coverage_expansion.owns(case)
            if timed and coverage_expansion.expired():
                coverage_expansion.reason='time_budget';report.unexecuted_case_ids=[item.case_id for item in cases[index:]];break
            options={'deadline':coverage_expansion.deadline} if timed else {}
            left_timeout=min(case_timeout,max(0.001,(coverage_expansion.deadline-coverage_expansion.clock())/2)) if timed else case_timeout
            left = execute_boundary_case(legacy, unit, boundary, legacy_binding, case, timeout=left_timeout,**options)
            right = execute_boundary_case(native, unit, boundary, native_binding, case, timeout=case_timeout,**options)
            logging_diagnostics = []
            outcome=None
            if comparison_policy:
                from tools.behavior_verification.independent_comparison import compare_case
                outcome=compare_case(case.case_id,left,right,native_binding.native_entry,xml_output=unit['kind']=='response_format')
                differences=outcome['differences'];logging_diagnostics=outcome['logging_diagnostics']
            else:
                differences=compare_boundary_observations(left,right,xml_output=unit['kind']=='response_format',
                    logging_diagnostics=logging_diagnostics)
            touched = {probe['id'] for probe in left.probes}
            implicated = [item.id for item in boundary.parser_checklist.items if item.id in touched or item.code_node_id in touched]
            for difference in differences: difference['related_checklist_ids'] = implicated
            report.cases.append(dict(case=case.model_dump(mode='json'), legacy=left.model_dump(mode='json'),
                native=right.model_dump(mode='json'), differences=differences, logging_diagnostics=logging_diagnostics,
                field_results=boundary_field_results(left, right, differences), candidate_label=candidate_label))
            if outcome:report.cases[-1].update(outcome)
            observations.append(left)
            if (stop_after_difference and outcome and outcome['comparison_status']=='different' and not outcome['limitations']
                and left.status=='completed' and right.status=='completed'):
                report.unexecuted_case_ids=[remaining.case_id for remaining in cases[index+1:]]
                report.execution_environment['stopping_reason']='completed_observable_difference'
                break
            if coverage_expansion is not None and index==len(cases)-1:
                report.coverage=boundary_coverage(boundary,observations)
                additional=coverage_expansion.propose(report)
                identities={item.case_id for item in cases}
                if any(item.case_id in identities or not item.case_id.replace('-','').replace('_','').isalnum() for item in additional):
                    raise ValueError('Expanded cases require new safe identities')
                cases.extend(additional)
            if not (continue_incomplete or comparison_policy) and (left.status != 'completed' or right.status != 'completed'):
                report.unexecuted_case_ids = [remaining.case_id for remaining in cases[index + 1:]]
                break
        report.coverage = boundary_coverage(boundary, observations)
        verify_compiled_artifacts(legacy); verify_compiled_artifacts(native)
        if runtime_fingerprint()!=report.execution_environment['runtime_fingerprint']:
            raise ValueError('Comparison runtime or policy changed during execution')
        if any(item['legacy']['status'] != 'completed' or item['native']['status'] != 'completed' for item in report.cases):
            if not comparison_policy:report.issues.append('One or more isolated cases could not be verified')
        elif any(item['differences'] for item in report.cases): report.status = 'differences_found'
        else: report.status = 'matched_observed_cases'
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        report.issues.append(str(error))
        executed = {item['case']['case_id'] for item in report.cases}
        report.unexecuted_case_ids = [case.case_id for case in cases if case.case_id not in executed]
    finally:
        if coverage_expansion is not None:report.execution_environment['coverage_expansion']=coverage_expansion.record(report)
        if comparison_policy:
            from tools.behavior_verification.independent_comparison import finish_report
            finish_report(report)
        temporary = directory / 'boundary-comparison.json.tmp'
        temporary.write_text(report.model_dump_json(indent=2), encoding='utf-8')
        temporary.replace(directory / 'boundary-comparison.json')
    return report

