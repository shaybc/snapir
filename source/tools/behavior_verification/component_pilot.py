"""Measure live component-first runs without treating preparation or cached flags as acceptance."""
import json
import logging
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from runtime.workspace_paths import run_report_path


class PilotMetrics(logging.Handler):
    """Persist existing request-weight and executor events, excluding prompts and credentials."""
    def __init__(self, directory):
        super().__init__()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        try:
            if record.name == 'runtime.behavior_conversion.request_size' and record.args:
                value = json.loads(record.args[0])
                filename = 'request-sizes.jsonl'
            elif record.name == 'runtime.model_execution.adk_executor':
                boundary = getattr(record,'model_interaction_boundary',None)
                if boundary:
                    value = dict(event='interaction_'+boundary)
                elif record.msg.startswith('Model execution attempt '):
                    value = dict(event='transport_attempt',attempt=record.args[0],limit=record.args[1],
                        model=record.args[2],provider=record.args[3])
                else:
                    return
                from runtime.model_execution.component_progress import COMPONENT_LABEL
                value['component'] = COMPONENT_LABEL.get()
                filename = 'model-interactions.jsonl'
            else:
                return
            value = dict(recorded_at=datetime.now(timezone.utc).isoformat(),**value)
            with (self.directory/filename).open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(value,ensure_ascii=True)+'\n')
        except (ValueError,TypeError,OSError):
            self.handleError(record)


