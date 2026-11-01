"""Standalone milestone-5 checker, deliberately not wired into acceptance yet."""
import subprocess
import json
from pathlib import Path
from pydantic import ValidationError
from models.static_check_policy import StaticCheckPolicy
from models.unit_checklist_answers import UnitChecklistAnswers
from models.unit_static_check_report import UnitStaticCheckReport
from tools.behavior_verification.boundary_contracts import digest
from tools.behavior_verification.checklist_mapping import candidate_files, candidate_digest, validate_revisions
from tools.behavior_verification.checklist_exclusions import validate_exclusion
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.static_comparison_evidence import comparison_cases
from tools.behavior_verification.supporting_static_checks import supporting_checks


def validate_unit_static(unit, boundary, files, answers, *, policy=None, authorizations=(), comparison_report=None,
                         trusted_harness_sources=(), tool=None, directory=None):
    """Check complete mapping and supported exclusions; warnings never establish acceptance."""
    report = UnitStaticCheckReport(unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash,
                                  configuration_hash=boundary.configuration_hash)
    try:
        policy = StaticCheckPolicy.model_validate(policy or StaticCheckPolicy())
        report.policy_hash = digest(policy.model_dump(mode='json'))
        files = candidate_files(files)
        report.candidate_hash = candidate_digest(files)
        answers = UnitChecklistAnswers.model_validate(answers)
        report.errors.extend(validate_revisions(unit, boundary, answers))
        rejected_ids={e.get('checklist_id') for e in report.errors}
        answers=answers.model_copy(deep=True)
        answers.responses=[answer for answer in answers.responses if answer.checklist_id not in rejected_ids]
        if report.errors and not answers.responses:
            report.status = 'mapping_invalid'
            return report
        cases = comparison_cases(comparison_report, boundary, files, trusted_harness_sources)
        try:
            analysis, report.tool_hash = inspect_static_sources(unit, boundary, files, answers, policy, tool)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            report.errors.append(dict(kind='analysis_unavailable', message=str(error)))
            return report
        lookup = {item.id: item for item in boundary.parser_checklist.items}
        report.configuration_controls = analysis.get('settings', [])
        unresolved, excluded = False, set()
        for answer in answers.responses:
            item = lookup[answer.checklist_id]
            decision = dict(checklist_id=item.id, status=answer.status)
            try:
                if answer.status == 'implemented':
                    for index, location in enumerate(answer.locations):
                        if not location.path.startswith('src/main/java/') or not analysis['native']['locations'].get(item.id + ':' + str(index)):
                            raise ValueError('Implementation excerpt must exist in current main Java code, outside comments/imports/package')
                    decision['locations'] = [location.model_dump(mode='json') for location in answer.locations]
                elif answer.status == 'not_applicable':
                    proof = validate_exclusion(item, answer, boundary, report.candidate_hash, policy, analysis['proofs'], authorizations)
                    decision['proof'] = proof
                    excluded.add(item.id)
                    if 'authorization' in proof:
                        report.authorization_receipts.append(proof)
                else:
                    unresolved = True
                    decision['question'] = answer.question
            except ValueError as error:
                report.errors.append(dict(checklist_id=item.id, message=str(error)))
                decision['status'] = 'rejected'
            report.decisions.append(decision)
        supporting_checks(unit, boundary, analysis['native']['files'], excluded, cases, report)
        report.status = 'mapping_invalid' if report.errors else 'verification_incomplete' if unresolved else 'mapping_valid'
    except (ValueError, ValidationError, KeyError, TypeError) as error:
        report.errors.append(dict(kind='invalid_contract', message=str(error)))
        report.status = 'mapping_invalid'
    finally:
        if directory is not None:
            folder = Path(directory)
            folder.mkdir(parents=True, exist_ok=True)
            temporary = folder / 'unit-static-checks.json.tmp'
            # Java literals can contain isolated UTF-16 code units; JSON escapes preserve them.
            temporary.write_text(json.dumps(report.model_dump(mode='python'), ensure_ascii=True, indent=2), encoding='utf-8')
            temporary.replace(folder / 'unit-static-checks.json')
    return report
