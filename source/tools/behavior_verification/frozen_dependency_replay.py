"""Reuse exact saved production, metadata and tests through current canonical validators."""
import json
from contextlib import contextmanager
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.format_metadata_compatibility import discard_internal_chain_metadata
from runtime.behavior_conversion.stage_tasks import StageTasks
from runtime.component_conversion.saved_experiment import candidate_key
from tools.behavior_verification.experimental_checkpoint import verify_saved_inputs
from tools.behavior_verification.format_regeneration_scope import guarded_model_call
from tools.component_inventory_tools.identity import stable_id


def saved_stage(conn,identity,production_hash,stage):
    """A retained stage is reusable only when its compile proof names the exact frozen Java."""
    rows=conn.execute("SELECT t.artifact_json,c.artifact_json FROM staged_conversion_tasks t JOIN staged_conversion_tasks c ON c.run_id=t.run_id AND c.identity=t.identity AND c.revision=t.revision AND c.stage='compile' WHERE t.identity=? AND t.stage=? AND t.status='retained' AND t.artifact_json IS NOT NULL ORDER BY t.updated_at DESC",(identity,stage))
    for artifact,proof in rows:
        if proof and json.loads(proof).get('production_hash')==production_hash:return json.loads(artifact)
    return None


@contextmanager
def frozen_dependency_replay(conn,saved,report,save):
    """Never generate or repair production; current compilation and tests remain mandatory."""
    original_init,original_ask=StageTasks.__init__,StageTasks.ask
    def initialize(self,*args,**kwargs):
        original_init(self,*args,**kwargs);self.call=guarded_model_call(self.call,False)
        item=saved.get(candidate_key((self.payload or {}).get('components',{})))
        if item is None:raise ValueError('No exact saved production candidate; generation disabled: '+self.identity)
        production,digest,prior=item;verify_saved_inputs(prior,self.payload)
        self.validator.frozen_implementation=production.model_copy(deep=True);self.validator.frozen_implementation_hash=digest
        tests=saved_stage(conn,prior['group_id'],digest,'tests')
        if tests and set(self.payload.get('requirements',{}))<=set(tests.get('coverage',{})):
            self.validator.frozen_tests=NativeTestBundle.model_validate(tests)
        self.dependency_replay_metadata=saved_stage(conn,prior['group_id'],digest,'semantic_metadata')
        report['groups'][self.identity]=dict(labels=[node['label'] for node in self.payload['components'].values()],
            revision=self.revision,java_hash=digest,old_identity=prior['group_id'],retained_tests=hasattr(self.validator,'frozen_tests'))
        save()
    def ask(self,stage,request,prompt,schema,check,**kwargs):
        value=getattr(self,'dependency_replay_metadata',None)
        if stage=='semantic_metadata' and value is not None:
            self.fresh();metadata=schema.model_validate(discard_internal_chain_metadata(value));check(metadata)
            from tools.state_store_tools import staged_conversion_state
            staged_conversion_state.retain(self.conn,self.config.run_id,self.identity,self.revision,stage,metadata.model_dump(mode='json'),stable_id(metadata.model_dump(mode='json')))
            return metadata
        return original_ask(self,stage,request,prompt,schema,check,**kwargs)
    StageTasks.__init__,StageTasks.ask=initialize,ask
    try:yield
    finally:StageTasks.__init__,StageTasks.ask=original_init,original_ask
