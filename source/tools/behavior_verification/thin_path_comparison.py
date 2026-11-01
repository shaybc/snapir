"""Experimental boundary comparison with automatic request projections and explicit limitations."""
import json
import subprocess
from pathlib import Path
from models.thin_path_comparison_report import ThinPathComparisonReport
from tools.behavior_verification.boundary_execution import compile_boundary_side,execute_boundary_case,verify_compiled_artifacts
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.boundary_coverage import boundary_coverage
from tools.behavior_verification.thin_path_binding import configured_fields,inspect_getters,auto_bind
from tools.behavior_verification.thin_path_observations import expected_types,compare_observable_case
from tools.behavior_verification.boundary_logging import LOGGING_POLICY
from runtime.java_toolchain import java_version


def compare_thin_boundary(unit,boundary,legacy_binding,native_binding,cases,directory,*,tool=None):
    """Run all case-specific failures; unsupported API/tool failures never become AI correction evidence."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    report=ThinPathComparisonReport(unit_id=unit['unit_id'],source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash,logging_comparison_policy=LOGGING_POLICY.copy())
    report.execution_environment=dict(java_version=java_version(),isolation='fresh_JVM_per_side_per_case',
        timezone='UTC',locale='ROOT',getter_matching='case_and_separators_exact_unique_path_and_type',
        absence_policy='explicit_presence_required',partial_writes_policy='not_compared_until_operation_policy_is_defined')
    cases=list(cases)
    try:
        current=boundary_contract(unit,{'opStep':boundary.implementation_class})
        if any(getattr(current,key)!=getattr(boundary,key) for key in ('unit_id','unit_fingerprint','source_manifest_hash','configuration_hash')):
            raise ValueError('Original source/configuration revision changed')
        if not cases or len({case.case_id for case in cases})!=len(cases):raise ValueError('Cases need unique identities')
        if any(not case.case_id.replace('-','').replace('_','').isalnum() for case in cases):raise ValueError('Unsafe case identity')
        settings=[setting for case in cases for setting in case.settings]
        legacy=compile_boundary_side(unit,boundary,legacy_binding,directory/'legacy','legacy',tool,settings=settings)
        native=compile_boundary_side(unit,boundary,native_binding,directory/'native','native',tool,settings=settings)
        report.artifact_hashes={**{'legacy:'+k:v for k,v in legacy['hashes'].items()},**{'native:'+k:v for k,v in native['hashes'].items()}}
        originals=[execute_boundary_case(legacy,unit,boundary,legacy_binding,case) for case in cases]
        mappings=[]
        if unit['kind']=='request_unformat':
            inventory=inspect_getters(native,native_binding.native_entry)
            selected,mappings,limitations=auto_bind(unit,native_binding.native_entry,inventory,
                expected_types(originals,configured_fields(unit)))
            native_binding=native_binding.model_copy(update={'native_entry':selected})
            report.auto_binding=mappings
            report.limitations=limitations
            (directory/'auto-binding.json').write_text(json.dumps(dict(binding=selected.model_dump(mode='json'),
                mappings=mappings,limitations=limitations),indent=2),encoding='utf-8')
        consecutive=None
        for index,(case,left) in enumerate(zip(cases,originals)):
            right=execute_boundary_case(native,unit,boundary,native_binding,case)
            logging_diagnostics=[]
            differences,limitations=compare_observable_case(left,right,mappings,xml_output=unit['kind']=='response_format',
                logging_diagnostics=logging_diagnostics)
            report.cases.append(dict(case=case.model_dump(mode='json'),legacy=left.model_dump(mode='json'),
                native=right.model_dump(mode='json'),differences=differences,limitations=limitations,logging_diagnostics=logging_diagnostics,
                comparison_status='different' if differences else 'incomplete' if limitations else 'matched'))
            if limitations:report.limitations.append(dict(case_id=case.case_id,details=limitations))
            issue=tuple(right.issues) if right.status!='completed' else None
            global_api_failure=issue and any(marker in ' '.join(issue) for marker in (
                'NoSuchMethodException','ClassNotFoundException','IllegalAccessException','Unsupported observable type'))
            if global_api_failure and issue==consecutive:
                report.issues.append('Native invocation repeatedly unavailable; remaining native cases not executed')
                report.unexecuted_case_ids=[item.case_id for item in cases[index+1:]];break
            consecutive=issue
        report.coverage=boundary_coverage(boundary,originals)
        verify_compiled_artifacts(legacy);verify_compiled_artifacts(native)
        if any(case['differences'] for case in report.cases):report.status='differences_found'
        elif not report.limitations and not report.issues and not report.unexecuted_case_ids:report.status='matched_observed_cases'
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        report.issues.append(str(error));executed={case['case']['case_id'] for case in report.cases}
        report.unexecuted_case_ids=[case.case_id for case in cases if case.case_id not in executed]
    finally:
        (directory/'boundary-comparison.json').write_text(report.model_dump_json(indent=2),encoding='utf-8')
    return report
