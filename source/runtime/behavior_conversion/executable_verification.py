"""Citation-free verification using the existing isolated, independently compared JVMs.

This implementation executes restricted plans through the trusted typed adapter. Unsupported invocation
shapes remain incomplete; it never substitutes an AI expectation or a server run.
"""
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.native_unit_bundle import NativeSourceFile
from models.static_check_policy import StaticCheckPolicy
from models.unit_checklist_answers import UnitChecklistAnswers
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.verification_binding import validate_binding,project_context_only
from runtime.behavior_conversion.verification_cases import controlled_cases
from runtime.behavior_conversion.verification_classpath import native_runtime_classpath
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete,comparison_feedback
from tools.behavior_verification.checklist_mapping import candidate_files,candidate_digest
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.java_tool import default_tool_path
from tools.behavior_verification.boundary_verification import verify_boundary

VERSION='executable-boundary-v1'


def prepare_boundary(session,bundle):
    """Check structure and derive runtime controls without requesting any citations."""
    session.last_report=None
    if bundle.verification_binding is None:
        raise VerificationIncomplete(dict(stage='adapter',errors=['This boundary needs a validated adapter plan from the staged adapter task']))
    bundle.verification_binding=project_context_only(bundle.verification_binding,session.boundary)
    validate_bundle(bundle,bundle.unit_contract.apis if bundle.unit_contract else ())
    if not session.boundary.reachable_slice or not session.boundary.parser_checklist:
        raise VerificationIncomplete(dict(stage='source_analysis',errors=['Original boundary/parser evidence is required']))
    files=candidate_files(bundle.files)
    session.attempt=session.root/('attempt-'+uuid.uuid4().hex);session.attempt.mkdir()
    # Empty answers are an application-created tool input, never a claim that
    # checklist details were mapped or implemented. Only settings are consumed.
    answers=UnitChecklistAnswers(unit_id=session.unit['unit_id'],source_manifest_hash=session.boundary.source_manifest_hash,
        configuration_hash=session.boundary.configuration_hash)
    from tools.behavior_verification.checklist_mapping import validate_revisions
    # This validates original graph/configuration provenance. Returned missing
    # citation answers are intentionally irrelevant to this execution mode.
    try:
        validate_revisions(session.unit,session.boundary,answers)
        analysis,tool_hash=inspect_static_sources(session.unit,session.boundary,files,answers,
            session.policy or StaticCheckPolicy(),session.tool)
        from tools.behavior_verification.configured_preparation import retain_preparation
        retain_preparation(session.boundary,analysis.get('preparation',{}))
    except (ValueError,OSError) as error:
        raise VerificationIncomplete(dict(stage='source_analysis',errors=[str(error)])) from error
    _save(session.attempt/'configuration-preparation.json',session.boundary.configuration_preparation)
    session.executable_structure=dict(schema_version=VERSION,unit_id=session.unit['unit_id'],
        source_manifest_hash=session.boundary.source_manifest_hash,configuration_hash=session.boundary.configuration_hash,
        candidate_hash=candidate_digest(files),tool_hash=tool_hash,policy=session.executable_settings.model_dump(mode='json'),
        configuration_controls=analysis.get('settings',[]),citations_required=False)
    from tools.behavior_verification.structured_inputs import VERSION as INPUT_VERSION
    session.executable_structure['input_generation_version']=INPUT_VERSION
    from tools.behavior_verification.independent_comparison import VERSION as COMPARISON_VERSION
    session.executable_structure.update(comparison_policy=COMPARISON_VERSION,kind=session.unit['kind'])
    from tools.behavior_verification.coverage_expansion import VERSION as COVERAGE_VERSION
    session.executable_structure['coverage_expansion_version']=COVERAGE_VERSION
    from runtime.behavior_conversion.coverage_receipts import coverage_inventory
    session.executable_structure['coverage_inventory']=coverage_inventory(session.boundary)
    from runtime.behavior_conversion.settings_readiness import prepare_settings
    session.executable_structure['comparison_preparation']=prepare_settings(session.unit,session.boundary,bundle,
        session.executable_structure['configuration_controls'],tool=session.tool,settings=session.executable_settings)
    _save(session.attempt/'boundary-structure.json',session.executable_structure)


