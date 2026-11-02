"""Execute one durable AI responsibility at a time with non-resetting role budgets."""
import json
from tools.state_store_tools import staged_conversion_state as state


class StageTasks:
    """Reuse canonical model transport, request sizing, correction and persisted attempts."""
    def __init__(self,conn,config,profile,identity,revision,model_call,validator,label='',implementation_attempt=None,*,category=None,payload=None):
        self.conn,self.config,self.profile=conn,config,profile
        self.identity,self.revision,self.label=identity,revision,label or identity
        self.validator,self.implementation_attempt=validator,implementation_attempt
        self.model_call=model_call
        self.category,self.payload=category,payload
        from runtime.model_execution.adk_executor import AdkExecutor
        self.call=model_call or AdkExecutor(profile).execute

    def fresh(self):
        """Verify original task scope and source freshness before each stage operation."""
        if self.category:
            from runtime.behavior_conversion.stage_scope import verify_parent
            verify_parent(self.conn,self.config,self.profile,self.category,self.identity,self.payload)
        getattr(self.validator,'fresh',lambda:None)()

    def ask(self,stage,request,prompt,schema,check,*,request_limit=None):
        """Reserve only actual model calls; revalidating cached artifacts costs no attempt."""
        from runtime.behavior_conversion.generation import _generate
        fresh=self.fresh
        settings=self.profile.model_copy(update=dict(staged_unit_conversion=False,side_road_conversion=False))
        if request_limit is not None:settings.behavior_context_chars=min(settings.behavior_context_chars,request_limit)
        state.read(self.conn,self.config.run_id,self.identity,self.revision,stage)
        current=None;raw=None
        def counted(instruction,encoded):
            nonlocal current,raw
            fresh()
            if stage=='implementation':
                from runtime.behavior_conversion.implementation_repair import repair_baseline,focused_repair
                from runtime.behavior_conversion.request_context import encode_request
                baseline=repair_baseline(state.read(self.conn,self.config.run_id,self.identity,self.revision,'implementation'),
                    state.read(self.conn,self.config.run_id,self.identity,self.revision,'compile'))
                _,encoded=encode_request(focused_repair(json.loads(encoded),baseline),instruction,settings.behavior_context_chars)
            current=state.reserve(self.conn,self.config.run_id,self.identity,self.revision,stage,
                                  self.profile.max_agent_task_retries,json.loads(encoded))
            if stage=='implementation' and self.implementation_attempt:self.implementation_attempt()
            try:
                raw=self.call(instruction,encoded)
                state.finish(self.conn,self.config.run_id,self.identity,self.revision,stage,current,response=raw)
                return raw
            except Exception as error:
                state.finish(self.conn,self.config.run_id,self.identity,self.revision,stage,current,error=error)
                raise
        def checked(output,cached=False):
            try:
                fresh()
                check(output)
            except Exception as error:
                if current:state.finish(self.conn,self.config.run_id,self.identity,self.revision,stage,current,response=raw,error=error)
                from runtime.behavior_conversion.verification_mode import executable_mode
                if executable_mode(self.profile):
                    from runtime.behavior_conversion.failure_routing import stage_error
                    routed=stage_error(error,stage)
                    if routed is not error:raise routed from error
                raise
        from runtime.behavior_conversion.stage_scope import authorized_stage
        with authorized_stage(self.conn,self.config,settings,'staged_'+stage,self.identity+':'+self.revision,fresh):
            try:
                result,fingerprint=_generate(self.conn,self.config,settings,'staged_'+stage,self.identity+':'+self.revision,
                    prompt,request,schema,validator=checked,model_call=counted,label=self.label+' / '+stage,require_coverage=False)
            except ValueError as error:
                from runtime.behavior_conversion.verification_mode import executable_mode
                if executable_mode(self.profile) and ('context budget' in str(error) or str(error).startswith('Staged '+stage+' attempt budget exhausted')):
                    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
                    raise VerificationIncomplete(dict(stage='stage_budget',owner=stage,errors=[str(error)])) from error
                raise
        state.retain(self.conn,self.config.run_id,self.identity,self.revision,stage,result.model_dump(mode='json'),fingerprint)
        return result
