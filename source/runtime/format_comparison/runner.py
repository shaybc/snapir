"""Orchestrate disposable format diagnostics through the existing JVM adapters."""
import hashlib
import shutil
import tempfile
import subprocess
from pathlib import Path
from runtime.java_toolchain import java_scope
from runtime.format_comparison.bindings import resolved_binding, missing_binding_inputs
from runtime.format_comparison.cases import expand_fixtures, unresolved_inputs
from runtime.format_comparison.planning import unit_for_case
from runtime.format_comparison.execution import execute_pair
from runtime.format_comparison.reporting import compare_case, publish, branch_results
from tools.behavior_verification.boundary_contracts import digest
from tools.behavior_verification.boundary_execution import verify_compiled_artifacts
from tools.behavior_verification.java_tool import default_tool_path


def run_comparison(plan, profile, directory=None, *, tool=None):
    """Run explicit diagnostics only; never open migration state or mark conversion accepted."""
    settings = profile.format_comparison
    if not settings.enabled:
        raise ValueError('Format comparison is disabled; explicitly enable the diagnostic setting')
    directory = Path(directory) if directory else Path(tempfile.mkdtemp(prefix='snapir-format-comparison-'))
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('Comparison output must be a new empty directory')
    snapshot = plan.model_dump_json()
    (directory / 'plan.json').write_text(snapshot, encoding='utf-8')
    report = dict(label=plan.label, directory=str(directory.resolve()), status='running', cases=[], acceptance_changed=False, conversion_resumed=False,
                  exhaustive_equivalence=False, plan_hash=digest(plan.model_dump(mode='json')),
                  policy=settings.model_dump(mode='json'), limitations=list(plan.discovery.limitations),
                  fact_collection='enabled' if settings.collect_facts else 'disabled_for_test',
                  fact_validation='not_run', fact_validation_blocking=False,
                  unresolved_inputs=plan.discovery.model_dump(mode='json'),
                  isolation='fresh JVM per side per case; disposable compiled snapshots')
    if not settings.collect_facts:
        report['limitations'].append('Fact collection and fact-derived branch probes are disabled for this diagnostic; fact validation is not run')
    compiled = {}; boundaries = {}
    try:
        cases = expand_fixtures(plan, settings)
        report['planned_cases'] = len(cases)
        publish(report, directory)
        harness = directory / 'harness.jar'
        shutil.copyfile(tool or default_tool_path(), harness)
        report['tool_hash'] = hashlib.sha256(harness.read_bytes()).hexdigest()
        with java_scope(profile):
            for case in cases:
                item = dict(case=case.model_dump(mode='json'), status='comparison_unavailable', differences=[], limitations=[])
                report['cases'].append(item)
                missing = unresolved_inputs(plan, case)
                if missing:
                    item['limitations'] = missing; publish(report, directory); continue
                try:
                    unit = unit_for_case(plan, case)
                    entry = plan.entries[case.binding_id]
                    try:
                        binding = resolved_binding(entry, unit, plan.native_sources)
                    except ValueError as error:
                        item['limitations'] = [str(error)]
                        publish(report, directory)
                        continue
                    missing = missing_binding_inputs(binding, case)
                    if missing:
                        item['limitations'] = missing
                        publish(report, directory)
                        continue
                    left, right = execute_pair(plan, unit, binding, case, directory, harness, settings, compiled, boundaries)
                    item.update(legacy=left.model_dump(mode='json'), native=right.model_dump(mode='json'))
                    item.update(compare_case(left, right, entry.direction, settings))
                    item['targeted_branches'] = branch_results(case, left.probes)
                    if case.roundtrip_binding_id is not None:
                        if left.exception or right.exception or not isinstance(left.output, str) or not isinstance(right.output, str):
                            item['limitations'].append('Round-trip formatting did not produce XML on both sides')
                            if item['status'] == 'matched': item['status'] = 'comparison_unavailable'
                        else:
                            read_case = case.model_copy(deep=True)
                            read_case.case_id = '_roundtrip-' + digest(case.case_id)[:24]
                            read_case.binding_id = case.roundtrip_binding_id
                            read_case.roundtrip_binding_id = None
                            read_case.input_xml = left.output
                            read_unit = unit_for_case(plan, read_case)
                            read_entry = plan.entries[read_case.binding_id]
                            read_binding = resolved_binding(read_entry, read_unit, plan.native_sources)
                            result_keys = {projection.context_key for projection in read_binding.context_writes}
                            read_case.initial_context = {key: value for key, value in case.initial_context.items() if key not in result_keys}
                            read_native = read_case.model_copy(update={'input_xml': right.output})
                            a, b = execute_pair(plan, read_unit, read_binding, read_case, directory, harness, settings,
                                                compiled, boundaries, native_case=read_native)
                            roundtrip = compare_case(a, b, 'unformat', settings)
                            item['roundtrip'] = dict(legacy=a.model_dump(mode='json'), native=b.model_dump(mode='json'), **roundtrip)
                            if roundtrip['status'] == 'different' or item['status'] == 'matched':
                                item['status'] = roundtrip['status']
                except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                    item.update(status='execution_failed', limitations=[str(error)])
                publish(report, directory)
            for artifact in compiled.values():
                verify_compiled_artifacts(artifact)
        if plan.model_dump_json() != snapshot:
            raise ValueError('Plan inputs changed during execution')
        report['status'] = 'completed'
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        report.update(status='execution_failed', error=str(error))
    finally:
        report['inputs_unchanged'] = plan.model_dump_json() == snapshot
        report['artifact_hashes'] = {key: artifact['hashes'] for key, artifact in compiled.items()}
        publish(report, directory)
    return report