def compare_boundary(session,project,context,bundle,build_validation):
    """Require fresh builds, observed agreement and explicit coverage limitations."""
    structure=getattr(session,'executable_structure',None)
    if not structure or structure['candidate_hash']!=candidate_digest(candidate_files(bundle.files)):
        raise VerificationIncomplete(dict(stage='revision',errors=['Candidate changed after structural verification']))
    if session.executable_settings.model_dump(mode='json')!=structure['policy']:
        raise VerificationIncomplete(dict(stage='policy_revision',errors=['Input/verification policy changed after structural verification']))
    if not build_validation or not build_validation.get('build_passed') or not build_validation.get('tests_passed') or build_validation.get('test_count',0)<1 or build_validation.get('issues'):
        raise VerificationIncomplete(dict(stage='build',errors=['Passing compilation and executed JUnit evidence are required']))
    generation={}
    cases=controlled_cases(session.unit,session.boundary,bundle.verification_binding,structure['configuration_controls'],
        executable_settings=session.executable_settings,generation_report=generation)
    if len(cases)>session.executable_settings.max_cases:
        raise VerificationIncomplete(dict(stage='cases',errors=['Configured executable case budget exceeded'],case_count=len(cases)))
    _save(session.attempt/'input-cases.json',dict(unit_id=session.unit['unit_id'],generation=generation,
        cases=[case.model_dump(mode='json') for case in cases]))
    project=Path(project)
    sources=[dict(path=p.relative_to(project).as_posix(),content=p.read_text(encoding='utf-8')) for p in sorted((project/'src/main/java').rglob('*.java'))]
    native=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',native_entry=bundle.verification_binding,
        sources=sources,settings_bindings=bundle.verification_binding.settings_bindings,classpath=native_runtime_classpath(project,context))
    harness=session.attempt/'harness-tool.jar';shutil.copyfile(session.tool or default_tool_path(),harness)
    if _hash(harness)!=structure['tool_hash']:
        raise VerificationIncomplete(dict(stage='tool_revision',errors=['Analysis tool changed before execution']))
    legacy=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    from tools.behavior_verification.independent_comparison import VERSION as COMPARISON_VERSION
    from tools.behavior_verification.coverage_expansion import CoverageExpansion
    expansion=CoverageExpansion(session.unit,session.boundary,session.executable_settings,legacy)
    report=verify_boundary(session.unit,session.boundary,legacy,native,cases,session.attempt/'comparison',tool=harness,
        candidate_label='citation_free_native_boundary',continue_incomplete=True,comparison_policy=COMPARISON_VERSION,coverage_expansion=expansion)
    all_cases=[*cases,*expansion.planned]
    generation.update(planned_cases=len(all_cases),coverage_expansion_cases=len(expansion.planned))
    _save(session.attempt/'input-cases.json',dict(unit_id=session.unit['unit_id'],generation=generation,
        cases=[case.model_dump(mode='json') for case in all_cases]))
    feedback=comparison_feedback(report)
    if report.coverage.get('configuration_proof_conflicts'):
        raise VerificationIncomplete(dict(stage='configuration_proof',errors=['Executed outcomes contradict configured preparation'],
            conflicts=report.coverage['configuration_proof_conflicts']))
    from runtime.behavior_conversion.failure_routing import adapter_failure,AdapterRepairRequired
    wiring=adapter_failure(report)
    if wiring:raise AdapterRepairRequired(wiring)
    if report.status=='differences_found':raise VerificationFailure(dict(stage='boundary',**feedback))
    if report.status!='matched_observed_cases':raise VerificationIncomplete(dict(stage='boundary',**feedback))
    successful=[c for c in report.cases if c['legacy']['exception'] is None and c['native']['exception'] is None]
    if not successful:
        raise VerificationIncomplete(dict(stage='coverage',errors=['No successful original/native case; exception-only agreement is insufficient']))
    from runtime.behavior_conversion.native_metadata import inspect_native
    inventory=inspect_native([NativeSourceFile.model_validate(s) for s in sources],harness)
    binding=bundle.verification_binding
    entries=[m for m in inventory['types'].get(binding.owner_type,{}).get('methods',[]) if m['name']==binding.method_name
        and [p['type'] for p in m['parameters']]==[p.type_name for p in binding.arguments]
        and (m.get('static')=='true')==binding.static_method]
    if len(entries)!=1:raise VerificationIncomplete(dict(stage='adapter',errors=['Selected entry is not uniquely resolved']))
    entry=entries[0];owner=entry.get('declaring_type',binding.owner_type)
    required='native:'+owner+'.'+binding.method_name+'('+', '.join(p['type'] for p in entry['parameters'])+')'
    observed={p['id'] for c in report.cases for p in c['native']['probes']}
    if required not in observed:
        raise VerificationIncomplete(dict(stage='adapter',errors=['Comparison did not execute the selected production entry'],required_entry=required))
    gaps=[b for b in report.coverage.get('branches',[]) if b['unexercised_outcomes']]
    unresolved=report.coverage.get('unresolved_edges',[])
    if unresolved or session.executable_settings.require_branch_coverage and gaps:
        raise VerificationIncomplete(dict(stage='coverage',gaps=gaps,unresolved_edges=unresolved,
            coverage_expansion=report.execution_environment['coverage_expansion'],
            evidence=str(session.attempt),errors=['Uncovered or unresolved original behavior; no automatic code correction']))
    evidence=session.attempt/'comparison/boundary-comparison.json'
    session.last_report=dict(verification_version=VERSION,source_manifest_hash=structure['source_manifest_hash'],
        configuration_hash=structure['configuration_hash'],candidate_hash=structure['candidate_hash'],evidence=str(session.attempt),
        structural_report_hash=_hash(session.attempt/'boundary-structure.json'),report_hash=_hash(evidence),
        boundary_status=report.status,observed_cases=len(report.cases),coverage=report.coverage,
        warnings=['Observed-case agreement is not exhaustive equivalence'],observed_native_apis=sorted(observed),
        build_validation=build_validation,binding=binding.model_dump(mode='json'),required_native_entry=required,exhaustive_equivalence=False)
    session.last_report.update(input_generation=generation,input_cases_hash=_hash(session.attempt/'input-cases.json'))
    session.last_report['comparison_summary']=report.execution_environment['comparison_summary']
    session.last_report['coverage_expansion']=report.execution_environment['coverage_expansion']
    if gaps:session.last_report['warnings'].append('Original branch outcomes remain unexercised under explicit nonblocking coverage policy')
    from runtime.behavior_conversion.comparison_strength import measure_comparisons
    measurement=measure_comparisons(session,native,legacy,all_cases,harness,
        owned_paths=[file.path for file in bundle.files if file.path.startswith('src/main/java/')])
    if measurement is not None:session.last_report['comparison_strength']=measurement
    from runtime.behavior_conversion.verification_test_strength import prepare_measurement
    prepare_measurement(session,project,bundle)


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _save(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(path)
