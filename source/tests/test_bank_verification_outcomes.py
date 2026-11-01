"""Fresh whole-bank scoped execution classifies unsupported candidates without false acceptance."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from models.native_unit_bundle import NativeUnitBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope, resolve_java_home
from runtime.scoped_native.runner import resume_scoped_pipeline
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import upsert_run, get_run
from test_scoped_vault_identity import scoped_mapper, invoke_mapper
from test_behavior_verification_boundaries import boundary_tool


def test_fresh_bank_classifies_every_unit_and_does_not_assemble_unverified_code(tmp_path, scoped_mapper, boundary_tool):
    root, vault, output = tmp_path / 'source', tmp_path / 'vault', tmp_path / 'generated'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace', root)
    mapped = invoke_mapper(scoped_mapper, root, vault)
    assert mapped.returncode == 0, mapped.stderr
    conn = get_connection(str(tmp_path / 'migration.db')); create_all_tables(conn)
    config = SimpleNamespace(run_id='bank-verification-7', source_root=str(root), vault_root=str(vault), output_root=str(output),
        run_mode=SimpleNamespace(value='full_inventory'), target_channels=[], include_operations=None, exclude_operations=None)
    upsert_run(conn, run_id=config.run_id, run_mode='full_inventory')
    import_vault(conn, str(vault), config, progress=lambda _: None)
    profile = PipelineConfiguration(source_root=str(root), conversion_strategy='behavior_units', scoped_native_mode='behavior_units_v1',
        scoped_java_projects={'INTERNET':'WSBCC_INTERNET', 'IVR':'WSBCC_IVR', 'XML':'WSBCC_XML'},
        plan_approval_policy='automatic', gate_policies={str(number):'automatic' for number in range(1,5)},
        java_version=25, java_home=resolve_java_home(25), model_provider='mock', max_agent_task_retries=1,
        classpath_jars=[], eclipse_classpath_variables={})
    requests = []
    def unresolved_candidate(instruction, encoded):
        data = json.loads(encoded); requests.append(data)
        assert data['schema']['title'] == 'NativeUnitBundle'
        assert data['verification_version'] == 'parser-boundary-v1' and 'behavior_specification' not in data
        assert data['checklist']['items'] and data['slice_sources']
        platform = data.get('testing_contract', {}).get('requirement', {}).get('requirement_id')
        requirements = {key:value for key,value in data['requirements'].items() if key != platform}
        package = data['native_package']
        main, test = 'src/main/java/' + package.replace('.', '/') + '/Unconverted.java', 'src/test/java/' + package.replace('.', '/') + '/UnconvertedTest.java'
        return NativeUnitBundle(files=[dict(path=main, content='package '+package+'; public class Unconverted { public int run(){return 0;} }'),
            dict(path=test, content='package '+package+'; public class UnconvertedTest { @org.junit.jupiter.api.Test public void placeholder(){org.junit.jupiter.api.Assertions.assertEquals(0,new Unconverted().run());} }')],
            dependencies=data['testing_contract']['dependencies'], coverage={key:[test] for key in requirements}, evidence_ids=data['evidence_ids'],
            unit_contract=dict(unit_id=data['unit_id'], apis=[dict(type_name=package+'.Unconverted', method_signatures=['public int run()'])],
                               requirements=requirements, evidence_ids=data['evidence_ids']),
            checklist_answers=dict(unit_id=data['unit_id'], source_manifest_hash=data['boundary']['source_manifest_hash'],
                configuration_hash=data['boundary']['configuration_hash'], responses=[dict(checklist_id=item['id'], status='unresolved',
                    question='Offline test deliberately supplies no native business implementation') for item in data['checklist']['items']]),
            verification_binding=dict(owner_type=package+'.Unconverted', method_name='run')).model_dump_json()
    def no_build(*args, **kwargs):
        raise AssertionError('Unresolved checklist must not reach Maven publication or assembly')
    try:
        with java_scope(profile):
            resume_scoped_pipeline(conn, config, profile, tmp_path, model_call=unresolved_candidate, context_factory=no_build)
        rows = conn.execute("SELECT identity,status,data_json FROM behavior_snapshots WHERE run_id=? AND category='unit_verification'", (config.run_id,)).fetchall()
        assert len(rows) == 83, [(row['identity'],row['status']) for row in rows]
        assert all(row['status'] in {'failed','verification_incomplete'} for row in rows)
        assert all(json.loads(row['data_json'])['verification_version'] == 'parser-boundary-v1' for row in rows)
        assert get_run(conn, config.run_id)['current_phase'] == 'conversion_units_verification_incomplete'
        reports = list(tmp_path.rglob('unit-verification-results.json'))
        assert reports
        summary = json.loads(reports[0].read_text(encoding='utf-8'))
        assert not summary['pending_unit_ids'] and summary['counts']['accepted'] == 0
        assert len(summary['units']) == 83
        import os
        export = os.environ.get('SNAPIR_BANK_VERIFICATION_AUDIT_EXPORT')
        if export:
            Path(export).write_text(json.dumps(dict(validation='offline unresolved-candidate audit; not live AI acceptance',
                model_requests=len(requests), report=summary), indent=2), encoding='utf-8')
        assert requests and all(request['schema']['title'] == 'NativeUnitBundle' for request in requests)
        assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category='operation'").fetchone()[0] == 0
        assert not list(output.rglob('src/main/java/*.java'))
    finally:
        conn.close()
