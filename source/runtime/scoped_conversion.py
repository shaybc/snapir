"""Publish scoped preparation evidence while keeping native generation explicitly gated."""

import json
import logging
from time import perf_counter

from runtime.workspace_paths import write_run_report
from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow, GENERATION_GATE
from tools.state_store_tools.runs import update_run_status


def prepare_scoped_runtime(conn, config, profile, directory, *, plan=None):
    """Prepare exact imported/packet selection before any legacy reads, gates, or model calls."""
    selected = None
    if plan is not None:
        if plan.run_id != config.run_id:
            raise ValueError('Execution plan belongs to another run')
        selected = {packet.channel + '/' + packet.operation_id for batch in plan.batches for packet in batch.task_packets}
    started = perf_counter()
    logging.getLogger(__name__).info('Starting scoped preparation acceptance measurement: %s', config.run_id)
    try:
        report = prepare_scoped_workflow(conn, config, profile, selected=selected)
    except (ValueError, OSError) as exc:
        report = dict(run_id=config.run_id, conversion_enabled=False, generation_gate=GENERATION_GATE,
                      preparation_error=str(exc), operations={})
        from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale
        if isinstance(exc, ScopedCheckpointStale):
            report['stale_contexts'] = exc.affected
    elapsed = perf_counter() - started
    write_run_report(directory, 'scoped_workflow_preparation.json', json.dumps(report, indent=2))
    from runtime.scoped_acceptance import preparation_acceptance
    acceptance = preparation_acceptance(conn, config.run_id, report, elapsed)
    write_run_report(directory, 'scoped_acceptance.json', json.dumps(acceptance, indent=2))
    logging.getLogger(__name__).info('Scoped preparation %s: %s/%s contexts prepared in %.3fs; native acceptance remains pending',
        acceptance['preparation_status'], acceptance['counts']['prepared_contexts'],
        acceptance['counts']['attempted_contexts'], acceptance['elapsed_seconds'])
    phase = 'conversion_scoped_stale' if report.get('stale_contexts') else 'conversion_scoped_gated'
    update_run_status(conn, config.run_id, 'blocked', phase)
    return report
