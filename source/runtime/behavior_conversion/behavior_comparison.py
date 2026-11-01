"""Compare each source obligation and translate grounded findings into correction feedback."""

from agents.behavior_conversion.behavior_extraction import COMPARE
from models.behavior_comparison import BehaviorComparison
from models.behavior_specification import BehaviorSpecification
from runtime.behavior_conversion.behavior_extraction import evidence_catalog
from runtime.behavior_conversion.behavior_fact_validation import validate_comparison
from runtime.behavior_conversion.review_payload import review_requests
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools.behavior_units import save


def compare_behavior(conn, config, profile, identity, payload, model_call=None):
    """Review source plus facts, retaining advisory findings without rejecting style."""
    from runtime.behavior_conversion.generation import generate
    from runtime.behavior_conversion.review import BehaviorReview
    from runtime.behavior_conversion.response_json import JSON_INSTRUCTION
    specification = BehaviorSpecification.model_validate(payload['behavior_specification'])
    sources = evidence_catalog(payload, identity)
    requests = review_requests(payload, COMPARE + '\n' + JSON_INSTRUCTION,
                               BehaviorComparison.model_json_schema(), profile.behavior_context_chars)
    findings, fingerprints = [], []
    for number, request in enumerate(requests, 1):
        bundle = request.get('generated_bundle', request.get('bundle', {}))
        files = {item['path']: item['content'] for item in bundle.get('files', [])}
        def validate(result, cached=False):
            validate_comparison(result, specification, sources, files)
        result, fingerprint = generate(conn, config, profile, 'review',
            identity + ':behavior-comparison:' + str(number), COMPARE, request, BehaviorComparison,
            validate, model_call, 'Behavior comparison: ' + identity)
        findings.extend(result.findings)
        fingerprints.append(fingerprint)
    findings = list({finding.model_dump_json(): finding for finding in findings}.values())
    issues = [finding.model_dump_json() for finding in findings
              if finding.status in {'missing', 'changed', 'invented_behavior'}]
    questions = [finding.model_dump_json() for finding in findings if finding.status == 'insufficient_evidence']
    result = BehaviorReview(approved=not issues and not questions, issues=issues,
                            unresolved_questions=questions, comparisons=findings)
    fingerprint = stable_id(fingerprints, 'behavior-comparison-v1')
    save(conn, config.run_id, 'review', identity, fingerprint, result.model_dump(mode='json'))
    return result, fingerprint
