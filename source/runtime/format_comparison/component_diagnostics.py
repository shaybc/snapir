"""Optional post-build diagnostics; never candidate repair or conversion acceptance."""
import json
from runtime.behavior_conversion.original_classpath import original_classpath
from pathlib import Path
from models.format_comparison_case import FormatComparisonCase
from models.format_comparison_plan import FormatComparisonEntry
from models.native_unit_bundle import NativeSourceFile
from runtime.format_comparison.preparation import prepare_plan
from runtime.format_comparison.runner import run_comparison
from runtime.model_execution.adk_executor import AdkExecutor
from tools.behavior_verification.boundary_contracts import digest
from tools.behavior_verification.input_scenarios import generate_input_scenarios
from runtime.format_comparison.context_discovery import applies_to_direction


def diagnose_component(validator, candidate, files, directory, *, model_call=None, native_classpath=()):
    """Diagnose a complete configured format only after its normal checks have succeeded."""
    if not validator.profile.format_comparison.enabled or not validator.request.get('configured_format'):
        return None
    try:
        return _diagnose_component(validator, candidate, files, directory, model_call=model_call, native_classpath=native_classpath)
    except Exception as error:
        result=dict(status='comparison_unavailable', reason=type(error).__name__+': '+str(error), acceptance_changed=False)
        root=Path(directory);root.mkdir(parents=True,exist_ok=True)
        (root/'unavailable.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result


def _diagnose_component(validator, candidate, files, directory, *, model_call=None, native_classpath=()):
    """Prepare and execute one explicit diagnostic, with no state-store calls."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    identity = validator.request['configured_format']['unit_id']
    unit = validator.units[identity]
    from models.unit_verification_boundary import UnitVerificationBoundary
    boundary = UnitVerificationBoundary.model_validate(validator.boundaries['boundaries'][identity])
    sources = [NativeSourceFile(path=name, content=content) for name, content in files.items() if name.startswith('src/main/java/')]
    from runtime.test_assets.preparation import current,enabled
    assets=current()
    if enabled(validator.profile):
        if not assets:raise ValueError('Shared comparison scenarios are not prepared; no deterministic fallback')
        from runtime.test_assets.materialization import comparison_plan
        plan=comparison_plan(validator.request['configured_format']['logical_id'],unit,sources,
            assets['bank'],assets['comparisons'],assets['manifest_hash'])
        plan.native_classpath=list(native_classpath);plan.original_framework.classpath=original_classpath(validator.profile,unit)
        from runtime.composer_units.comparison import prepare_comparison
        plan=prepare_comparison(plan,validator.profile,directory/'original-packages')
        result=run_comparison(plan,validator.profile,directory/'execution')
        return dict(status=result['status'],counts=result['counts'],acceptance_changed=False,
            fixture_manifest_hash=assets['manifest_hash'],report='execution/format-comparison.json')
    direction = 'format' if unit['kind'] == 'response_format' else 'unformat'
    prior = getattr(candidate, 'verification_binding', None)
    entries = {'configured': FormatComparisonEntry(direction=direction, binding=prior)} if prior else None
    profile = validator.profile.model_copy(deep=True)
    profile.max_model_attempts = 1
    if model_call is None:
        model_call = AdkExecutor(profile).execute

    def fixtures(selected, discovery):
        # Reuse input generation. Its samples are exploratory, not inferred expected outputs.
        generated, _ = generate_input_scenarios(unit, boundary, profile.executable_verification)
        result = []
        for key, entry in selected.items():
            if entry.direction != direction:
                continue  # Other direction needs its own configured boundary and fixtures.
            for original in generated:
                values = original.model_dump(mode='json')
                values.update(binding_id=key, origin='exploratory', case_id='fixture-' + digest((key, values))[:24])
                if discovery:
                    for requirement in discovery.requirements:
                        if not applies_to_direction(requirement,entry.direction):
                            continue
                        supported = [value for value in requirement.values if value.origin == 'source_backed']
                        if requirement.context_key is not None and requirement.context_key not in values['initial_context'] and supported:
                            values['initial_context'][requirement.context_key] = supported[0].value
                result.append(FormatComparisonCase.model_validate(values))
        if not result:
            raise ValueError('No matching configured direction has runnable baseline fixtures')
        return result

    try:
        plan, preparation = prepare_plan(validator.request.get('configured_format', {}).get('logical_id', identity),
            'configured', unit, sources, fixtures, profile, directory / 'preparation', entries=entries, model_call=model_call)
        if plan is None:
            return preparation
        plan.native_classpath = list(native_classpath)
        plan.original_framework.classpath = original_classpath(profile,unit)
        from runtime.composer_units.comparison import prepare_comparison
        plan=prepare_comparison(plan,profile,directory/'original-packages')
        # Use only approved runtime dependencies from the existing build verifier.
        result = run_comparison(plan, profile, directory / 'execution')
        return dict(status=result['status'], counts=result['counts'], acceptance_changed=False,
                    report='execution/format-comparison.json')
    except Exception as error:
        # No diagnostic/model failure can repair Java, reset retries or replace normal acceptance.
        result = dict(status='comparison_unavailable', reason=type(error).__name__, acceptance_changed=False)
        (directory / 'unavailable.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
