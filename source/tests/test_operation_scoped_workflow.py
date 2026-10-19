"""Verify operation-scoped integration with existing packaging and finalization."""

from runtime.service_generation import run_service_generation
from runtime.finalization import run_finalization
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_service_generation import ready, run, wrappers, Verifier
from tests.runtime.test_finalization import setup_final
from tools.state_store_tools.operation_progress import initialize_progress, progress_rows
from tools.state_store_tools.runs import get_run


def test_packaging_does_not_include_previously_completed_operations(tmp_path):
    setup = ready(tmp_path)
    assert run(tmp_path, setup) == 'validation_evidence_pending'
    conn, config, profile, plan, _ = setup
    conn.execute('''INSERT INTO service_generation_checkpoints
        (run_id,operation_id,channel,input_hash,project_hash,attempts,validation_json)
        VALUES (?,?,?,?,?,?,?)''', (config.run_id, 'EarlierCompletedOperation', 'INTERNET', 'other', 'other', 1, '{}'))
    conn.commit()
    result = run_service_generation(conn, config, profile, plan, tmp_path,
        gate_checker=lambda: 'service_generation_pending', generator=wrappers,
        context_factory=lambda settings, project, artifact: ManagedBuildContext(str(project / 'pom.xml'), Verifier()),
        operation_scoped=True)
    assert result == 'validation_evidence_pending'


def test_finalization_completes_operation_without_completing_run(tmp_path):
    conn, config, profile, plan, _ = setup_final(tmp_path, True)
    from tools.workspace_intake_tools.run_factory import persist_run_config
    persist_run_config(conn, config)
    profile.gate_policies['4'] = 'automatic'
    initialize_progress(conn, config.run_id, ['INTERNET/Op', 'INTERNET/Next'])
    phase = run_finalization(conn, config, profile, plan, tmp_path, complete_run=False)
    assert phase == 'operation_workflow_completed'
    assert get_run(conn, config.run_id)['status'] == 'paused'
    assert [row['status'] for row in progress_rows(conn, config.run_id)] == ['workflow_completed','pending']
