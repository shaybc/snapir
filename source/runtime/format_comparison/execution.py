"""Cache immutable compiled snapshots while executing each observation in a fresh JVM."""
from models.boundary_harness_binding import BoundaryHarnessBinding
from runtime.format_comparison.planning import analyze_unit
from tools.behavior_verification.boundary_contracts import digest
from tools.behavior_verification.boundary_execution import compile_boundary_side, execute_boundary_case


def execute_pair(plan, unit, binding, case, directory, harness, settings, compiled, boundaries, *, native_case=None):
    """Run equivalent boundaries; a round trip may feed each side its own actual XML output."""
    key = digest(unit)
    if key not in boundaries:
        boundaries[key] = analyze_unit(unit, harness, collect_facts=settings.collect_facts)
    boundary = boundaries[key]
    native = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',
        sources=plan.native_sources, native_entry=binding, classpath=plan.native_classpath,
        external_bindings=plan.native_external_bindings, settings_bindings=binding.settings_bindings)
    observations = []
    for side, adapter, fixture in [('legacy', plan.original_framework, case), ('native', native, native_case or case)]:
        cache_key = digest((key, side, adapter.model_dump(mode='json'), fixture.settings))
        if cache_key not in compiled:
            compiled[cache_key] = compile_boundary_side(unit, boundary, adapter, directory / cache_key[:24], side, harness, settings=fixture.settings)
        observations.append(execute_boundary_case(compiled[cache_key], unit, boundary, adapter, fixture,
                                                  timeout=settings.case_timeout_seconds))
    return observations
