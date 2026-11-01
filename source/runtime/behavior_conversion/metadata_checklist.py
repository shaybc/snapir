"""Bounded, resumable citation mapping; existing owner validators still decide acceptance."""
import json
import logging
from collections import deque
from models.metadata_checklist_batch import MetadataChecklistBatch
from runtime.managed_conversion_response import _remove_response_fence
from runtime.behavior_conversion.response_json import clean_structural_escapes
from runtime.behavior_conversion.metadata_checklist_batches import plan_batches,build_request,split,EvidenceTooLarge
from runtime.behavior_conversion.metadata_checklist_evidence import source_catalog
from runtime.behavior_conversion.metadata_checklist_validation import validate_batch
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from agents.behavior_conversion.metadata_checklist import MAPPING
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import metadata_checklist_state as state

POLICY='metadata-checklist-v2'


def checklist_context(tasks,payload):
    """Locate whole-unit policy without making component citation success an approval."""
    session=None
    if payload.get('configured_format') and getattr(tasks.validator,'boundaries',None):
        from runtime.component_conversion.format_verification import session_for
        key=payload['configured_format']['unit_id']
        session=session_for(tasks.config,tasks.profile,tasks.validator.units[key],tasks.validator.boundaries['boundaries'][key])
    if session is None:
        from runtime.behavior_conversion.verification_ladder import active_verification
        session=active_verification()
    items=payload.get('parser_checklist') or []
    if isinstance(items,dict):items=items.get('items',[])
    if session:items=[i.model_dump(mode='json') for i in session.boundary.parser_checklist.items]
    return items,session


def mapping_enabled(tasks,payload):
    return tasks.profile.metadata_checklist_batching and bool(checklist_context(tasks,payload)[0])


def _policy_check(session,items,files,entries):
    """Apply the existing AST/exclusion policy to a revision-bound subset before retention."""
    from models.unit_checklist_answers import UnitChecklistAnswers
    from models.parser_checklist_item import ParserChecklistItem
    from tools.behavior_verification.static_checks import validate_unit_static
    boundary=session.boundary.model_copy(deep=True)
    ids={e['checklist_id'] for e in entries}
    boundary.parser_checklist.items=[ParserChecklistItem.model_validate(items[k]) for k in sorted(ids)]
    answers=UnitChecklistAnswers(unit_id=boundary.unit_id,source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash,responses=entries)
    report=validate_unit_static(session.unit,boundary,[dict(path=p,content=t) for p,t in files.items()],answers,
        tool=session.tool,policy=session.policy,authorizations=session.authorizations)
    if any(e.get('kind') in {'analysis_unavailable','invalid_contract'} for e in report.errors):
        raise VerificationIncomplete(dict(stage='metadata_checklist_tooling',errors=report.errors))
    return [dict(item_id=e.get('checklist_id'),code='policy_rejected',message=e.get('message','Existing policy rejected mapping')) for e in report.errors]


