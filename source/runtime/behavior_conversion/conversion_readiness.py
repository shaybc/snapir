"""Accept revision-bound conversion traceability and executed tests, never legacy equivalence."""
import hashlib
import json
import uuid
from pathlib import Path
from models.unit_static_check_report import UnitStaticCheckReport
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from tools.behavior_verification.checklist_mapping import candidate_digest,candidate_files
from tools.behavior_verification.static_checks import validate_unit_static

VERSION='conversion-checklist-v1'


def prepare_conversion(session,bundle):
    """Check all source-derived mappings without bindings, harnesses or generated comparison inputs."""
    session.last_report=None
    session.attempt=session.root/('conversion-'+uuid.uuid4().hex)
    session.attempt.mkdir()
    from runtime.behavior_conversion.verification_mode import facts_disabled
    if facts_disabled(session.executable_settings):
        from runtime.behavior_conversion.fact_validation_experiment import prepare_experiment
        return prepare_experiment(session,bundle)
    if bundle.checklist_answers is None:
        raise VerificationFailure(dict(stage='checklist',errors=['Missing checklist_answers']))
    report=validate_unit_static(session.unit,session.boundary,bundle.files,bundle.checklist_answers,
        policy=session.policy,authorizations=session.authorizations,tool=session.tool,
        directory=session.attempt/'static',conversion_only=True)
    session.static_report=report
    if report.status!='mapping_valid':
        error=VerificationFailure if report.status=='mapping_invalid' else VerificationIncomplete
        raise error(dict(stage='checklist',errors=report.errors,decisions=report.decisions,evidence=str(session.attempt)))
    from runtime.behavior_conversion.settings_readiness import prepare_native_settings
    _,targets=prepare_native_settings(session.unit,bundle,report.configuration_controls,tool=session.tool)
    session.native_settings_apis=targets
    return dict(mapping_status=report.status,behavioral_equivalence='not_assessed',native_settings_apis=targets)


def complete_conversion(session,bundle,build_validation):
    """Create readiness evidence only after mapping and actual managed build/JUnit success."""
    report=session.static_report
    from runtime.behavior_conversion.verification_mode import facts_disabled
    experimental = facts_disabled(session.executable_settings)
    expected_status = 'facts_disabled_for_test' if experimental else 'mapping_valid'
    if report is None or report.status!=expected_status or report.candidate_hash!=candidate_digest(candidate_files(bundle.files)):
        raise VerificationFailure(dict(stage='revision',errors=['Candidate changed after checklist validation']))
    build=build_validation or {}
    if not build.get('build_passed') or not build.get('tests_passed') or build.get('test_count',0)<1 or build.get('issues'):
        raise VerificationIncomplete(dict(stage='build',errors=['Passing compilation and executed JUnit tests are required']))
    from tools.behavior_verification.java_tool import default_tool_path
    tool=Path(session.tool or default_tool_path()).resolve()
    proof=dict(verification_version=VERSION,unit_id=session.unit['unit_id'],readiness_status='conversion_ready',
        behavioral_equivalence='not_assessed',exhaustive_equivalence=False,source_manifest_hash=report.source_manifest_hash,
        configuration_hash=report.configuration_hash,candidate_hash=report.candidate_hash,policy_hash=report.policy_hash,
        static_report_hash=_hash(session.attempt/'static/unit-static-checks.json'),analysis_tool=str(tool),
        analysis_tool_hash=report.tool_hash,build_validation=build)
    if experimental:
        from runtime.behavior_conversion.fact_validation_experiment import VERSION as EXPERIMENT_VERSION
        proof.update(verification_version=EXPERIMENT_VERSION,readiness_status='experimental_only',experimental_only=True,
                     fact_collection=False,fact_validation='disabled_for_test',tool_hash=report.tool_hash)
    target=session.attempt/'conversion-readiness.json'
    target.write_text(json.dumps(proof,indent=2),encoding='utf-8')
    session.last_report=dict(proof,evidence=str(session.attempt),report_hash=_hash(target))


def require_conversion_evidence(config,identity,receipt):
    """Reject old comparison receipts, changed evidence and readiness without a mapping/build proof."""
    folder=Path(receipt.get('evidence','')).resolve()
    root=(Path(config.output_root)/'.unit-verification').resolve()
    proof_file=folder/'conversion-readiness.json';static_file=folder/'static/unit-static-checks.json'
    if not folder.is_relative_to(root) or not proof_file.is_file() or _hash(proof_file)!=receipt.get('report_hash'):
        raise ValueError('Conversion readiness evidence changed or disappeared')
    proof=json.loads(proof_file.read_text(encoding='utf-8'))
    if any(receipt.get(key)!=value for key,value in proof.items()) or proof.get('verification_version')!=VERSION or proof.get('unit_id')!=identity:
        raise ValueError('Conversion readiness receipt does not match retained proof')
    if proof.get('readiness_status')!='conversion_ready' or proof.get('behavioral_equivalence')!='not_assessed':
        raise ValueError('Conversion readiness must not claim behavioral equivalence')
    if not static_file.is_file() or _hash(static_file)!=proof.get('static_report_hash'):
        raise ValueError('Conversion checklist evidence changed or disappeared')
    static=UnitStaticCheckReport.model_validate_json(static_file.read_text(encoding='utf-8'))
    if static.status!='mapping_valid' or static.unit_id!=identity or any(getattr(static,k)!=proof.get(k)
            for k in ('source_manifest_hash','configuration_hash','candidate_hash','policy_hash')):
        raise ValueError('Conversion checklist proof is incomplete or mismatched')
    tool=Path(proof.get('analysis_tool',''))
    if not tool.is_file() or _hash(tool)!=proof.get('analysis_tool_hash') or static.tool_hash!=proof.get('analysis_tool_hash'):
        raise ValueError('Conversion source analysis tool changed or disappeared')
    build=proof.get('build_validation',{})
    if not build.get('build_passed') or not build.get('tests_passed') or build.get('test_count',0)<1 or build.get('issues'):
        raise ValueError('Conversion readiness lacks executed passing build/JUnit evidence')


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
