"""Measure selected unit outcomes without promoting preparation or fixture evidence to acceptance."""
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace
from models.unit_static_check_report import UnitStaticCheckReport
from runtime.behavior_conversion.verification_state import _require_evidence
from tools.behavior_verification.pilot_selection import validate_pilot


def measure_pilot(conn, plan, *, run_id, output_root):
    """Read one run's latest receipts; pending, stale evidence and unmeasured literals stay explicit."""
    validate_pilot(plan)
    if conn.execute('SELECT 1 FROM runs WHERE run_id=?',(run_id,)).fetchone() is None:
        raise ValueError('Pilot run does not exist: ' + run_id)
    rows = conn.execute("SELECT identity,status,data_json FROM behavior_snapshots WHERE run_id=? AND category='unit_verification'",(run_id,)).fetchall()
    current={row['identity']:row for row in rows}
    units=[]
    for sample in plan['selected_units']:
        item=dict(unit_id=sample['unit_id'],kind=sample['kind'],operation=sample['operation'],status='pending',
                  literal_measurement='not_measured',literal_warning_ids=[])
        row=current.get(sample['unit_id'])
        if row:
            try:
                receipt=json.loads(row['data_json'])
                if receipt.get('verification_version') not in {'parser-boundary-v1','executable-boundary-v1'} or any(
                    receipt.get(key)!=sample[key] for key in ('source_manifest_hash','configuration_hash')):
                    raise ValueError('Outcome is missing matching original source/configuration identities')
                if row['status']!=receipt.get('status') or row['status'] not in {'accepted','failed','verification_incomplete'}:
                    raise ValueError('Outcome status is inconsistent')
                if row['status']=='accepted': _require_evidence(SimpleNamespace(output_root=output_root),sample['unit_id'],receipt)
                item['status']=row['status']
                if row['status']!='accepted':
                    feedback=receipt.get('feedback',{})
                    item['cause']=dict(stage=feedback.get('stage','generation_or_validation'),
                        detail=feedback.get('errors') or feedback.get('issues') or receipt.get('error','Unspecified failure'))
                _literals(item,receipt,sample,Path(output_root))
            except (ValueError, OSError, KeyError, TypeError) as error:
                item.update(status='unverified_evidence',evidence_issue=str(error))
        units.append(item)
    counts=Counter(item['status'] for item in units)
    measured=[item for item in units if item['literal_measurement']=='measured']
    warned=[item for item in measured if item['literal_warning_ids']]
    n=len(units)
    rates={status:dict(numerator=counts[status],denominator=n,percent=round(100*counts[status]/n,2))
           for status in ('accepted','failed','verification_incomplete')}
    causes=Counter(item['cause']['stage'] for item in units if item['status']=='verification_incomplete')
    complete=not counts['pending'] and not counts['unverified_evidence']
    return dict(schema_version='verification-pilot-measurement-v1',run_id=run_id,sample_hash=plan['sample_hash'],
        dataset_type=plan['dataset_type'], production_pilot_completed=plan['dataset_type']=='production' and complete,
        measurement_status='terminal_outcomes_recorded' if complete else 'incomplete',
        sample_size=n,sample_availability=plan['availability'],counts=dict(counts),rates=rates,incomplete_causes=dict(causes),
        literal_warnings=dict(units_with_warnings=len(warned),measured_units=len(measured),
            unmeasured_units=n-len(measured),percent=round(100*len(warned)/len(measured),2) if measured else None,
            denominator='units with a matching persisted static report; unmeasured units are not assumed warning-free'),
        by_kind={kind:dict(Counter(item['status'] for item in units if item['kind']==kind)) for kind in sorted({item['kind'] for item in units})},
        log_replay='not_run; optional and requires approved complete request/response logs',
        acceptance_basis='persisted technical receipts, checked against retained evidence; never preparation or mutation score',units=units)


def _literals(item, receipt, sample, output_root):
    if receipt.get('verification_version')=='executable-boundary-v1': return
    folder=receipt.get('evidence') or receipt.get('feedback',{}).get('evidence')
    if not folder: return
    folder=Path(folder).resolve()
    root=(output_root/'.unit-verification').resolve()
    if not folder.is_relative_to(root): raise ValueError('Static evidence lies outside this run output')
    path=folder/('static-observed' if item['status']=='accepted' else 'static')/'unit-static-checks.json'
    if not path.is_file(): return
    report=UnitStaticCheckReport.model_validate_json(path.read_text(encoding='utf-8'))
    if report.unit_id!=sample['unit_id'] or any(getattr(report,key)!=sample[key] for key in ('source_manifest_hash','configuration_hash')):
        raise ValueError('Static evidence does not match sampled source/configuration')
    if not sample['literal_inventory_available'] or not report.tool_hash: return
    checked={check['checklist_id'] for check in report.literal_checks}
    excluded={decision['checklist_id'] for decision in report.decisions if decision['status']=='not_applicable'}
    if set(sample['literal_item_ids']) != checked | (excluded & set(sample['literal_item_ids'])): return
    item.update(literal_measurement='measured',literal_warning_ids=sorted({warning['checklist_id'] for warning in report.warnings
        if warning.get('kind')=='missing_literal'}))
