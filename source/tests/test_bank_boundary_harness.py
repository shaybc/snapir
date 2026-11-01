"""Compare the actual configured bank request against an explicitly labeled native fixture."""
import json
from pathlib import Path
import pytest
from test_behavior_verification_boundaries import boundary_tool
from test_scoped_vault_identity import scoped_mapper, invoke_mapper
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.unit_verification_boundary import UnitVerificationBoundary
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.controlled_inputs import generate_boundary_cases
from tools.behavior_verification.boundary_verification import verify_boundary


def test_actual_bank_request_over_50_generated_cases(boundary_tool, scoped_mapper, tmp_path):
    # Reuse the validated mapper/preparation evidence without making any AI calls.
    report_path = Path(__file__).resolve().parents[2] / 'outputs/behavior-verification-boundaries-20261027/bank-demo-boundaries/reports/3_dependency_closure_and_component_conversion/scoped_workflow_preparation.json'
    preparation = json.loads(report_path.read_text()) if report_path.is_file() else _prepare_bank(tmp_path, scoped_mapper)
    operation = preparation['operations']['INTERNET/GetAccountDetailsOp']
    request = next(item for item in operation['units'] if item['logical_id'] == 'GetAccountDetailsRQFmt')
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    for origin in operation['behavior_request']['java_origins']:
        if origin['status'] == 'verified_source': assert file_digest(Path(origin['source_file'])) == origin['source_hash']
    analysis = build_boundary_report(dict(run_id='bank-boundary-test', operations={'INTERNET/GetAccountDetailsOp':
        dict(behavior_request=operation['behavior_request'], units=[request])}), tool_jar=boundary_tool)
    boundary = UnitVerificationBoundary.model_validate(analysis['boundaries'][request['unit_id']])
    cases = generate_boundary_cases(request, boundary)
    assert len(cases) >= 50
    assert cases == generate_boundary_cases(request, boundary)
    fixture = Path(__file__).parent / 'fixtures/BankRequestBoundaryAdapter.java'
    native = BoundaryHarnessBinding(adapter_class='fixture.BankRequestBoundaryAdapter', sources=[dict(path='fixture/BankRequestBoundaryAdapter.java', content=fixture.read_text())])
    legacy = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    result = verify_boundary(request, boundary, legacy, native, cases, tmp_path / 'bank-comparison', tool=boundary_tool,
                             candidate_label='independent_native_test_fixture_not_live_AI_acceptance')
    assert result.status == 'matched_observed_cases', result.model_dump_json(indent=2)
    assert len(result.cases) >= 50
    assert any(item['legacy']['exception'] is None for item in result.cases)
    assert any(item['legacy']['exception'] is not None for item in result.cases)
    assert any({'true', 'false'} <= set(branch['observed_outcomes']) for branch in result.coverage['branches'])
    assert any(branch['unexercised_outcomes'] for branch in result.coverage['branches'])
    assert result.coverage['unresolved_edges'] and not result.exhaustive_equivalence


def _prepare_bank(tmp_path, mapper):
    """Create real Mapper/intake evidence when a prior validated local run is unavailable."""
    import shutil
    from types import SimpleNamespace
    from models.pipeline_configuration import PipelineConfiguration
    from tools.composer_mapper_tools.vault_importer import import_vault
    from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
    from tools.state_store_tools.db import get_connection, create_all_tables
    root = tmp_path / 'source'
    original = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace'
    shutil.copytree(original, root); vault = tmp_path / 'vault'
    result = invoke_mapper(mapper, root, vault)
    assert result.returncode == 0, result.stderr
    conn = get_connection(':memory:'); create_all_tables(conn)
    config = SimpleNamespace(run_id='bank-boundary-test', source_root=str(root), vault_root=str(vault),
        run_mode=SimpleNamespace(value='full_inventory'), target_channels=[], include_operations=None, exclude_operations=None)
    profile = PipelineConfiguration(source_root=str(root), conversion_strategy='behavior_units',
        scoped_java_projects={'INTERNET': 'WSBCC_INTERNET', 'IVR': 'WSBCC_IVR', 'XML': 'WSBCC_XML'})
    try:
        import_vault(conn, str(vault), config, progress=lambda _: None)
        return prepare_scoped_workflow(conn, config, profile)
    finally: conn.close()
