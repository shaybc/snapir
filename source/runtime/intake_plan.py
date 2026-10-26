"""Produce intake's dependency-safe plan and reuse existing content-bound approval."""

import hashlib
import json
from pathlib import Path

from models.migration_models import MigrationPlan
from runtime.human_gates import evaluate_gate, record_decision
from runtime.workspace_paths import write_run_report, run_report_path
from tools.operation_call_tools.ordering import ordered_operations, operation_waves
from tools.state_store_tools.operation_calls import load_graph
from tools.state_store_tools.runs import update_run_status

# A separate key in the existing decision store, leaving conversion gates 1–4 intact.
PLAN_GATE = 0


def _preflight(conn, run_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_dependency_preflights'").fetchone():
        return None
    row = conn.execute('SELECT report_json FROM operation_dependency_preflights WHERE run_id=?', (run_id,)).fetchone()
    if not row:
        return None
    result = json.loads(row[0])
    if result['blockers']:
        raise ValueError('Dependency preflight is blocked; refresh intake before planning')
    return result


def dependency_plan_context(conn, run_id):
    """Calculate a stable dependency order using only included operations and published boundaries.

    Older runs without preflight retain their existing planning behavior.
    """
    preflight = _preflight(conn, run_id)
    if preflight is None:
        return None
    selected = sorted(row[0] + '/' + row[1] for row in conn.execute(
        'SELECT channel,operation_id FROM operations WHERE run_id=?', (run_id,)))
    if selected != preflight['selected']:
        raise ValueError('Conversion scope changed; refresh intake dependency checks')
    graph = load_graph(conn, run_id)
    if graph is None or not selected:
        raise ValueError('Mapped operations and a nonempty scope are required')
    reused = preflight['reused_services']
    included = set(selected)
    effective = dict(operations={key: value for key, value in graph['operations'].items() if key in included},
                     calls=[], issues=[])
    effective['operations'].update({key: {} for key in reused if key not in included})
    for call in graph['calls']:
        if call['caller'] in included:
            if call['callee'] not in effective['operations']:
                raise ValueError('Required operation changed; refresh intake: ' + call['callee'])
            effective['calls'].append(call)
    for issue in graph['issues']:
        if issue['operation'] not in included:
            continue
        if issue.get('callee') in reused:
            effective['calls'].append(dict(issue, caller=issue['operation']))
        else:
            effective['issues'].append(issue)
    order = ordered_operations(effective, selected, reused)
    waves = operation_waves(effective)
    return dict(order=order, operations=[dict(operation=key, **waves[key]) for key in order],
                graph=effective, preflight=preflight)


def validate_dependency_order(conn, run_id, plan):
    """Reject any plan/pilot that changes the dependency-safe intake order."""
    try:
        context = dependency_plan_context(conn, run_id)
    except ValueError as exc:
        return [str(exc)]
    if context is None:
        return []
    actual = [packet.channel + '/' + packet.operation_id for batch in plan.batches for packet in batch.task_packets]
    return [] if actual == context['order'] else ['Plan must preserve the complete dependency-first intake order across and within batches']


def has_intake_plan(conn, run_id):
    """Detect new plan checkpoints without changing preexisting runs."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='intake_conversion_plans'").fetchone():
        return False
    return conn.execute('SELECT 1 FROM intake_conversion_plans WHERE run_id=?', (run_id,)).fetchone() is not None


def _snapshot(conn, config, profile, plan):
    context = dependency_plan_context(conn, config.run_id)
    if context is None:
        raise ValueError('Intake dependency checks are required before plan approval')
    from tools.converted_service_registry_tools.location import resolve_registry_settings
    from tools.converted_service_registry_tools.registry import open_registry, get_service
    application_id, registry_path = resolve_registry_settings(profile)
    registry = open_registry(registry_path)
    try:
        for key, saved in context['preflight']['reused_services'].items():
            channel, operation = key.split('/', 1)
            current = get_service(registry, application_id, channel, operation, api_revision=saved['api_revision'])
            if current is None or current.model_dump(mode='json') != saved:
                raise ValueError('Published API changed; refresh intake before approving: ' + key)
            if profile.deployment_environment not in saved['addresses']:
                raise ValueError('Published API has no address configuration for the selected environment: ' + key)
    finally:
        registry.close()
    errors = validate_dependency_order(conn, config.run_id, plan)
    if errors:
        raise ValueError('; '.join(errors))
    notes = {}
    root = Path(config.vault_root).resolve()
    paths = {value.get('note') for key, value in context['graph']['operations'].items() if key in context['order']}
    paths.update(call.get('note') for call in context['graph']['calls'])
    for relative in sorted(path for path in paths if path):
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Plan evidence is unavailable; refresh intake: ' + relative)
        notes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(plan=plan.model_dump(mode='json'), dependency_context=context, evidence_hashes=notes,
                application_id=application_id, registry_path=str(registry_path),
                approval_policy=profile.plan_approval_policy, deployment_environment=profile.deployment_environment)


def _render(snapshot):
    context = snapshot['dependency_context']
    lines = ['# Conversion plan', '', 'Approval applies to this complete scope, order and dependency evidence.', '',
             '| Order | Wave | Operation | Direct prerequisites |', '|---|---|---|---|']
    for index, item in enumerate(context['operations'], 1):
        lines.append(f"| {index} | {item['wave']} | {item['operation']} | " + ', '.join(item['prerequisites']) + ' |')
    lines.extend(['', '## Reused published services', ''])
    reused = context['preflight']['reused_services']
    lines.extend('- ' + key + ': revision ' + value['api_revision'] for key, value in sorted(reused.items()))
    if not reused:
        lines.append('None.')
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    lines.extend(['', '## Approval evidence', '',
                  'Full plan, graph, scope, reused API contracts and note hashes: [conversion_plan.json](conversion_plan.json).',
                  '', 'Evidence fingerprint: `' + digest + '`', ''])
    return '\n'.join(lines)


def prepare_intake_plan(conn, config, profile, directory, operations):
    """Use the existing planner and persist its reviewable intake plan before execution."""
    from runtime.planning import prepare_plan
    update_run_status(conn, config.run_id, 'in_progress', 'planning')
    plan = prepare_plan(conn, config, profile, operations)
    snapshot = _snapshot(conn, config, profile, plan)
    report = _render(snapshot)
    conn.execute('CREATE TABLE IF NOT EXISTS intake_conversion_plans (run_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, report TEXT NOT NULL)')
    with conn:
        conn.execute('INSERT OR REPLACE INTO intake_conversion_plans VALUES (?,?,?)',
                     (config.run_id, json.dumps(snapshot, sort_keys=True), report))
    write_run_report(directory, 'conversion_plan.json', json.dumps(snapshot, indent=2, sort_keys=True))
    write_run_report(directory, 'conversion_plan.md', report)
    resume_intake_plan(conn, config, profile, directory)
    print('Conversion plan: ' + str(run_report_path(directory, 'conversion_plan.md')))
    return plan


def _checked_report(conn, config, profile, directory):
    from tools.conversion_tools.scoped_workflow.preparation import is_scoped_run
    if is_scoped_run(conn, config.run_id):
        from runtime.scoped_native.plan_approval import checked_report
        return checked_report(conn, config, profile, directory)
    row = conn.execute('SELECT snapshot_json,report FROM intake_conversion_plans WHERE run_id=?', (config.run_id,)).fetchone()
    if row is None:
        raise ValueError('No intake conversion plan exists')
    saved, report = json.loads(row[0]), row[1]
    current_plan = conn.execute('SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1', (config.run_id,)).fetchone()
    if current_plan is None:
        raise ValueError('Saved migration plan is unavailable')
    current = _snapshot(conn, config, profile, MigrationPlan.model_validate_json(current_plan[0]))
    if current != saved or report != _render(saved):
        raise ValueError('Conversion plan evidence changed; refresh intake and approve the revised plan')
    if run_report_path(directory, 'conversion_plan.md').read_text(encoding='utf-8') != report:
        raise ValueError('Displayed conversion plan changed; refresh intake before approval')
    if json.loads(run_report_path(directory, 'conversion_plan.json').read_text(encoding='utf-8')) != saved:
        raise ValueError('Displayed conversion plan JSON changed; refresh intake before approval')
    return report


def resume_intake_plan(conn, config, profile, directory):
    """Evaluate the separate plan gate; stop at the future sequential-wrapper handoff."""
    try:
        report = _checked_report(conn, config, profile, directory)
    except (ValueError, OSError):
        update_run_status(conn, config.run_id, 'blocked', 'conversion_plan_blocked')
        raise
    decision = evaluate_gate(conn, config.run_id, PLAN_GATE, report, profile.plan_approval_policy, True)
    update_run_status(conn, config.run_id, 'paused' if decision != 'rejected' else 'stopped',
                      'conversion_plan_' + decision)
    return decision


def record_plan_decision(conn, config, profile, directory, decision):
    """Record a human plan decision only while all displayed evidence still matches."""
    try:
        report = _checked_report(conn, config, profile, directory)
    except (ValueError, OSError):
        update_run_status(conn, config.run_id, 'blocked', 'conversion_plan_blocked')
        raise
    record_decision(conn, config.run_id, PLAN_GATE, report, decision)
