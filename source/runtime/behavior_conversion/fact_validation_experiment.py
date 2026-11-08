"""Source/build evidence with separate supported test-based and historical experiment policies."""
import hashlib
import json
from pathlib import Path
from models.unit_static_check_report import UnitStaticCheckReport
from models.unit_checklist_answers import UnitChecklistAnswers
from models.static_check_policy import StaticCheckPolicy
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from tools.behavior_verification.boundary_contracts import boundary_contract, digest
from tools.behavior_verification.checklist_mapping import candidate_files, candidate_digest
from tools.behavior_verification.static_analysis import inspect_static_sources

VERSION = 'conversion-facts-experiment-v1'


def prepare_experiment(session, bundle, *, supported=False):
    """Retain freshness and source-defined settings checks without creating or mapping facts."""
    label = 'Test-based' if supported else 'Experimental'
    current = boundary_contract(session.unit)
    fields = ('unit_id', 'source_manifest_hash', 'configuration_hash', 'unit_fingerprint', 'operation_identity',
              'kind', 'implementation_class', 'method_name', 'parameter_contract', 'return_contract', 'setup_bindings')
    if any(getattr(current, field) != getattr(session.boundary, field) for field in fields):
        raise VerificationFailure(dict(stage='source_analysis', errors=[label + ' boundary source/configuration changed']))
    graph = session.boundary.reachable_slice
    if graph is None or graph.source_manifest_hash != current.source_manifest_hash or graph.configuration_hash != current.configuration_hash:
        raise VerificationFailure(dict(stage='source_analysis', errors=[label + ' run requires its current source graph']))
    policy = StaticCheckPolicy.model_validate(session.policy or StaticCheckPolicy())
    answers = UnitChecklistAnswers(unit_id=current.unit_id, source_manifest_hash=current.source_manifest_hash,
                                    configuration_hash=current.configuration_hash)
    analysis, tool_hash = inspect_static_sources(session.unit, session.boundary, candidate_files(bundle.files), answers, policy, session.tool)
    report = UnitStaticCheckReport(unit_id=current.unit_id, source_manifest_hash=current.source_manifest_hash,
        configuration_hash=current.configuration_hash, candidate_hash=candidate_digest(candidate_files(bundle.files)),
        policy_hash=digest(dict(policy='test-based-conversion-v1', static_policy=policy.model_dump(mode='json'))) if supported else digest(dict(experimental_disable_facts=True, static_policy=policy.model_dump(mode='json'))),
        tool_hash=tool_hash, status='test_based_ready' if supported else 'facts_disabled_for_test', configuration_controls=analysis.get('settings', []),
        warnings=[] if supported else [dict(kind='experimental_only', message='Fact collection, mapping and blocking validation are disabled for this test')])
    folder = session.attempt / 'static'; folder.mkdir()
    (folder / 'unit-static-checks.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
    session.static_report = report
    from runtime.behavior_conversion.settings_readiness import prepare_native_settings
    _, session.native_settings_apis = prepare_native_settings(session.unit, bundle, report.configuration_controls, tool=session.tool)
    return dict(mapping_status=report.status, experimental_only=not supported, behavioral_equivalence='not_assessed',
                native_settings_apis=session.native_settings_apis)


def require_experiment_evidence(config, identity, receipt, *, supported=False):
    """Validate source/build evidence without accepting a different policy's receipts."""
    label = 'Test-based' if supported else 'Experimental'
    folder = Path(receipt.get('evidence', '')).resolve()
    root = (Path(config.output_root) / '.unit-verification').resolve()
    target = folder / 'conversion-readiness.json'
    if not folder.is_relative_to(root) or not target.is_file() or _hash(target) != receipt.get('report_hash'):
        raise ValueError(label + ' evidence changed or disappeared')
    proof = json.loads(target.read_text(encoding='utf-8'))
    version = 'test-based-conversion-v1' if supported else VERSION
    if any(receipt.get(key) != value for key, value in proof.items()) or proof.get('verification_version') != version or proof.get('unit_id') != identity:
        raise ValueError(label + ' receipt does not match retained proof')
    if supported and (proof.get('readiness_status') != 'conversion_ready' or proof.get('behavioral_equivalence') != 'not_assessed' or proof.get('experimental_only') is not False or proof.get('fact_collection') is not False or proof.get('fact_validation') != 'disabled'):
        raise ValueError('Test-based proof must identify its supported fact-free policy')
    if not supported and (proof.get('readiness_status') != 'experimental_only' or proof.get('experimental_only') is not True):
        raise ValueError('Experimental proof must not claim normal conversion readiness')
    static_file = folder / 'static/unit-static-checks.json'
    if not static_file.is_file() or _hash(static_file) != proof.get('static_report_hash'):
        raise ValueError(label + ' source evidence changed')
    static = UnitStaticCheckReport.model_validate_json(static_file.read_text(encoding='utf-8'))
    if static.status != ('test_based_ready' if supported else 'facts_disabled_for_test') or static.unit_id != identity or any(getattr(static, key) != proof.get(key)
            for key in ('source_manifest_hash', 'configuration_hash', 'candidate_hash', 'policy_hash', 'tool_hash')):
        raise ValueError(label + ' source/build proof is mismatched')
    tool = Path(proof.get('analysis_tool', ''))
    if not tool.is_file() or _hash(tool) != proof.get('analysis_tool_hash') or static.tool_hash != proof.get('analysis_tool_hash'):
        raise ValueError(label + ' source analysis tool changed')
    build = proof.get('build_validation', {})
    if not build.get('build_passed') or not build.get('tests_passed') or build.get('test_count', 0) < 1 or build.get('issues'):
        raise ValueError(label + ' proof lacks actual passing compilation/JUnit')


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
