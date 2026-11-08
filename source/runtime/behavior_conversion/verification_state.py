"""Persist terminal unit verification outcomes without calling preparation acceptance."""
import hashlib
import json
from pathlib import Path
from tools.state_store_tools.behavior_units import save


def record_verification(conn, config, identity, status, report):
    """Only a completed technical ladder can record Accepted; other states remain explicit."""
    if status not in {'accepted', 'failed', 'verification_incomplete'}:
        raise ValueError('Unknown unit verification outcome')
    if status == 'accepted':
        _require_evidence(config, identity, report)
    data = dict(report,unit_id=identity,status=status)
    data.setdefault('verification_version','parser-boundary-v1')
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    save(conn, config.run_id, 'unit_verification', identity, fingerprint, data, status)
    return data


def write_verification_results(conn, config, directory, unit_ids=None):
    """Publish actual terminal outcomes, not preparation/fixture acceptance counts."""
    rows = conn.execute("SELECT identity,status,data_json FROM behavior_snapshots WHERE run_id=? AND category='unit_verification' ORDER BY identity",
                        (config.run_id,)).fetchall()
    if unit_ids is not None:
        unit_ids = set(unit_ids)
        rows = [row for row in rows if row['identity'] in unit_ids]
    data = dict(schema_version='unit-verification-results-v1', units={row['identity']: json.loads(row['data_json']) for row in rows})
    data['counts'] = {status: sum(row['status'] == status for row in rows) for status in ('accepted', 'failed', 'verification_incomplete')}
    data['pending_unit_ids'] = sorted((unit_ids or set()) - {row['identity'] for row in rows})
    folder = Path(directory); folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / 'unit-verification-results.json.tmp'
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding='utf-8')
    temporary.replace(folder / 'unit-verification-results.json')
    return data


def require_unit_receipts(conn, config, record, *, expected_version=None):
    """Packaging cannot promote old fact-only bundles or changed native/evidence bytes."""
    from tools.state_store_tools.behavior_units import snapshot
    from tools.behavior_verification.boundary_contracts import digest
    for binding in record.get('bindings', {}).values():
        row = snapshot(conn, config.run_id, 'unit_verification', binding['unit_id'])
        if row is None or row['status'] != 'accepted':
            raise ValueError('Unit lacks technical boundary acceptance: ' + binding['unit_id'])
        receipt = json.loads(row['data_json'])
        if expected_version is not None and receipt.get('verification_version')!=expected_version:
            raise ValueError('Unit readiness policy changed; revalidate source, mappings and tests')
        if record.get('component_first') and not receipt.get('component_receipt'):
            raise ValueError('Component-first unit lacks transitive component acceptance: ' + binding['unit_id'])
        allowed = {'parser-boundary-v1','executable-boundary-v1','conversion-checklist-v1','test-based-conversion-v1'}
        if expected_version == 'conversion-facts-experiment-v1':allowed.add(expected_version)
        if receipt.get('verification_version') not in allowed or receipt.get('candidate_hash') != digest(binding['files']):
            raise ValueError('Unit verification receipt does not match native source manifest')
        _require_evidence(config, binding['unit_id'], receipt)
        if receipt.get('component_receipt'):
            from runtime.component_conversion.unit_artifacts import require_unit_components
            require_unit_components(conn,config,binding['unit_id'],receipt['candidate_hash'],revision=receipt['component_receipt'])


def _require_evidence(config, identity, receipt):
    """An Accepted row needs matching, nonempty boundary and static reports, not a boolean claim."""
    if receipt.get('verification_version')=='conversion-facts-experiment-v1':
        from runtime.behavior_conversion.fact_validation_experiment import require_experiment_evidence
        return require_experiment_evidence(config,identity,receipt)
    if receipt.get('verification_version') in {'conversion-checklist-v1','test-based-conversion-v1'}:
        from runtime.behavior_conversion.conversion_readiness import require_conversion_evidence
        return require_conversion_evidence(config,identity,receipt)
    from models.boundary_comparison_report import BoundaryComparisonReport
    from models.unit_static_check_report import UnitStaticCheckReport
    folder = Path(receipt.get('evidence', '')).resolve()
    evidence = folder / 'comparison/boundary-comparison.json'
    root = (Path(config.output_root) / '.unit-verification').resolve()
    if not evidence.is_relative_to(root) or not evidence.is_file() or hashlib.sha256(evidence.read_bytes()).hexdigest() != receipt.get('report_hash'):
        raise ValueError('Unit boundary evidence changed or disappeared')
    compared = BoundaryComparisonReport.model_validate_json(evidence.read_text(encoding='utf-8'))
    harness = folder / 'harness-tool.jar'
    if not harness.is_file() or hashlib.sha256(harness.read_bytes()).hexdigest() != compared.artifact_hashes.get('native:tool'):
        raise ValueError('Unit verification harness changed or disappeared')
    for key, expected in compared.artifact_hashes.items():
        if ':dependency:' in key:
            dependency = Path(key.split(':dependency:', 1)[1])
            if not dependency.is_file() or hashlib.sha256(dependency.read_bytes()).hexdigest() != expected:
                raise ValueError('Unit verification dependency changed or disappeared')
    build = receipt.get('build_validation', {})
    if not build.get('build_passed') or not build.get('tests_passed') or build.get('test_count', 0) < 1 or build.get('issues'):
        raise ValueError('Unit lacks passing build and executed-test evidence')
    if receipt.get('verification_version')=='executable-boundary-v1':
        from runtime.behavior_conversion.executable_receipts import require_executable_evidence
        require_executable_evidence(folder,identity,receipt,compared)
        return
    static = UnitStaticCheckReport.model_validate_json((folder / 'static-observed/unit-static-checks.json').read_text(encoding='utf-8'))
    if (compared.unit_id != identity or compared.status != 'matched_observed_cases' or not compared.cases
        or compared.unexecuted_case_ids or static.status != 'mapping_valid' or static.candidate_hash != receipt.get('candidate_hash')
        or (compared.source_manifest_hash, compared.configuration_hash) != (static.source_manifest_hash, static.configuration_hash)
        or (static.source_manifest_hash, static.configuration_hash) != (receipt.get('source_manifest_hash'), receipt.get('configuration_hash'))
        or any(case['differences'] or case['legacy']['status'] != 'completed' or case['native']['status'] != 'completed' for case in compared.cases)):
        raise ValueError('Unit technical acceptance evidence is incomplete or mismatched')
