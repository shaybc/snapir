"""Generate bounded XML cases while retaining nested and repeated occurrence identities."""
import hashlib
import json
import random
import re
from xml.sax.saxutils import escape
from models.boundary_case import BoundaryCase
from tools.behavior_verification.input_domains import domain_sampler

VERSION='structured-inputs-v1'
MISSING=object()


def generate_xml_cases(unit,boundary,settings):
    """Sample exact configured element paths; unsupported layouts never become flat XML."""
    definitions={item['definition_id']:item for item in unit.get('referenced_definitions',[])}
    nodes={};fields={};collections={};omitted=0
    sample=domain_sampler(boundary.parser_checklist,settings.max_domain_values)
    def expand(node,path,active=frozenset()):
        nonlocal omitted
        if len(path)>64:raise ValueError('XML input nesting budget exceeded')
        attributes=dict(node.get('attributes',{}));children=node.get('children',[])
        reference=node.get('reference_definition_id')
        if reference:
            if reference in active or reference not in definitions:raise ValueError('Unavailable/cyclic format reference')
            target=definitions[reference]
            if attributes.get('dataName') and attributes['dataName']!=target.get('attributes',{}).get('dataName'):
                raise ValueError('Reference name overrides need an explicit supported XML layout')
            return expand(target,path,active|{reference})
        name=attributes.get('dataName')
        if name and not re.fullmatch(r'[A-Za-z_][\w.-]*',name):raise ValueError('Explicit simple XML element names are required')
        maximum=attributes.get('maxOccurs','1')
        minimum=attributes.get('minOccurs','1')
        if not minimum.isdigit() or int(minimum)>settings.max_collection_items:raise ValueError('XML minimum occurrence exceeds collection budget or is unsupported')
        minimum=int(minimum)
        if node.get('collection_kind')=='indexed' and 'maxOccurs' not in attributes:
            raise ValueError('Indexed format has no explicit XML occurrence layout')
        if maximum!='1':
            if maximum!='unbounded' and (not maximum.isdigit() or int(maximum)<1):raise ValueError('Unsupported XML maxOccurs')
            if not name:raise ValueError('Repeated XML occurrence needs an explicit element name')
            cap=min(settings.max_collection_items,int(maximum)) if maximum!='unbounded' else settings.max_collection_items
            if minimum>cap:raise ValueError('Inconsistent XML occurrence bounds')
            collections[path]=(max(1,minimum),sorted({0,1,min(2,cap),cap,minimum}))
        elif minimum>1:raise ValueError('Inconsistent XML occurrence bounds')
        item=dict(name=name,children=[expand(child,path+(index,),active) for index,child in enumerate(children)])
        if name:
            nodes[path]=item
            if not children:
                baseline,values,truncated=sample(attributes)
                fields[path]=(baseline,values);omitted+=truncated
        return item
    tree=expand(unit['effective_configuration'],())
    def roots(node):return [node] if node['name'] else [root for child in node['children'] for root in roots(child)]
    if len(roots(tree))!=1 or not fields:raise ValueError('Automatic XML inputs require exactly one configured root and leaf fields')
    root_path=next(path for path,item in nodes.items() if item is roots(tree)[0])
    if root_path in collections:raise ValueError('Repeated document roots need an explicit supported XML layout')
    baseline={path:value[0] for path,value in fields.items()}
    baseline_counts={path:value[0] for path,value in collections.items()}
    def candidates():
        yield 'baseline',baseline,baseline_counts
        for path,item in nodes.items():
            values=[MISSING,None,''] if item['children'] else [MISSING,None,*fields[path][1]]
            for value in values:yield 'path:'+_path(path),{**baseline,path:value},baseline_counts
        for path,(_,counts) in collections.items():
            for count in counts:yield 'count:'+_path(path),baseline,{**baseline_counts,path:count}
        rng=random.Random(settings.seed)
        for _ in range(settings.random_cases):
            yield 'seeded_combination',{p:rng.choice([MISSING,None,*v[1]]) for p,v in fields.items()},baseline_counts
    seen=set();result=[]
    def render(node,path,row,counts,root=False):
        name=node['name'];value=row.get(path)
        pieces=[];size=0
        for index,child in enumerate(node['children']):
            piece=render(child,path+(index,),row,counts,root and not name);size+=len(piece)
            if size>settings.max_case_chars:raise ValueError('XML input size budget exceeded')
            pieces.append(piece)
        children=''.join(pieces)
        if not name:return children
        if path in row and value is MISSING:return ''
        namespace=' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' if root else ''
        if path in row and value is None:text='<'+name+namespace+' xsi:nil="true"/>'
        else:
            body=children if node['children'] and path not in row else escape(str(row.get(path,'')))
            text='<'+name+namespace+'>'+body+'</'+name+'>'
        count=counts.get(path,1)
        if len(text)*count>settings.max_case_chars:raise ValueError('XML input size budget exceeded')
        return text*count
    for label,row,counts in candidates():
        xml=render(tree,(),row,counts,True)
        if len(xml)>settings.max_case_chars:raise ValueError('XML input size budget exceeded')
        # A missing/nil root is intentionally sampled; namespaces are explicit.
        if xml in seen:continue
        seen.add(xml)
        identity=hashlib.sha256((str(settings.seed)+':'+xml).encode()).hexdigest()[:20]
        result.append(BoundaryCase(case_id=identity,input_xml=xml,random_seed=settings.seed,clock_millis=settings.clock_millis,labels=[label,VERSION]))
        if len(result)>settings.max_cases:raise ValueError('Structured input case budget exceeded')
    paths=[dict(occurrence=_path(path),xml_path='/'+ '/'.join(nodes[path[:n]]['name'] for n in range(len(path)+1) if path[:n] in nodes)) for path in sorted(nodes)]
    return result,dict(version=VERSION,sampled_paths=len(nodes),paths=paths,collection_paths=len(collections),domain_values_omitted=omitted)


def _path(path):return '/'.join(map(str,path)) or 'root'