def _json_lines(path):
    """Tolerate only a partial final event while its producer is still writing."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding='utf-8').splitlines()
    result = []
    for index,line in enumerate(lines):
        try:
            result.append(json.loads(line))
        except ValueError:
            if index != len(lines)-1:
                raise
    return result


def measure_component_run(base, run_id, *, running=False):
    """Report persisted outcomes; validate every accepted unit/operation at terminal measurement."""
    base = Path(base).resolve()
    directory = base/run_id
    result = dict(schema_version='component-first-pilot-v1',run_id=run_id,dataset_type='bank_demo',
        recorded_at=datetime.now(timezone.utc).isoformat(),process_running=running,status='starting',phase='fresh_intake',
        total_units=0,total_operations=0,accepted_units=0,accepted_operations=0,failed_units=0,incomplete_units=0,
        unverified_units=[],unverified_operations=[],component_statuses={},component_validated=0,reused_components=0,
        model_tasks=0,model_interactions=0,transport_attempts=0,acceptance_complete=False,blockers=[])
    prep_path = run_report_path(directory,'scoped_workflow_preparation.json')
    units,operations = {},{}
    if prep_path.is_file():
        operations = json.loads(prep_path.read_text(encoding='utf-8')).get('operations',{})
        units = {unit['unit_id']:unit for item in operations.values() for unit in item.get('units',[])}
        result.update(total_units=len(units),total_operations=len(operations))
        result['blockers'].extend(dict(operation=key,stage='preparation',detail=item.get('issues',item.get('status')))
            for key,item in operations.items() if item.get('status')!='prepared')
    database = directory/'state/migration.db'
    if database.is_file():
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT status,current_phase FROM runs WHERE run_id=?',(run_id,)).fetchone()
            if row:
                result.update(status=row['status'],phase=row['current_phase'])
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'behavior_attempts' in tables:
                attempts = conn.execute('SELECT category,count(*) AS n FROM behavior_attempts WHERE run_id=? GROUP BY category',(run_id,)).fetchall()
                result['recorded_attempts_by_category'] = {row['category']:row['n'] for row in attempts}
                result['model_tasks'] = conn.execute('SELECT count(*) FROM (SELECT DISTINCT category,identity FROM behavior_attempts WHERE run_id=?)',(run_id,)).fetchone()[0]
            if 'behavior_snapshots' in tables:
                outcomes = conn.execute("SELECT identity,status,data_json FROM behavior_snapshots WHERE run_id=? AND category='unit_verification'",(run_id,)).fetchall()
                outcomes = [row for row in outcomes if row['identity'] in units]
                config = SimpleNamespace(run_id=run_id,output_root=str(directory/'generated'))
                for outcome in outcomes:
                    status = outcome['status']
                    if status=='accepted' and not running:
                        try:
                            from runtime.behavior_conversion.verification_state import _require_evidence
                            from runtime.component_conversion.unit_artifacts import require_unit_components
                            receipt = json.loads(outcome['data_json'])
                            _require_evidence(config,outcome['identity'],receipt)
                            if not receipt.get('component_receipt'):
                                raise ValueError('Missing final transitive component receipt')
                            require_unit_components(conn,config,outcome['identity'],receipt['candidate_hash'],revision=receipt['component_receipt'])
                        except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as error:
                            result['unverified_units'].append(dict(unit_id=outcome['identity'],detail=str(error)))
                            continue
                    key = {'accepted':'accepted_units','failed':'failed_units','verification_incomplete':'incomplete_units'}.get(status)
                    if key:
                        result[key] += 1
                    if status!='accepted':
                        data = json.loads(outcome['data_json'])
                        result['blockers'].append(dict(unit_id=outcome['identity'],stage='unit_verification',
                            detail=data.get('feedback') or data.get('error',status)))
                if operations:
                    records = conn.execute("SELECT identity,data_json FROM behavior_snapshots WHERE run_id=? AND category='operation' AND status='accepted'",(run_id,)).fetchall()
                    for record in records:
                        if record['identity'] not in operations:
                            continue
                        if running:
                            # No acceptance claim is made from unchecked live flags.
                            continue
                        try:
                            from runtime.behavior_conversion.verification_state import require_unit_receipts
                            from runtime.behavior_conversion.bundle_output import verify_manifest
                            data = json.loads(record['data_json'])
                            if not data.get('component_first') or not data.get('bindings') or not data.get('files'):
                                raise ValueError('Missing component-first operation evidence')
                            if not data['review']['approved'] or data['review']['issues'] or data['review']['unresolved_questions']:
                                raise ValueError('Operation review has not passed')
                            project = Path(data['project']).resolve()
                            if not project.is_relative_to(Path(config.output_root).resolve()):
                                raise ValueError('Operation project is outside this run')
                            verify_manifest(project,data['files'])
                            require_unit_receipts(conn,config,data)
                            result['accepted_operations'] += 1
                        except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as error:
                            result['unverified_operations'].append(dict(operation=record['identity'],detail=str(error)))
    components_path = run_report_path(directory,'component-generation.json')
    if components_path.is_file():
        components = json.loads(components_path.read_text(encoding='utf-8'))
        result.update(component_statuses=dict(Counter(item['status'] for item in components['groups'].values())),
            component_validated=components['component_validated'],reused_components=components['reused_components'])
        result['blockers'].extend(dict(component_group=key,stage='component_generation',detail=value.get('reason',value['status']))
            for key,value in components['groups'].items() if value['status'] in {'incomplete','deferred'})
        if components.get('fatal_error'):
            result['blockers'].append(dict(stage='component_generation',detail=components['fatal_error']))
    sizes = _json_lines(base/'request-sizes.jsonl')
    weights = [item['total'] for item in sizes]
    result['request_weights'] = dict(measurements=len(sizes),over_budget=sum(item['decision']=='too_large' for item in sizes),
        largest=max(weights,key=lambda item:item['characters']) if weights else None,
        note='Full application JSON and instructions, including schema/files; budget checks include candidates not sent. Not token/HTTP sizes.')
    events = _json_lines(base/'model-interactions.jsonl')
    result['model_interactions'] = sum(item['event']=='interaction_start' for item in events)
    result['transport_attempts'] = sum(item['event']=='transport_attempt' for item in events)
    result['pending_units'] = len(units)-sum(result[key] for key in ('accepted_units','failed_units','incomplete_units'))-len(result['unverified_units'])
    result['acceptance_complete'] = bool(not running and result['status']=='completed' and units and operations
        and result['accepted_units']==len(units) and result['accepted_operations']==len(operations)
        and not result['unverified_units'] and not result['unverified_operations'] and not result['blockers'])
    result['acceptance_basis'] = 'Final unit static/build/boundary and transitive component receipts plus checked operation artifacts; component/fixture progress is not acceptance.'
    return result


def publish_component_run(base, run_id, *, running=False, error=None):
    """Atomically publish a concise user report and its exact machine-readable evidence."""
    result = measure_component_run(base,run_id,running=running)
    if error:
        result.update(error=error,acceptance_complete=False)
    base = Path(base)
    for name in ('cf8-measurement.json','live-status.json'):
        temporary = base/(name+'.'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(result,indent=2,ensure_ascii=True),encoding='utf-8')
        temporary.replace(base/name)
    (base/'acceptance-report.md').write_text('# Component-first bank-demo acceptance\n\n'
        + f"Status: {result['status']}; phase: {result['phase']}.\n\n"
        + f"Accepted units: {result['accepted_units']}/{result['total_units']}; accepted operations: {result['accepted_operations']}/{result['total_operations']}.\n\n"
        + f"Failed: {result['failed_units']}; incomplete: {result['incomplete_units']}; pending: {result['pending_units']}.\n\n"
        + f"Validated components: {result['component_validated']}; reused: {result['reused_components']}.\n\n"
        + f"Model interactions: {result['model_interactions']}; transport attempts: {result['transport_attempts']}.\n\n"
        + f"End-to-end acceptance complete: {str(result['acceptance_complete']).lower()}.\n\n"
        + 'All technical checks remain required. Bank-demo results do not establish enterprise/production acceptance.\n',encoding='utf-8')
    return result
