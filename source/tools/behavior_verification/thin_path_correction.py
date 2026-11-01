"""Seed a native correction from an exact saved candidate and real compared-value differences."""
import hashlib
import json
from pathlib import Path
from models.thin_path_comparison_report import ThinPathComparisonReport
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.thin_path_saved_candidate import read_candidate
from tools.behavior_verification.thin_path_validation import difference_feedback


def seed_correction(request,database,attempt,unit,comparison):
    """Reject mismatched source/candidate reports; never send tooling limitations as code corrections."""
    bundle,saved=read_candidate(database,attempt,unit)
    report=ThinPathComparisonReport.model_validate_json(Path(comparison).read_text(encoding='utf-8'))
    boundary=boundary_contract(unit)
    if any(getattr(report,key)!=getattr(boundary,key) for key in ('unit_id','source_manifest_hash','configuration_hash')):
        raise ValueError('Correction report belongs to another source/configuration revision')
    if report.status!='differences_found' or not any(case['differences'] for case in report.cases):
        raise ValueError('Correction requires actual compared-value differences')
    if any(case['differences'] and (case['legacy']['status']!='completed' or case['native']['status']!='completed')
           for case in report.cases):
        raise ValueError('Tooling failures cannot seed a code correction')
    expected={file.path:hashlib.sha256(file.content.encode('utf-8')).hexdigest() for file in bundle.files
              if file.path.startswith('src/main/java/')}
    observed={key[len('native:compiled_text:'):]:value for key,value in report.artifact_hashes.items()
              if key.startswith('native:compiled_text:')}
    if expected!=observed:
        raise ValueError('Correction report was not produced from this saved candidate')
    feedback=difference_feedback(report)
    request=dict(request,previous_model_response=bundle.model_dump_json(),
        correction_feedback=json.dumps(feedback,ensure_ascii=False),saved_candidate=saved)
    return request,saved
