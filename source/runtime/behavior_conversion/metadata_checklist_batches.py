"""Deterministic method-based grouping and complete serialized request measurement."""
import json
import logging
from models.checklist_response import ChecklistResponse
from models.metadata_checklist_batch import MetadataChecklistBatch
from agents.behavior_conversion.metadata_checklist import MAPPING
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.metadata_checklist_evidence import evidence_for,compact_index
from tools.component_inventory_tools.identity import stable_id


class EvidenceTooLarge(ValueError):
    """One item cannot fit with sufficient exact evidence; never silently truncate it."""


def plan_batches(items,size):
    groups={}
    for item in sorted(items,key=lambda i:(i['source_identity'],i.get('code_node_id',''),i['start_line'],i['id'])):
        groups.setdefault((item['source_identity'],item.get('code_node_id','')),[]).append(item['id'])
    result=[];current=[];source=None
    for (owner,_),ids in groups.items():
        for n in range(0,len(ids),size):
            part=ids[n:n+size]
            if current and (source!=owner or len(current)+len(part)>size):result.append(current);current=[]
            current+=part;source=owner
    if current:result.append(current)
    return result


def build_request(ids,items,catalog,profile,revision,production,*,extra=(),errors=(),previous=(),allow_exclusions=False,context=None):
    """Reserve response space and include schema/instructions in every preflight check."""
    selected=[items[key] for key in ids]
    required,ranked=evidence_for(selected,catalog,extra)
    batch_id=stable_id(revision,production,sorted(ids),sorted(extra))
    feedback=[{k:(v[:600]+' [truncated; full diagnostic retained locally]' if isinstance(v,str) and len(v)>600 else v) for k,v in e.items()} for e in errors]
    prior=[]
    for entry in previous:
        prior.append(dict(checklist_id=entry.get('checklist_id'),status=entry.get('status'),
            locations=[dict(path=location.get('path'),excerpt=str(location.get('excerpt',''))[:600]) for location in entry.get('locations',[])[:8] if isinstance(location,dict)],
            note='Repair context only; full rejected entry is retained locally'))
    payload=dict(task_revision=revision,production_revision=production,batch_id=batch_id,assigned_items=selected,
        evidence_catalog=compact_index(catalog),evidence=[catalog[k] for k in sorted(required)],
        errors=feedback,previous_entries=prior,allow_exclusions=allow_exclusions,
        context=context or {},entry_schema=ChecklistResponse.model_json_schema(),schema=MetadataChecklistBatch.model_json_schema())
    from agents.behavior_conversion.metadata_checklist import CHAIN_MAPPING
    instruction=MAPPING+(CHAIN_MAPPING if (context or {}).get('format_chain_policy') else '')
    limit=min(profile.behavior_context_chars,profile.metadata_checklist_request_chars)-profile.metadata_checklist_response_chars
    def fits(value,*,optional=False):
        from runtime.composer_behavior_context import attach_composer_behavior
        request=attach_composer_behavior(value);encoded=json.dumps(request,ensure_ascii=False)
        total=len(encoded)+len(instruction)
        if total>limit:
            message=('Metadata evidence exceeds reserved request budget: '
                f'effective_limit_chars={limit}, payload_chars={len(encoded)}, instruction_chars={len(instruction)}, '
                f'total_chars={total}, response_reserve_chars={profile.metadata_checklist_response_chars}, '
                f'checklist_cap_chars={profile.metadata_checklist_request_chars}, behavior_cap_chars={profile.behavior_context_chars}')
            logging.getLogger(__name__).log(logging.DEBUG if optional else logging.WARNING,'%s; batch_id=%s',message,batch_id)
            raise ValueError(message)
        return request,encoded
    try:request,encoded=fits(payload)
    except ValueError as error:raise EvidenceTooLarge(str(error)) from error
    candidates=0;last_native_rejection=None
    for key in ranked:
        if key in required:continue
        if candidates>=max(4,len(selected)):break
        proposed=dict(payload,evidence=[*payload['evidence'],catalog[key]])
        try:new_request,new_encoded=fits(proposed,optional=True)
        except ValueError as error:last_native_rejection=str(error);continue
        payload=proposed;request,encoded=new_request,new_encoded;candidates+=1
    if not any(e['kind']=='native' for e in payload['evidence']):
        message='Assigned items leave no room for native evidence; split this batch or request a smaller exact range'
        if last_native_rejection:message+='; last_native_candidate: '+last_native_rejection
        logging.getLogger(__name__).warning('%s; batch_id=%s',message,batch_id)
        raise EvidenceTooLarge(message)
    return encode_request(payload,instruction,limit)


def split(ids):
    if len(ids)<2:raise EvidenceTooLarge('Single checklist item cannot be split further')
    middle=len(ids)//2
    return [ids[:middle],ids[middle:]]
