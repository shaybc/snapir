"""Prepare generated bindings and fixtures without Java generation or conversion state writes."""
import json
from models.format_comparison_plan import FormatComparisonPlan
from runtime.format_comparison.bindings import propose_bindings
from runtime.format_comparison.context_discovery import discover_context


def prepare_plan(label, scope, unit, native_sources, cases, profile, directory, *, entries=None, model_call=None):
    """Use existing bindings first, with bounded AI discovery/proposal only when explicitly supplied.

    Cases are baseline input fixtures or a callback receiving validated entries and discovery.
    This permits converter-owned input generation without accepting executable AI adapter code.
    Missing wiring produces a retained preparation report and no fabricated plan.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if not profile.format_comparison.enabled:
        raise ValueError('Diagnostic preparation is disabled')
    unresolved = []
    discovery = None
    if not entries:
        if model_call is None:
            unresolved.append('Native API binding unavailable; provide metadata or an explicit mapping-only model call')
        else:
            entries, unresolved = propose_bindings(unit, native_sources, model_call, profile.format_comparison, directory / 'binding-proposal')
    if model_call is not None:
        discovery = discover_context(unit, model_call, profile.format_comparison, directory / 'context-discovery',
            directions=sorted({entry.direction for entry in entries.values()}) if entries else None)
    report = dict(status='preparing' if entries else 'comparison_unavailable', unresolved=unresolved,
                  acceptance_changed=False, java_regenerated=False)
    (directory / 'preparation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not entries:
        return None, report
    try:
        inputs = cases(entries, discovery) if callable(cases) else cases
        plan = FormatComparisonPlan(label=label, scope=scope, original_unit=unit, native_sources=native_sources,
                                    entries=entries, cases=inputs, **({'discovery': discovery} if discovery else {}))
    except (ValueError, TypeError, KeyError) as error:
        report.update(status='comparison_unavailable', unresolved=[*unresolved, 'Fixture preparation failed: ' + type(error).__name__])
        (directory / 'preparation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return None, report
    if unresolved:
        plan.discovery.unresolved.extend(unresolved)
    (directory / 'prepared-plan.json').write_text(plan.model_dump_json(indent=2), encoding='utf-8')
    report['status'] = 'prepared'
    (directory / 'preparation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return plan, report
