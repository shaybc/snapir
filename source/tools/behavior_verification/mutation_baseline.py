"""Reuse only immutable, complete baseline observations for the exact current mutation job."""
import hashlib
import json
from pathlib import Path
from models.boundary_comparison_report import BoundaryComparisonReport
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.comparison_environment import runtime_fingerprint
from tools.behavior_verification.independent_comparison import VERSION


def reusable_baseline(job,boundary,legacy,native,cases,tool):
    """Reject any mismatch and let the caller execute a fresh full baseline instead."""
    reference=job.get('verified_baseline')
    if not reference:return None,'no_verified_baseline'
    try:
        path=Path(reference['path']).resolve()
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=reference['sha256']:raise ValueError('baseline_report_hash_changed')
        report=BoundaryComparisonReport.model_validate_json(raw)
        if (report.status!='matched_observed_cases' or report.issues or report.unexecuted_case_ids or not report.cases
            or any(c.get('comparison_status')!='matched' or c.get('limitations') or c.get('differences')
                   or c['legacy']['status']!='completed' or c['native']['status']!='completed' for c in report.cases)):
            raise ValueError('baseline_observations_not_complete')
        current=boundary_contract(job['unit'],{'opStep':boundary.implementation_class})
        if (report.unit_id!=boundary.unit_id or current.source_manifest_hash!=boundary.source_manifest_hash
            or current.configuration_hash!=boundary.configuration_hash
            or report.source_manifest_hash!=current.source_manifest_hash or report.configuration_hash!=current.configuration_hash):
            raise ValueError('baseline_source_or_configuration_changed')
        if [c['case'] for c in report.cases]!=[c.model_dump(mode='json') for c in cases]:raise ValueError('baseline_inputs_changed')
        environment=report.execution_environment
        if (environment.get('runtime_fingerprint')!=runtime_fingerprint() or environment.get('comparison_policy')!=VERSION
            or str(environment.get('java_version'))!=str(job['java_version'])
            or environment.get('case_timeout_seconds')!=15 or environment.get('assertions_enabled') is not True
            or environment.get('timezone')!='UTC' or environment.get('locale')!='ROOT'
            or environment.get('isolation')!='fresh_JVM_per_side_per_case'):
            raise ValueError('baseline_environment_or_policy_changed')
        hashes=report.artifact_hashes
        tool_hash=hashlib.sha256(Path(tool).read_bytes()).hexdigest()
        for side,binding in (('legacy',legacy),('native',native)):
            fingerprint=hashlib.sha256(json.dumps(binding.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
            if hashes.get(side+':tool')!=tool_hash or hashes.get(side+':binding')!=fingerprint:
                raise ValueError('baseline_tool_or_binding_changed')
            expected={str(Path(name).resolve()) for name in binding.classpath}
            dependencies={key[len(side+':dependency:'):]:value for key,value in hashes.items() if key.startswith(side+':dependency:')}
            if set(dependencies)!=expected:raise ValueError('baseline_dependency_set_changed')
            for name,value in dependencies.items():
                if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=value:raise ValueError('baseline_dependency_changed')
        sources={f.path:hashlib.sha256(f.content.encode()).hexdigest() for f in native.sources}
        if sources!=job['candidate_sources']:raise ValueError('baseline_candidate_manifest_changed')
        for side,items in (('legacy',job['unit']['sources']),('native',[dict(identity=f.path,content=f.content,content_hash=sources[f.path]) for f in native.sources])):
            expected={item['identity'] for item in items}
            actual={key[len(side+':source:'):] for key in hashes if key.startswith(side+':source:')}
            if actual!=expected:raise ValueError('baseline_source_set_changed')
            for item in items:
                if (hashes.get(side+':source:'+item['identity'])!=item['content_hash']
                    or hashes.get(side+':compiled_text:'+item['identity'])!=hashlib.sha256(item['content'].encode()).hexdigest()):
                    raise ValueError('baseline_source_text_changed')
        return report,'exact_verified_baseline'
    except (OSError,ValueError,KeyError,TypeError) as error:
        return None,str(error)
