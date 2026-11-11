"""Cache immutable compiled snapshots while executing each observation in a fresh JVM."""
import subprocess
from models.boundary_harness_binding import BoundaryHarnessBinding
from runtime.format_comparison.planning import analyze_unit
from tools.behavior_verification.boundary_contracts import digest
from tools.behavior_verification.boundary_execution import compile_boundary_side, execute_boundary_case


def execute_pair(plan, unit, binding, case, directory, harness, settings, compiled, boundaries, *, native_case=None, compilation_failures=None, profile=None):
    """Run equivalent boundaries; a round trip may feed each side its own actual XML output."""
    key = digest(unit)
    if key not in boundaries:
        boundaries[key] = analyze_unit(unit, harness, collect_facts=settings.collect_facts,
            **({'original_classpath': plan.original_framework.classpath} if plan.original_framework.classpath else {}),
            **({'step_implementation':plan.original_step_implementation} if getattr(plan,'original_step_implementation',None) else {}))
    boundary = boundaries[key]
    native = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',
        sources=plan.native_sources, native_entry=binding, classpath=plan.native_classpath,
        external_bindings=plan.native_external_bindings, settings_bindings=binding.settings_bindings)
    observations = []
    if plan.native_classpath:
        from runtime.test_assets.runtime_dependencies import verify_runtime_dependencies
        verify_runtime_dependencies(harness,plan.native_classpath)
    for side, adapter, fixture in [('legacy', plan.original_framework, case), ('native', native, native_case or case)]:
        from runtime.composer_units.comparison import setup_key
        direction='unformat' if unit.get('kind')=='request_unformat' else 'format'
        packages=getattr(plan,'original_packages',{})
        package=packages.get(setup_key(unit,direction)) if packages else None
        if packages and not package and side=='legacy':raise ValueError('Original package is not prepared for this configuration variant')
        if side=='legacy' and package:
            from models.boundary_case import BoundaryCase
            from models.boundary_observation import BoundaryObservation
            from runtime.composer_units.execution import execute
            scenario={key:value for key,value in fixture.model_dump(mode='json').items() if key in BoundaryCase.model_fields}
            result=execute(package,scenario,profile,directory/'original-observations'/fixture.case_id)
            observations.append(BoundaryObservation.model_validate(result.observation) if result.observation else
                BoundaryObservation(case_id=fixture.case_id,status='verification_incomplete',issues=result.issues))
            continue
        resource_mode=bool(fixture.test_assets)
        cache_key = digest((key, side, adapter.model_dump(mode='json'), fixture.settings,resource_mode))
        if compilation_failures is not None and cache_key in compilation_failures:
            raise ValueError(compilation_failures[cache_key])
        if cache_key not in compiled:
            try:
                compiled[cache_key] = compile_boundary_side(unit, boundary, adapter, directory / cache_key[:24], side, harness,
                    settings=fixture.settings,**({'fixture_resources':True} if resource_mode else {}),
                    **({'allow_unknown_calls':True} if unit.get('kind') in {'response_format','request_unformat'} else {}))
            except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
                if compilation_failures is not None:compilation_failures[cache_key]=str(error)
                raise
        observations.append(execute_boundary_case(compiled[cache_key], unit, boundary, adapter, fixture,
                                                  timeout=settings.case_timeout_seconds))
    return observations
