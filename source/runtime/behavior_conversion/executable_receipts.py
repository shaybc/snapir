"""Recheck citation-free acceptance evidence without interpreting legacy mappings."""
import hashlib
import json
from models.executable_verification_settings import ExecutableVerificationSettings


def require_executable_evidence(folder,identity,receipt,compared):
    """Packaging still requires immutable, nonempty original/native execution proof."""
    path=folder/'boundary-structure.json'
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=receipt.get('structural_report_hash'):
        raise ValueError('Executable structural evidence changed or disappeared')
    structure=json.loads(path.read_text(encoding='utf-8'))
    if structure.get('comparison_policy'):
        from runtime.behavior_conversion.comparison_receipts import require_observed_agreement
        require_observed_agreement(structure,receipt,compared)
    if structure.get('input_generation_version'):
        inputs=folder/'input-cases.json'
        if not inputs.is_file() or hashlib.sha256(inputs.read_bytes()).hexdigest()!=receipt.get('input_cases_hash'):
            raise ValueError('Controlled input evidence changed or disappeared')
        plan=json.loads(inputs.read_text(encoding='utf-8'))
        if plan['unit_id']!=identity or plan['cases']!=[case['case'] for case in compared.cases]:
            raise ValueError('Comparison did not execute the retained controlled inputs')
    policy=ExecutableVerificationSettings.model_validate(structure['policy'])
    if structure.get('coverage_expansion_version'):
        from runtime.behavior_conversion.coverage_receipts import require_coverage_evidence
        require_coverage_evidence(structure,receipt,compared,policy)
    if any(compared.artifact_hashes.get(key)!=structure.get('tool_hash') for key in ('native:tool','legacy:tool')):
        raise ValueError('Executable analysis/execution tool revisions differ')
    if policy.mode!='executable_boundary_v1' or structure.get('schema_version')!='executable-boundary-v1':
        raise ValueError('Unknown executable verification policy')
    keys=('source_manifest_hash','configuration_hash','candidate_hash')
    if any(structure.get(key)!=receipt.get(key) for key in keys):
        raise ValueError('Executable verification revisions do not match')
    if (structure.get('unit_id')!=identity or compared.unit_id!=identity or compared.status!='matched_observed_cases'
        or not compared.cases or compared.unexecuted_case_ids or len(compared.cases)>policy.max_cases
        or compared.source_manifest_hash!=structure['source_manifest_hash'] or compared.configuration_hash!=structure['configuration_hash']
        or any(c['differences'] or c['legacy']['status']!='completed' or c['native']['status']!='completed' for c in compared.cases)):
        raise ValueError('Executable comparison evidence is incomplete or mismatched')
    if not any(c['legacy']['exception'] is None and c['native']['exception'] is None for c in compared.cases):
        raise ValueError('Executable verification requires a successful observed case')
    if compared.coverage.get('unresolved_edges') or policy.require_branch_coverage and any(b['unexercised_outcomes'] for b in compared.coverage.get('branches',[])):
        raise ValueError('Executable verification still has blocking coverage gaps')
    observed={p['id'] for c in compared.cases for p in c['native']['probes']}
    if (not receipt.get('required_native_entry') or receipt['required_native_entry'] not in observed
        or not set(receipt.get('observed_native_apis',[])).issubset(observed)):
        raise ValueError('Executable verification lacks native invocation evidence')
