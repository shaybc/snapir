"""Phase 6: each compilable planted defect must fail at the real bank unit boundary."""
import hashlib
import json
from pathlib import Path
import pytest
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.unit_verification_boundary import UnitVerificationBoundary
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_verification import verify_boundary
from test_behavior_verification_boundaries import boundary_tool
from test_scoped_vault_identity import scoped_mapper
from test_bank_boundary_harness import _prepare_bank
from bank_seeded_defect_cases import native_binding, request_cases, response_cases, MUTATIONS, seed_defect


@pytest.fixture(scope='module')
def bank_seed_controls(boundary_tool, scoped_mapper, tmp_path_factory):
    """Fresh Mapper/preparation evidence, then passing controls before any native source mutation."""
    directory = tmp_path_factory.mktemp('bank-seeded-defects')
    preparation = _prepare_bank(directory, scoped_mapper)
    selections = [('INTERNET/GetAccountDetailsOp', 'GetAccountDetailsRQFmt'),
                  ('INTERNET/GetClientLinksOp', 'StandardErrorRSFmt')]
    operations, units = {}, {}
    for operation, name in selections:
        prepared = preparation['operations'][operation]
        unit = next(unit for unit in prepared['units'] if unit['logical_id'] == name)
        operations[operation] = dict(behavior_request=prepared['behavior_request'], units=[unit])
        units[unit['kind']] = unit
    analysis = build_boundary_report(dict(run_id='bank-seeded-defects', operations=operations), tool_jar=boundary_tool)
    assert analysis['counts'] == dict(total=2, identified=2, incomplete=0)
    legacy = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    controls = {}
    for kind, unit in units.items():
        boundary = UnitVerificationBoundary.model_validate(analysis['boundaries'][unit['unit_id']])
        assert boundary.parser_checklist.status == 'extracted'
        native = native_binding(kind)
        cases = request_cases() if kind == 'request_unformat' else response_cases()
        report = verify_boundary(unit, boundary, legacy, native, cases, directory / ('control-' + kind),
            tool=boundary_tool, candidate_label='independent_native_test_fixture_not_live_AI_acceptance')
        assert report.status == 'matched_observed_cases', report.model_dump_json(indent=2)
        assert len(report.cases) == len(cases) and not report.unexecuted_case_ids
        assert not report.acceptance_gate_enabled and not report.exhaustive_equivalence
        controls[kind] = dict(unit=unit, boundary=boundary, legacy=legacy, native=native, cases=cases, report=report)
    summary = dict(schema_version='bank-seeded-defects-v1', live_conversion_acceptance=False,
        controls={kind: dict(status=item['report'].status, cases=len(item['cases']),
            report='control-' + kind + '/boundary-comparison.json') for kind, item in controls.items()}, mutants={})
    summary_path = directory / 'seeded-defects-summary.json'
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return dict(directory=directory, controls=controls, summary_path=summary_path)


def test_correct_native_controls_preserve_required_branches(bank_seed_controls):
    controls = bank_seed_controls['controls']
    request = {case['case']['case_id']: case for case in controls['request_unformat']['report'].cases}
    assert request['client-empty']['legacy']['exception']['type'] == 'java.lang.IllegalArgumentException'
    assert request['maximum-empty']['legacy']['context']['MaxTransactions'] == '0'
    assert request['maximum-missing']['legacy']['context']['MaxTransactions'] == '0'
    assert request['account-trailing-zero']['legacy']['context']['AccountNumber'] == '12300'
    response = controls['response_format']['report']
    for case in response.cases:
        identity, output = case['case']['case_id'], case['native']['output']
        should_nil = identity in {'channel-1-excluded-0-null', 'channel-1-excluded-0-empty'}
        assert ('xsi:nil="true"' in output) == should_nil
        assert 'wtc:nil' not in output
    assert len(response.cases) == 17


@pytest.mark.parametrize('name', list(MUTATIONS))
def test_each_seeded_defect_has_a_reproducible_failing_input(name, bank_seed_controls, boundary_tool):
    kind, _, _, witness, expected_path = MUTATIONS[name]
    control = bank_seed_controls['controls'][kind]
    native = seed_defect(control['native'], name)
    directory = bank_seed_controls['directory'] / ('mutant-' + name)
    report = verify_boundary(control['unit'], control['boundary'], control['legacy'], native, control['cases'],
        directory, tool=boundary_tool, candidate_label='deliberate_test_defect_' + name)
    # Compiler failures, missing sources and incomplete executions do not count as detected behavior defects.
    assert report.status == 'differences_found', report.model_dump_json(indent=2)
    assert len(report.cases) == len(control['cases']) and not report.unexecuted_case_ids
    assert all(case['legacy']['status'] == case['native']['status'] == 'completed' for case in report.cases)
    observed = next(case for case in report.cases if case['case']['case_id'] == witness)
    differences = [difference for difference in observed['differences'] if difference['path'].startswith(expected_path)]
    assert differences, observed
    assert all(difference['related_checklist_ids'] for difference in differences)
    saved = json.loads((directory / 'boundary-comparison.json').read_text(encoding='utf-8'))
    saved_witness = next(case for case in saved['cases'] if case['case']['case_id'] == witness)
    assert saved_witness['case'] == observed['case'] and saved_witness['differences'] == observed['differences']
    assert saved['coverage'] and not saved['acceptance_gate_enabled']
    assert report.artifact_hashes['native:compiled_text:' + native.sources[0].path] != control['report'].artifact_hashes[
        'native:compiled_text:' + native.sources[0].path]
    summary_path = bank_seed_controls['summary_path']
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary['mutants'][name] = dict(status=report.status, witness=saved_witness['case'],
        differences=differences, report='mutant-' + name + '/boundary-comparison.json',
        source_hash=hashlib.sha256(native.sources[0].content.encode()).hexdigest())
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')


def test_every_planned_mutation_names_a_real_case_and_single_edit():
    corpora = {'request_unformat': request_cases(), 'response_format': response_cases()}
    assert len(MUTATIONS) == 10
    for name, (kind, _, _, witness, _) in MUTATIONS.items():
        assert witness in {case.case_id for case in corpora[kind]}
        changed = seed_defect(native_binding(kind), name)
        assert changed.sources[0].content != native_binding(kind).sources[0].content
