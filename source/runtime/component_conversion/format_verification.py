"""Run the existing whole-format technical ladder without writing unit acceptance receipts."""
import shutil
from pathlib import Path
from models.native_unit_bundle import NativeUnitBundle,NativeSourceFile
from models.operation_data_contract import UnitContract
from models.unit_verification_boundary import UnitVerificationBoundary
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession
from tools.behavior_verification.java_tool import default_tool_path


def format_bundle(candidate, request, dependency_files):
    """Give the checker the assembled source tree and the original unit's declarative bindings."""
    composed=request['configured_format']; key=next(iter(candidate.contracts))
    if candidate.checklist_implementations:
        raise ValueError('Whole formats use checklist_answers, not duplicate component-only mappings')
    files={**dependency_files,**{file.path:file.content for file in candidate.files}}
    return NativeUnitBundle(files=[NativeSourceFile(path=path,content=text) for path,text in files.items()],
        dependencies=candidate.dependencies,coverage=candidate.coverage,evidence_ids=candidate.evidence_ids,
        unresolved_questions=candidate.unresolved_questions,checklist_answers=candidate.checklist_answers,
        verification_binding=candidate.verification_binding,unit_contract=UnitContract(unit_id=composed['unit_id'],
            apis=candidate.contracts[key].apis,requirements=request['requirements'],evidence_ids=candidate.evidence_ids))


def session_for(config,profile,unit,boundary):
    """Reuse existing parser/binding, controlled-input and source/native comparison policies."""
    return UnitVerificationSession(config,unit,UnitVerificationBoundary.model_validate(boundary),tool=default_tool_path(),
        policy=profile.unit_verification_policy,authorizations=profile.unit_verification_authorizations,
        mutation_settings=profile.unit_mutation_testing,executable_settings=profile.executable_verification)


def retain_format_evidence(session, project):
    """Retain comparison/static artifacts inside the component's checked manifest."""
    if session.last_report is None: raise ValueError('Format comparison did not complete')
    shutil.copytree(session.attempt,Path(project)/'verification')
    return dict(session.last_report,retained_evidence='verification',final_unit_acceptance=False)


def recheck_format(config,profile,contracts,results,project,context,validation,report,units,boundaries):
    """A saved format is rebuilt and compared again against current original evidence."""
    if config is None or units is None or boundaries is None:
        raise ValueError('Format reuse requires current original unit/boundary evidence')
    from models.native_format_component_bundle import NativeFormatComponentBundle
    composed=report['configured_format']; identity=composed['unit_id']
    if identity not in units or identity not in boundaries['boundaries']:
        raise ValueError('Saved format is outside the selected original boundaries')
    files=[dict(path=path.relative_to(project).as_posix(),content=path.read_text(encoding='utf-8'))
           for path in (Path(project)/'src').rglob('*.java')]
    candidate=NativeFormatComponentBundle(contracts=contracts,files=files,evidence_ids=report['format_candidate']['evidence_ids'],
        checklist_answers=report['format_candidate']['checklist_answers'],verification_binding=report['format_candidate']['verification_binding'])
    bundle=format_bundle(candidate,dict(configured_format=composed,requirements=report['format_candidate']['requirements']),{})
    session=session_for(config,profile,units[identity],boundaries['boundaries'][identity])
    session.static(bundle)
    session.compare(project,context,bundle,build_validation=validation.model_dump(mode='json'))
    return session.last_report
