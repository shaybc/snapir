"""Literal/XML signals and reproducible comparison requests; never static equivalence proof."""
from xml.parsers.expat import ExpatError
import hashlib
import json
from tools.behavior_verification.boundary_xml import xml_structure
from tools.behavior_verification.controlled_inputs import generate_boundary_cases


def supporting_checks(unit, boundary, inventory, excluded, cases, report):
    """Record missing literals and actual XML shape differences without rejecting equivalent code."""
    literals = {(item['category'], item['value']) for file in inventory.values() for item in file['literals']}
    generated = None
    for item in boundary.parser_checklist.items:
        if item.kind != 'literal' or item.id in excluded:
            continue
        value = item.properties.get('value', '')
        category = {'StringLiteralExpr': 'string', 'TextBlockLiteralExpr': 'string', 'CharLiteralExpr': 'character',
                    'BooleanLiteralExpr': 'boolean', 'NullLiteralExpr': 'null'}.get(item.detail, 'number')
        present = (category, value) in literals
        observed = category == 'string' and bool(value) and any(_contains(case['native']['output'], value) for case in cases)
        status = 'present_in_code' if present else 'present_in_observed_output' if observed else 'not_found'
        report.literal_checks.append(dict(checklist_id=item.id, category=category, value=value, status=status,
                                         equivalence_proven=False))
        if present or observed:
            continue
        report.warnings.append(dict(checklist_id=item.id, kind='missing_literal', message='Literal not found; comparison required', value=value))
        touched = [case for case in cases if any(probe['id'] in {item.id, item.code_node_id} for probe in case['legacy'].get('probes', []))]
        if touched:
            candidates = [case['case'] for case in touched]
            targeting = 'observed_owner_only_not_branch_proof'
        else:
            if generated is None:
                try:
                    generated = [case.model_dump(mode='json') for case in generate_boundary_cases(unit, boundary, random_cases=0)]
                except ValueError:
                    generated = []
            candidates, targeting = generated, 'generated_candidates_not_path_proven'
        report.comparison_requests.append(dict(checklist_ids=[item.id], source_identity=item.source_identity,
            start_line=item.start_line, end_line=item.end_line, literal=value, targeting=targeting,
            case_ids=_case_references(candidates, report),
            coverage_gap=True, requires_path_confirmation=True,
            next_action='Run boundary comparison and confirm this source path was exercised'))

    for case in cases:
        left, right = case['legacy']['output'], case['native']['output']
        if unit['kind'] != 'response_format' or not isinstance(left, str) or not isinstance(right, str):
            continue
        try:
            matches = xml_structure(left) == xml_structure(right)
            check = dict(case_id=case['case']['case_id'], status='observed_match' if matches else 'observed_difference',
                         checks=['names', 'nesting', 'order', 'attributes', 'namespace_uris', 'prefixes', 'text'])
        except (ValueError, ExpatError) as error:
            # XML parse failures are a signal too; malformed output cannot be normalized into a match.
            matches = False
            check = dict(case_id=case['case']['case_id'], status='xml_unavailable', message=str(error))
        report.xml_checks.append(check)
        if not matches:
            report.warnings.append(dict(kind='xml_structure', **check))
            report.comparison_requests.append(dict(reason='xml_structure', case_ids=_case_references([case['case']], report), targeting='exact_observed_case'))
    if not report.xml_checks:
        report.xml_checks.append(dict(status='not_observed', message='No paired XML outputs; static names alone cannot prove structure'))


def _contains(value, literal):
    if isinstance(value, str):
        return literal in value
    if isinstance(value, dict):
        return any(_contains(item, literal) for item in value.values())
    if isinstance(value, list):
        return any(_contains(item, literal) for item in value)
    return False


def _case_references(cases, report):
    """Keep reproducible inputs once instead of copying them for every missing checklist literal."""
    identities = []
    for case in cases:
        identity = hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        report.comparison_cases[identity] = case
        identities.append(identity)
    return identities
