"""Run existing original/native comparison engines for each standalone direction."""
import json
from pathlib import Path

from models.native_unit_bundle import NativeSourceFile
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.format_comparison.preparation import prepare_plan
from runtime.format_comparison.bindings import propose_bindings
from runtime.format_comparison.runner import run_comparison
from runtime.behavior_conversion.original_classpath import original_classpath
from runtime.format_comparison.component_diagnostics import directional_fixtures


def compare_standalone(request, units, files, profile, directory, native_classpath=(), *, model_call=None):
    """Retain independent directional outcomes without changing normal conversion acceptance."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    sources = [NativeSourceFile(path=name, content=text) for name, text in files.items() if name.startswith('src/main/java/')]
    results = {}
    for identity, value in request['standalone_component']['boundaries'].items():
        boundary = UnitVerificationBoundary.model_validate(value)
        unit = units[identity]
        direction = {'response_format': 'format', 'request_unformat': 'unformat', 'configured_step': 'step_execute'}[unit['kind']]
        folder = root / identity
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if not profile.format_comparison.enabled:
                raise ValueError('Comparison testing is disabled in this profile')
            call = model_call
            if call is None:
                from runtime.model_execution.adk_executor import AdkExecutor
                call = AdkExecutor(profile).execute
            entries, issues = propose_bindings(unit, sources, call, profile.format_comparison,
                folder / 'binding-proposal', directions=[direction])
            if issues or not entries or any(entry.direction != direction for entry in entries.values()):
                raise ValueError('Directional native binding unavailable: ' + '; '.join(issues))
            def fixtures(selected, discovery):
                return directional_fixtures(unit, boundary, profile.executable_verification, direction, selected, discovery)
            plan, preparation = prepare_plan(unit['component_class'], 'configured' if direction == 'step_execute' else 'basic', unit, sources, fixtures,
                profile, folder / 'preparation', entries=entries, model_call=call)
            if plan is None:
                raise ValueError('Comparison preparation unavailable: ' + json.dumps(preparation))
            plan.native_classpath = list(native_classpath)
            plan.original_framework.classpath = original_classpath(profile, unit)
            if direction == 'step_execute':
                plan.original_step_implementation = boundary.implementation_class
            outcome = run_comparison(plan, profile, folder / 'execution')
            counts = outcome['counts']
            matched = (outcome['status'] == 'completed' and counts.get('planned', 0) > 0 and
                       counts.get('matched') == counts.get('planned'))
            results[identity] = dict(direction=direction, class_name=unit['component_class'],
                status='matched' if matched else 'failed' if counts.get('different') or counts.get('execution_failed') else 'comparison_unavailable',
                counts=counts, report=str((folder / 'execution/format-comparison.json').resolve()))
        except Exception as error:
            from runtime.model_execution.error_details import sanitize_diagnostic
            results[identity] = dict(direction=direction, class_name=unit['component_class'],
                status='comparison_unavailable', reason=sanitize_diagnostic(str(error)))
        (folder / 'result.json').write_text(json.dumps(results[identity], indent=2), encoding='utf-8')
    (root / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return results
