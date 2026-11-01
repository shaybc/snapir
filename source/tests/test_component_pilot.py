"""CF8 metrics never turn preparation, component counts or unverified flags into acceptance."""
import json
import logging
import sqlite3
import os
from pathlib import Path
from tools.behavior_verification.component_pilot import measure_component_run,publish_component_run,PilotMetrics
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run,update_run_status
from tools.state_store_tools.behavior_units import initialize,save
from runtime.workspace_paths import write_run_report


def pilot_state(tmp_path):
    directory=tmp_path/'bank';database=directory/'state/migration.db';database.parent.mkdir(parents=True)
    conn=get_connection(str(database));create_all_tables(conn);initialize(conn)
    upsert_run(conn,run_id='bank',run_mode='conversion')
    write_run_report(directory,'scoped_workflow_preparation.json',json.dumps(dict(operations={
        'INTERNET/Demo':dict(status='prepared',units=[dict(unit_id='unit')])})))
    write_run_report(directory,'component-generation.json',json.dumps(dict(groups={
        'root':dict(status='component_validated')},component_validated=2,reused_components=1)))
    conn.commit()
    return conn,directory


def test_component_progress_and_completed_flags_are_not_unit_acceptance(tmp_path):
    conn,_=pilot_state(tmp_path)
    update_run_status(conn,'bank','completed','migration_approved');conn.commit()
    result=measure_component_run(tmp_path,'bank')
    assert result['component_validated']==2 and result['reused_components']==1
    assert result['accepted_units']==result['accepted_operations']==0
    assert result['pending_units']==1 and not result['acceptance_complete']
    conn.close()


def test_terminal_measurement_rejects_unverified_unit_flags_without_mutating_state(tmp_path):
    conn,_=pilot_state(tmp_path)
    save(conn,'bank','unit_verification','unit','synthetic',dict(status='accepted'))
    update_run_status(conn,'bank','completed','migration_approved');conn.commit()
    live=measure_component_run(tmp_path,'bank',running=True)
    assert live['accepted_units']==1 and not live['acceptance_complete']
    terminal=measure_component_run(tmp_path,'bank',running=False)
    assert terminal['accepted_units']==0 and len(terminal['unverified_units'])==1
    assert not terminal['acceptance_complete']
    assert conn.execute("SELECT status FROM behavior_snapshots WHERE category='unit_verification'").fetchone()[0]=='accepted'
    conn.close()


def test_component_blockers_and_oversize_weights_remain_visible(tmp_path):
    conn,directory=pilot_state(tmp_path)
    write_run_report(directory,'component-generation.json',json.dumps(dict(groups={
        'root':dict(status='incomplete',reason='Indivisible source exceeds budget')},component_validated=0,reused_components=0)))
    (tmp_path/'request-sizes.jsonl').write_text(json.dumps(dict(decision='too_large',
        total=dict(characters=900001,bytes=900050,KB=900.05,MB=.90005,GB=.00090005)))+'\n')
    result=publish_component_run(tmp_path,'bank')
    assert result['blockers'][0]['detail']=='Indivisible source exceeds budget'
    assert result['request_weights']['over_budget']==1 and result['request_weights']['largest']['characters']==900001
    assert not result['acceptance_complete']
    assert (tmp_path/'acceptance-report.md').is_file() and (tmp_path/'cf8-measurement.json').is_file()
    failed=publish_component_run(tmp_path,'bank',error='Measurement unavailable')
    assert failed['error']=='Measurement unavailable' and not failed['acceptance_complete']
    conn.close()


def test_metrics_capture_weights_and_real_executor_events_without_prompt_text(tmp_path):
    handler=PilotMetrics(tmp_path)
    weights=dict(stage='initial_budget_check',decision='fits_budget',total=dict(characters=42,bytes=42))
    handler.emit(logging.LogRecord('runtime.behavior_conversion.request_size',logging.INFO,'',1,'Model request size: %s',(json.dumps(weights),),None))
    record=logging.LogRecord('runtime.model_execution.adk_executor',logging.INFO,'',1,'Model interaction started',(),None)
    record.model_interaction_boundary='start';handler.emit(record)
    handler.emit(logging.LogRecord('runtime.model_execution.adk_executor',logging.INFO,'',1,
        'Model execution attempt %s/%s using %s (%s).%s',(1,4,'test-model','gemini',''),None))
    handler.emit(logging.LogRecord('other',logging.INFO,'',1,'private original Java source and credential',(),None))
    assert json.loads((tmp_path/'request-sizes.jsonl').read_text())['total']['characters']==42
    events=[json.loads(line) for line in (tmp_path/'model-interactions.jsonl').read_text().splitlines()]
    assert [event['event'] for event in events]==['interaction_start','transport_attempt']
    assert 'private original' not in ''.join(path.read_text() for path in tmp_path.glob('*.jsonl'))


def test_process_probe_queries_its_own_liveness_without_signalling():
    from tools.behavior_verification.component_pilot_run import process_alive
    assert process_alive(os.getpid()) is True
