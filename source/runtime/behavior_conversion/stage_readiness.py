"""Record fresh stage gates without confusing build readiness with behavioral acceptance."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import staged_conversion_state as state
from runtime.behavior_conversion.failure_routing import AdapterRepairRequired,record_correction
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete

_test_gate=ContextVar('staged_test_readiness',default=None)
VERSION='staged-readiness-v1'


def prepare_metadata(tasks,payload,production,inventory,bundle,check):
    """Repair invocation wiring here, before a tests-only call can consume its errors."""
    state.invalidate_readiness(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'binding')
    compiled=state.read(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'compile')
    proof=json.loads(compiled['artifact_json']) if compiled['artifact_json'] else None
    if (compiled['status']!='retained' or not proof or stable_id(proof)!=compiled['artifact_hash'] or
            proof.get('production_hash')!=stable_id(production.model_dump(mode='json')) or
            proof.get('validation',{}).get('build_passed') is not True):
        raise VerificationIncomplete(dict(stage='implementation_readiness',errors=['Fresh production compile evidence is required before test generation']))
    repaired=False
    while True:
        try:
            tasks.fresh()
            check(bundle)
            tasks.fresh()
            receipt=dict(version=VERSION,acceptance=False,production_hash=stable_id(production.model_dump(mode='json')),
                production_files_hash=stable_id([f.model_dump(mode='json') for f in production.files]),
                source_hash=stable_id(payload),api_hash=stable_id(inventory['apis']),
                binding=bundle.verification_binding.model_dump(mode='json') if getattr(bundle,'verification_binding',None) else None,
                dependencies=[d.model_dump(mode='json') for d in getattr(bundle,'dependencies',[])],
                compile_hash=compiled['artifact_hash'],
                verification_policy=tasks.profile.executable_verification.model_dump(mode='json'))
            state.retain(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,
                'implementation_ready',receipt,stable_id(receipt))
            return receipt
        except AdapterRepairRequired as error:
            from runtime.behavior_conversion.verification_mode import conversion_mode
            if conversion_mode(tasks.profile):
                raise VerificationIncomplete(dict(stage='conversion_readiness',errors=[str(error)],
                    action='Resolve native production wiring; comparison adapter generation is disabled')) from error
            if repaired:record_correction(tasks,'adapter',error.verification_feedback)
            from runtime.behavior_conversion.executable_adapters import resolve_adapter
            context=dict(payload);context.update(getattr(error,'preparation_context',{}))
            candidate=production.model_copy(update={'files':getattr(error,'preparation_files',production.files)})
            bundle.verification_binding=resolve_adapter(tasks,context,candidate,
                getattr(error,'preparation_inventory',inventory),repair_feedback=error.verification_feedback)
            repaired=True


@contextmanager
def testing_gate(tasks,bundle):
    """Bind executed-test evidence to the exact current source/binding candidate."""
    ready=state.read(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'implementation_ready')
    proof=json.loads(ready['artifact_json']) if ready['artifact_json'] else None
    production=[f.model_dump(mode='json') for f in bundle.files if f.path.startswith('src/main/java/')]
    binding=getattr(bundle,'verification_binding',None)
    if (ready['status']!='retained' or not proof or stable_id(proof)!=ready['artifact_hash'] or
            proof.get('production_files_hash')!=stable_id(production) or
            proof.get('binding')!=(binding.model_dump(mode='json') if binding else None)):
        raise VerificationIncomplete(dict(stage='test_readiness',errors=['Current implementation and binding must be ready before tests execute']))
    state.invalidate_readiness(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'tests')
    token=_test_gate.set((tasks,bundle))
    try:yield
    finally:_test_gate.reset(token)


def record_test_build(validation,files,dependencies,*,require_tests=True):
    """Called after successful build/JUnit, before the comparison callback executes."""
    current=_test_gate.get()
    if current is None or not require_tests:return
    tasks,bundle=current
    expected={f.path:f.content for f in bundle.files if f.path.startswith('src/test/java/')}
    if not expected or any(files.get(path)!=text for path,text in expected.items()):
        raise VerificationIncomplete(dict(stage='test_readiness',errors=['The built test files do not match the current test candidate']))
    if not validation.build_passed or not validation.tests_passed or validation.test_count<1 or validation.issues:
        raise VerificationIncomplete(dict(stage='test_readiness',errors=['Executed passing JUnit evidence is required']))
    tasks.fresh()
    receipt=dict(version=VERSION,acceptance=False,candidate_hash=stable_id(bundle.model_dump(mode='json')),
        built_files_hash=stable_id(files),dependencies=[d.model_dump(mode='json') for d in dependencies],
        build_validation=validation.model_dump(mode='json'))
    from runtime.test_assets.preparation import current
    assets=current()
    if assets:receipt['fixture_manifest_hash']=assets['manifest_hash']
    state.retain(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'tests_ready',receipt,stable_id(receipt))