def map_checklist(tasks,payload,production,inventory):
    """Keep valid siblings, repair only unfinished IDs, and bound all descendant requests."""
    values,session=checklist_context(tasks,payload)
    if not values:return {}
    items={i['id']:i for i in values}
    if len(items)!=len(values):raise ValueError('Duplicate original checklist IDs')
    files={**getattr(tasks.validator,'stage_prerequisites',{}),**{f.path:f.content for f in production.files}}
    source_payload=dict(payload,sources=session.unit['sources'] if session else payload.get('sources',[]))
    catalog=source_catalog(source_payload,files,inventory)
    profile=tasks.profile
    revision=stable_id(POLICY,tasks.identity,tasks.revision)
    production_revision=stable_id(files)
    from models.static_check_policy import StaticCheckPolicy
    policy=StaticCheckPolicy.model_validate(session.policy or StaticCheckPolicy()) if session else profile.unit_verification_policy
    authorizations=(session.authorizations or ()) if session else profile.unit_verification_authorizations
    proof=stable_id(POLICY,values,files,catalog,policy.model_dump(mode='json'),
        [a.model_dump(mode='json') for a in authorizations],session.boundary.model_dump(mode='json') if session else None,
        profile.metadata_checklist_request_chars)
    conn,run=tasks.conn,tasks.config.run_id
    initial=plan_batches(values,profile.metadata_checklist_batch_items)
    maximum=profile.metadata_checklist_max_calls or max(1,len(initial))*profile.max_agent_task_retries*2
    limits=state.open_task(conn,run,revision,items,dict(calls=maximum,transports=profile.metadata_checklist_max_transport_calls or maximum*profile.max_model_attempts,item_attempts=profile.max_agent_task_retries))
    accepted=state.accepted(conn,run,revision,proof)
    logging.getLogger(__name__).info('Checklist task %s fixed budgets %s; %s/%s current item mappings; traceability only',revision,limits,len(accepted),len(items))
    state.mark_items(conn,run,revision,set(items)-set(accepted),'pending')
    queue=deque((ids,None,[]) for ids in initial);concerns=[]
    from runtime.model_execution.adk_executor import AdkExecutor
    # Every transport has its own persistent reservation; do not hide four retries inside one call.
    call=tasks.model_call or AdkExecutor(profile.model_copy(update={'max_model_attempts':1})).execute
    while queue:
        tasks.fresh()
        ids,parent,extra=queue.popleft();ids=[key for key in ids if key not in accepted]
        if not ids:continue
        key=stable_id(revision,production_revision,sorted(ids),sorted(extra))
        children=state.split_children(conn,run,revision,key)
        if children:
            queue.extend((child['ids'],key,child['extra']) for child in children);continue
        errors,previous=state.previous_errors(conn,run,revision,key)
        try:
            request,encoded=build_request(ids,items,catalog,profile,revision,production_revision,extra=extra,errors=errors,
                previous=previous.get('previous_entries',[]),allow_exclusions=session is not None,
                context=dict(configuration=(payload.get('configured_unit') or payload.get('configured_format') or {}).get('configuration_xml'),
                    boundary=session.boundary.model_dump(mode='json',exclude={'parser_checklist'}) if session else None,
                    exclusion_policy=policy.model_dump(mode='json') if session else None,
                    authorizations=[a.model_dump(mode='json') for a in authorizations]))
        except (EvidenceTooLarge,ValueError) as error:
            state.mark_items(conn,run,revision,ids,'evidence_incomplete')
            state.batch(conn,run,revision,key,parent,dict(ids=ids,extra=extra),'evidence_incomplete',[dict(code='request_size_or_evidence',message=str(error))])
            if len(ids)>1:
                queue.extendleft((child,key,extra) for child in reversed(split(ids)));continue
            raise VerificationIncomplete(dict(stage='metadata_checklist_evidence',item_ids=ids,errors=[str(error)])) from error
        try:logical=state.reserve_call(conn,run,revision,ids,limits)
        except ValueError as error:
            state.mark_items(conn,run,revision,ids,'terminal_failure')
            raise VerificationIncomplete(dict(stage='metadata_checklist_budget',item_ids=ids,errors=[str(error)])) from error
        state.batch(conn,run,revision,key,parent,dict(ids=ids,extra=extra,previous_entries=previous.get('previous_entries',[])),'running',errors)
        raw=None;transport_error=None
        for number in range(1,min(profile.max_model_attempts,profile.metadata_checklist_timeout_split_after)+1):
            tasks.fresh()
            try:state.reserve_transport(conn,run,revision,logical,number,request,limits)
            except ValueError as error:
                state.mark_items(conn,run,revision,ids,'terminal_failure')
                raise VerificationIncomplete(dict(stage='metadata_checklist_budget',item_ids=ids,errors=[str(error)])) from error
            try:
                raw=call(MAPPING,encoded)
                state.finish_transport(conn,run,revision,logical,number,response=raw);break
            except (OSError,TimeoutError,RuntimeError) as error:
                transport_error=error;state.finish_transport(conn,run,revision,logical,number,error=error)
                if 'timeout' not in str(error).lower() and not isinstance(error,TimeoutError):
                    raise VerificationIncomplete(dict(stage='metadata_checklist_provider',item_ids=ids,errors=[str(error)])) from error
            except Exception as error:
                state.finish_transport(conn,run,revision,logical,number,error=error)
                raise VerificationIncomplete(dict(stage='metadata_checklist_provider',item_ids=ids,errors=[str(error)])) from error
        if raw is None:
            state.batch(conn,run,revision,key,parent,dict(ids=ids,extra=extra),'split' if len(ids)>1 else 'retry',[dict(code='timeout',message=str(transport_error))])
            children=split(ids) if len(ids)>1 else [ids]
            if len(ids)>1:
                for child in children:
                    child_id=stable_id(revision,production_revision,sorted(child),sorted(extra))
                    state.batch(conn,run,revision,child_id,key,dict(ids=child,extra=extra),'pending')
            queue.extend((child,key,extra) for child in children);continue
        try:decoded=json.loads(clean_structural_escapes(_remove_response_fence(raw)))
        except (ValueError,TypeError):decoded=None
        visible={}
        for e in request['evidence']:
            if e['kind']=='native':visible.setdefault(e['owner'],[]).append(e['content'])
        check=(lambda entries:_policy_check(session,items,files,entries)) if session else None
        result=validate_batch(decoded,ids,files,revision=revision,production=production_revision,batch_id=request['batch_id'],
                              allow_exclusions=session is not None,check=check,visible=visible)
        tasks.fresh()
        state.save_items(conn,run,revision,proof,result['accepted']);accepted.update(result['accepted'])
        pending=[key for key in ids if key not in accepted]
        for identity in pending:
            codes={e['code'] for e in result['errors'] if e.get('item_id')==identity}
            status='implementation_concern' if 'implementation_concern' in codes else 'evidence_incomplete' if 'evidence_unavailable' in codes else 'needs_correction'
            state.mark_items(conn,run,revision,[identity],status)
        requested=result['evidence_requests'];unknown=set(requested)-set(catalog)
        if unknown:result['errors'].append(dict(item_id=None,code='unknown_evidence',message='Unknown catalog IDs: '+str(sorted(unknown))))
        prior=[entry for entry in (decoded or {}).get('entries',[]) if isinstance(entry,dict) and entry.get('checklist_id') in pending] if isinstance(decoded,dict) else []
        state.batch(conn,run,revision,key,parent,dict(ids=ids,extra=extra,previous_entries=prior),'mapped' if not pending else 'needs_correction',result['errors'])
        logging.getLogger(__name__).info('Checklist traceability %s/%s items mapped; %s pending in batch %s; not behavioral acceptance',len(accepted),len(items),len(pending),key)
        if pending:
            valid_requests=sorted(set(extra)|set(requested)-unknown)
            deferred={e['item_id'] for e in result['errors'] if e.get('code')=='implementation_concern'} if not requested else set()
            concerns.extend(e for e in result['errors'] if e.get('item_id') in deferred)
            pending=[identity for identity in pending if identity not in deferred]
            if not pending:continue
            # Retain precise errors for the repair's smaller identity too.
            repair=stable_id(revision,production_revision,sorted(pending),valid_requests)
            state.batch(conn,run,revision,repair,key,dict(ids=pending,extra=valid_requests,previous_entries=prior),'needs_correction',
                        [e for e in result['errors'] if e.get('item_id') in pending or not e.get('item_id')])
            queue.append((pending,key,valid_requests))
    if set(accepted)!=set(items):
        raise VerificationIncomplete(dict(stage='metadata_checklist_implementation_concern' if concerns else 'metadata_checklist',
            missing_ids=sorted(set(items)-set(accepted)),concerns=concerns,
            action='Investigate original/native code or behavioral evidence; model concerns do not prove implementation defects'))
    if session:
        return dict(checklist_answers=dict(unit_id=session.boundary.unit_id,source_manifest_hash=session.boundary.source_manifest_hash,
            configuration_hash=session.boundary.configuration_hash,responses=[accepted[k] for k in sorted(accepted)]))
    return dict(checklist_implementations={key:value['locations'] for key,value in sorted(accepted.items())})
