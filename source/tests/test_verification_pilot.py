"""Pilot sampling and denominators cannot silently turn missing evidence into success."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from tools.behavior_verification.boundary_contracts import boundary_contract,digest
from tools.behavior_verification.pilot_selection import select_pilot
from tools.behavior_verification.pilot_measurement import measure_pilot
from tools.behavior_verification.pilot import main
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.behavior_units import save
from models.unit_static_check_report import UnitStaticCheckReport
from test_behavior_verification_boundaries import unit,source,boundary_tool
from test_bank_boundary_harness import _prepare_bank
from test_scoped_vault_identity import scoped_mapper


def inventory(count=4):
    units=[]; boundaries={}
    for kind in ('request_unformat','response_format','configured_step'):
        for index in range(count):
            item=unit(kind,sources=[source('original','class Original {}')])
            item['unit_id']=kind+str(index); item['logical_id']=item['unit_id']
            units.append(item)
            boundaries[item['unit_id']]=boundary_contract(item).model_dump(mode='json')
    return dict(operations={'XML/Original':dict(units=units)}),dict(boundaries=boundaries,analysis_tool_hash='parser')


def test_selection_is_reproducible_keeps_incomplete_and_reports_shortfalls():
    preparation,analysis=inventory(2)
    plan=select_pilot(preparation,analysis,dataset_type='bank_demo',per_group=20)
    assert len(plan['selected_units'])==6
    assert plan['availability']['formats']['shortfall']==16
    assert plan['availability']['steps']['shortfall']==18
    assert {item['shape']['analysis_status'] for item in plan['selected_units']}=={'verification_incomplete'}
    preparation['operations']['XML/Original']['units'].reverse()
    assert plan==select_pilot(preparation,analysis,dataset_type='bank_demo',per_group=20)
    selected=select_pilot(preparation,analysis,dataset_type='production',per_group=2)
    assert len(selected['selected_units'])==4
    assert {item['kind'] for item in selected['selected_units'] if item['kind']!='configured_step'}=={'request_unformat','response_format'}


def test_selection_rejects_stale_analysis():
    preparation,analysis=inventory(1)
    next(iter(analysis['boundaries'].values()))['source_manifest_hash']='changed'
    with pytest.raises(ValueError,match='does not match'): select_pilot(preparation,analysis,dataset_type='production')


def db(tmp_path):
    conn=get_connection(str(tmp_path/'migration.db')); create_all_tables(conn)
    upsert_run(conn,run_id='pilot',run_mode='full_inventory')
    return conn


def outcome(conn,sample,status,**extra):
    receipt=dict(unit_id=sample['unit_id'],status=status,verification_version='parser-boundary-v1',
        source_manifest_hash=sample['source_manifest_hash'],configuration_hash=sample['configuration_hash'],**extra)
    save(conn,'pilot','unit_verification',sample['unit_id'],'test-only',receipt,status)


def test_metrics_preserve_pending_stale_and_unverified_acceptance(tmp_path):
    preparation,analysis=inventory(2); plan=select_pilot(preparation,analysis,dataset_type='production',per_group=20)
    conn=db(tmp_path)
    samples=plan['selected_units']
    outcome(conn,samples[0],'verification_incomplete',feedback=dict(stage='parser',errors=['Unresolved implementation']))
    outcome(conn,samples[1],'failed',error='Compile failure')
    outcome(conn,samples[2],'accepted',evidence=str(tmp_path/'missing'),report_hash='invalid')
    outcome(conn,{**samples[3],'configuration_hash':'old'},'verification_incomplete')
    result=measure_pilot(conn,plan,run_id='pilot',output_root=str(tmp_path))
    assert result['counts']==dict(verification_incomplete=1,failed=1,unverified_evidence=2,pending=2)
    assert result['rates']['accepted']==dict(numerator=0,denominator=6,percent=0.0)
    assert result['incomplete_causes']==dict(parser=1)
    assert result['literal_warnings']['percent'] is None and result['literal_warnings']['unmeasured_units']==6
    assert not result['production_pilot_completed']
    plan['selected_units'].pop()
    with pytest.raises(ValueError,match='manifest changed'): measure_pilot(conn,plan,run_id='pilot',output_root=str(tmp_path))
    conn.close()


def test_warning_rate_uses_only_complete_matching_static_measurements(tmp_path):
    preparation,analysis=inventory(1); plan=select_pilot(preparation,analysis,dataset_type='bank_demo',per_group=20)
    sample=plan['selected_units'][0]
    sample.update(literal_inventory_available=True,literal_item_ids=['literal-1'])
    plan['sample_hash']=digest({k:v for k,v in plan.items() if k!='sample_hash'})
    conn=db(tmp_path)
    folder=tmp_path/'.unit-verification/attempt/static'; folder.mkdir(parents=True)
    static=UnitStaticCheckReport(unit_id=sample['unit_id'],source_manifest_hash=sample['source_manifest_hash'],
        configuration_hash=sample['configuration_hash'],tool_hash='tool',
        literal_checks=[dict(checklist_id='literal-1',status='not_found')],
        warnings=[dict(checklist_id='literal-1',kind='missing_literal')])
    path=folder/'unit-static-checks.json'; path.write_text(static.model_dump_json())
    for item in plan['selected_units']:
        outcome(conn,item,'verification_incomplete',feedback=dict(stage='checklist',evidence=str(folder.parent)))
    # Only the first unit's static evidence matches; the others are explicitly invalid, never warning-free.
    result=measure_pilot(conn,plan,run_id='pilot',output_root=str(tmp_path))
    assert result['literal_warnings']['percent']==100 and result['literal_warnings']['measured_units']==1
    assert result['literal_warnings']['unmeasured_units']==2
    assert not result['production_pilot_completed']
    static.literal_checks=[]; path.write_text(static.model_dump_json())
    result=measure_pilot(conn,plan,run_id='pilot',output_root=str(tmp_path))
    assert result['literal_warnings']['percent'] is None
    conn.close()


def test_report_cli_is_read_only_and_fixture_results_cannot_complete_production(tmp_path,capsys):
    preparation,analysis=inventory(1); plan=select_pilot(preparation,analysis,dataset_type='bank_demo',per_group=20)
    conn=db(tmp_path)
    for sample in plan['selected_units']: outcome(conn,sample,'verification_incomplete',feedback=dict(stage='parser'))
    conn.close()
    sample_path=tmp_path/'sample.json'; sample_path.write_text(json.dumps(plan))
    database=tmp_path/'migration.db'; before=database.read_bytes()
    report=tmp_path/'report.json'
    assert main(['report','--sample',str(sample_path),'--database',str(database),'--run-id','pilot',
                 '--run-output',str(tmp_path),'--output',str(report)])==0
    result=json.loads(report.read_text())
    assert result['measurement_status']=='terminal_outcomes_recorded' and not result['production_pilot_completed']
    assert result['rates']['verification_incomplete']['percent']==100
    assert database.read_bytes()==before


def test_fresh_bank_mapper_preparation_can_supply_pilot_inventory(tmp_path,scoped_mapper,boundary_tool):
    from tools.behavior_verification.boundaries import build_boundary_report
    preparation=_prepare_bank(tmp_path,scoped_mapper)
    analysis=build_boundary_report(preparation,tool_jar=boundary_tool)
    plan=select_pilot(preparation,analysis,dataset_type='bank_demo')
    assert len(plan['selected_units'])==40 and plan['operations']
    assert plan['availability']['formats']['selected']==20 and plan['availability']['steps']['selected']==20
    assert all(item['source_manifest_hash'] and item['configuration_hash'] for item in plan['selected_units'])
    # Real inventory only: preparation cannot manufacture conversion outcomes or acceptance.
    conn=db(tmp_path)
    measured=measure_pilot(conn,plan,run_id='pilot',output_root=str(tmp_path/'generated'))
    assert measured['counts']=={'pending':40} and measured['rates']['accepted']['numerator']==0
    assert not measured['production_pilot_completed']
    import os
    export=os.environ.get('SNAPIR_PILOT_AUDIT_EXPORT')
    if export:
        folder=Path(export);folder.mkdir(parents=True,exist_ok=True)
        (folder/'sample.json').write_text(json.dumps(plan,indent=2))
        (folder/'measurement.json').write_text(json.dumps(measured,indent=2))
    conn.close()
