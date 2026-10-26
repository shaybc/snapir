"""Bind the existing plan gate and CLI to qualified selected-context evidence."""

import json

from runtime.workspace_paths import write_run_report, run_report_path
from tools.state_store_tools.runs import update_run_status


def _snapshot(conn, config, profile, plan):
    from tools.conversion_tools.scoped_reuse.state import checkpoints
    from tools.conversion_tools.scoped_reuse.checkpoint import validate_checkpoints
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from runtime.java_toolchain import java_scope
    keys = {packet.channel + '/' + packet.operation_id for batch in plan.batches for packet in batch.task_packets}
    with java_scope(profile):
        classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    validate_checkpoints(conn, config, profile, classpath, keys)
    proof = {item.operation_key: item.fingerprint for item in checkpoints(conn, config.run_id).values()
             if item.operation_key in keys}
    return dict(capability='scoped-behavior-v1', plan=plan.model_dump(mode='json'), checkpoints=proof,
                approval_policy=profile.plan_approval_policy)


def _render(snapshot):
    return '# Qualified native conversion plan\n\n' + json.dumps(snapshot, indent=2, sort_keys=True) + '\n'


def approve_plan(conn, config, profile, directory, plan):
    """Publish exact evidence and stop before generation when human approval is pending."""
    from runtime.human_gates import evaluate_gate
    from runtime.intake_plan import PLAN_GATE
    snapshot = _snapshot(conn, config, profile, plan)
    report = _render(snapshot)
    conn.execute('CREATE TABLE IF NOT EXISTS scoped_native_plans (run_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, report TEXT NOT NULL)')
    with conn:
        conn.execute('INSERT OR REPLACE INTO scoped_native_plans VALUES (?,?,?)',
                     (config.run_id, json.dumps(snapshot, sort_keys=True), report))
    write_run_report(directory, 'conversion_plan.json', json.dumps(snapshot, indent=2, sort_keys=True))
    write_run_report(directory, 'conversion_plan.md', report)
    decision = evaluate_gate(conn, config.run_id, PLAN_GATE, report, profile.plan_approval_policy, True)
    if decision != 'approved':
        update_run_status(conn, config.run_id, 'stopped' if decision == 'rejected' else 'paused',
                          'conversion_plan_' + decision)
    return decision == 'approved'


def checked_report(conn, config, profile, directory):
    """Validate displayed scoped plan and fresh checkpoints before a CLI decision."""
    from models.migration_models import MigrationPlan
    row = conn.execute('SELECT snapshot_json,report FROM scoped_native_plans WHERE run_id=?', (config.run_id,)).fetchone()
    plan = conn.execute('SELECT plan_json FROM migration_plans WHERE run_id=? ORDER BY updated_at DESC LIMIT 1', (config.run_id,)).fetchone()
    if row is None or plan is None:
        raise ValueError('Qualified conversion plan is unavailable')
    snapshot = _snapshot(conn, config, profile, MigrationPlan.model_validate_json(plan[0]))
    report = _render(snapshot)
    if json.loads(row[0]) != snapshot or row[1] != report or run_report_path(directory, 'conversion_plan.md').read_text(encoding='utf-8') != report or json.loads(run_report_path(directory, 'conversion_plan.json').read_text(encoding='utf-8')) != snapshot:
        raise ValueError('Qualified conversion plan changed; refresh and approve the revised plan')
    return report
