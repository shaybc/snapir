"""Select exact parser ranges, retaining a local catalog for bounded expansion."""
import hashlib
import re
from tools.component_inventory_tools.identity import stable_id


def source_catalog(payload,files,inventory):
    """Catalog original methods and native declarations without AI summaries."""
    sources={s['identity']:s for s in payload.get('sources',[])}
    ranges=inventory.get('evidence_ranges',[]);catalog={}
    for identity,source in sources.items():
        digest=hashlib.sha256(source['content'].encode('utf-8')).hexdigest()
        if source.get('content_hash') and source['content_hash']!=digest:raise ValueError('Original evidence hash changed: '+identity)
        spans=[r for r in ranges if r.get('source')==identity]
        spans=[*spans,dict(start_line=1,end_line=max(1,len(source['content'].splitlines())),kind='CompleteSource',name=identity)]
        for span in spans:_add(catalog,'original',identity,source['content'],span,digest)
    for path,text in files.items():
        spans=[r for r in ranges if r.get('path')==path and not r.get('source')]
        if not spans:spans=[dict(start_line=1,end_line=max(1,len(text.splitlines())),kind='CompleteSource',name=path)]
        for span in spans:_add(catalog,'native',path,text,span,stable_id(text))
    return catalog


def _add(catalog,kind,owner,text,span,digest):
    start,end=int(span['start_line']),int(span['end_line'])
    excerpt=''.join(text.splitlines(keepends=True)[start-1:end])
    key=stable_id(kind,owner,digest,start,end)
    catalog[key]=dict(evidence_id=key,kind=kind,owner=owner,source_hash=digest,start_line=start,end_line=end,
                      declaration_kind=span['kind'],name=span['name'],content=excerpt)


def evidence_for(items,catalog,extra=()):
    """Enclosing original declarations are mandatory; native choices can expand by catalog ID."""
    mandatory=set();native=[]
    for item in items:
        candidates=[(key,value) for key,value in catalog.items() if value['kind']=='original' and value['owner']==item['source_identity']
                    and value['start_line']<=item['start_line']<=item['end_line']<=value['end_line']]
        if not candidates:raise ValueError('No original declaration range contains checklist item: '+item['id'])
        selected=min(candidates,key=lambda pair:pair[1]['end_line']-pair[1]['start_line'])
        if item.get('source_hash') and selected[1]['source_hash']!=item['source_hash']:raise ValueError('Checklist original source revision mismatch: '+item['id'])
        mandatory.add(selected[0])
        # Include declarations/constants for the same original class, not unrelated operations.
        mandatory.update(k for k,v in catalog.items() if v['kind']=='original' and v['owner']==item['source_identity'] and v['declaration_kind'] in {'FieldDeclaration','InitializerDeclaration'})
    words=set(re.findall(r'[A-Za-z_$][\w$]{2,}', ' '.join(i.get('detail','')+' '+i.get('excerpt','') for i in items)))
    for key,value in catalog.items():
        if value['kind']=='native':native.append((len(words.intersection(re.findall(r'[A-Za-z_$][\w$]{2,}',value['content']))),key))
    native=[key for _,key in sorted(native,key=lambda p:(-p[0],p[1]))]
    unknown=set(extra)-set(catalog)
    if unknown:raise ValueError('Unknown evidence catalog IDs: '+str(sorted(unknown)))
    return mandatory|set(extra),native


def compact_index(catalog):
    """A navigation index advertises omitted evidence instead of silently hiding it."""
    groups={}
    for key,value in sorted(catalog.items()):
        group=groups.setdefault((value['kind'],value['owner']),[])
        group.append(dict(evidence_id=key,name=value['name'],start_line=value['start_line'],end_line=value['end_line']))
    return [dict(kind=kind,owner=owner,ranges=ranges) for (kind,owner),ranges in sorted(groups.items())]
