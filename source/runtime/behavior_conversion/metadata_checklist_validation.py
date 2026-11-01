"""Collect independent checklist citation errors without claiming equivalence."""
from collections import Counter
from pathlib import PurePosixPath
from pydantic import ValidationError
from models.checklist_response import ChecklistResponse
from models.metadata_checklist_batch import MetadataChecklistBatch
import json


def validate_batch(raw,expected,files,*,revision,production,batch_id,allow_exclusions=False,check=None,visible=None):
    """Return valid entries, all detectable errors and explicit evidence requests."""
    errors=[];accepted={}
    def error(identity,code,message,**details):
        errors.append(dict(item_id=identity,code=code,message=message,**details))
    try:envelope=MetadataChecklistBatch.model_validate(raw)
    except ValidationError as exc:
        return dict(accepted={},errors=[dict(item_id=None,code='invalid_envelope',message=str(exc))],evidence_requests=[])
    if (envelope.task_revision,envelope.production_revision,envelope.batch_id)!=(revision,production,batch_id):
        return dict(accepted={},errors=[dict(item_id=None,code='stale_revision',message='Return the exact current task, production and batch identities')],evidence_requests=[])
    ids=[v.get('checklist_id') for v in envelope.entries if isinstance(v,dict) and isinstance(v.get('checklist_id'),str)]
    counts=Counter(ids);expected=set(expected)
    for identity in sorted(expected-set(ids)):error(identity,'missing_item','Return a response for this assigned ID')
    for identity,count in sorted(counts.items()):
        if identity not in expected:error(identity,'unknown_item','Do not return IDs outside this repair/batch')
        if count>1:error(identity,'duplicate_item','Return exactly one response for this ID')
    for index,raw_entry in enumerate(envelope.entries):
        identity=raw_entry.get('checklist_id') if isinstance(raw_entry,dict) else None
        if isinstance(identity,str) and (identity not in expected or counts[identity]!=1):continue
        try:entry=ChecklistResponse.model_validate(raw_entry)
        except ValidationError as exc:
            error(identity,'malformed_entry',str(exc),entry_index=index);continue
        start=len(errors)
        if entry.status=='unresolved':error(identity,'implementation_concern',entry.question)
        elif entry.status=='not_applicable' and not allow_exclusions:
            error(identity,'unsupported_exclusion','This component requires implementation locations; exclusions use existing whole-unit policy only')
        for location in entry.locations:
            path=PurePosixPath(location.path)
            if '\\' in location.path or ':' in location.path or path.is_absolute() or '..' in path.parts or str(path)!=location.path or not location.path.startswith('src/main/java/'):
                error(identity,'unsafe_path','Cite a canonical production Java path',path=location.path)
            elif location.path not in files:error(identity,'missing_file','Cited file is not current supplied native evidence',path=location.path)
            elif not location.excerpt.strip():error(identity,'empty_excerpt','Cite nonempty exact production code',path=location.path)
            elif location.excerpt not in files[location.path]:error(identity,'excerpt_not_found','Cite exact text from the supplied current file',path=location.path,excerpt=location.excerpt)
            elif visible is not None and not any(location.excerpt in text for text in visible.get(location.path,[])):
                error(identity,'evidence_unavailable','Request the catalog range containing this excerpt before citing it',path=location.path)
        if len(errors)==start:accepted[identity]=entry.model_dump(mode='json')
    if check and accepted:
        # Existing policy/AST checks may reject citations which only occur in comments.
        rejected=check(list(accepted.values()))
        errors.extend(rejected)
        if any(not e.get('item_id') for e in rejected):accepted={}
        else:
            for e in rejected:accepted.pop(e['item_id'],None)
    return dict(accepted=accepted,errors=errors,evidence_requests=envelope.evidence_requests)


def validate_component_mappings(mappings,expected,files):
    """Use the same aggregate report in all final component/subtree owner validators."""
    entries=[dict(checklist_id=k,status='implemented',locations=[v.model_dump(mode='json') if hasattr(v,'model_dump') else v for v in values]) for k,values in mappings.items()]
    result=validate_batch(dict(task_revision='owner',production_revision='owner',batch_id='owner',entries=entries),expected,files,
                          revision='owner',production='owner',batch_id='owner')
    if result['errors']:raise ValueError('Invalid checklist mappings: '+json.dumps(result['errors']))
