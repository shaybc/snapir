"""Complete configured roots with the canonical Java syntax dependency resolver."""
import hashlib
from copy import deepcopy
from pathlib import Path
from models.conversion_component import ConversionComponent
from tools.source_discovery_tools import discover_java_sources,resolve_indexed_source
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.conversion_tools.java_dependency_readiness import check_java_dependencies
from tools.java_analysis_tools.java_text import read_java_text
from tools.behavior_verification.boundary_contracts import boundary_contract,digest


def discover(spec,profile):
    """Use XML-selected roots plus transitive source dependencies; never replace originals."""
    unit=deepcopy(spec.unit);unit['kind']='request_unformat' if spec.action=='unformat' else 'response_format'
    unit.setdefault('sources',[]);unit.setdefault('configuration_xml','');unit.setdefault('referenced_definitions',[])
    unit.setdefault('unit_id','original-'+digest(unit['effective_configuration'])[:24]);unit.setdefault('fingerprint',digest(unit['effective_configuration']))
    unit.setdefault('operation_identity','standalone')
    boundary=boundary_contract(unit)
    if boundary.issues:raise ValueError('; '.join(boundary.issues))
    index=discover_java_sources(profile.source_root)
    project=profile.scoped_java_projects.get(unit.get('channel','')) or profile.scoped_java_project
    if project:
        allowed={project};pending=[project]
        while pending:
            for name in index.project_references.get(pending.pop(),[]):
                if name not in allowed:allowed.add(name);pending.append(name)
        index=index.model_copy(update={'classes':{name:[p for p in paths if index.class_projects[p] in allowed] for name,paths in index.classes.items() if any(index.class_projects[p] in allowed for p in paths)}})
    roots=set(boundary.setup_class_roots)|set(spec.input_types)|{spec.framework.context_class,spec.framework.tag_class}
    visible={project} if project else set()
    for name in roots:
        path=resolve_indexed_source(index,name,project)
        if path:visible.add(index.class_projects[path])
    pending=list(visible)
    while pending:
        for dependency in index.project_references.get(pending.pop(),[]):
            if dependency not in visible:visible.add(dependency);pending.append(dependency)
    source_roots=[root for name in visible for root in index.source_roots.get(name,[])]
    classpath=discover_java_classpath(profile.source_root,list(dict.fromkeys([*profile.classpath_jars, *profile.framework_jars])),profile.eclipse_classpath_variables,visible_source_roots=source_roots,
        containers=getattr(profile,'eclipse_classpath_containers',{}),project_containers=getattr(profile,'eclipse_project_classpath_containers',{}))
    if classpath.issues:raise ValueError('; '.join(classpath.issues))
    from tools.source_discovery_tools.binary_resolution import classpath_for_project,ordered_library_paths
    owner_paths=index.classes.get(boundary.implementation_class,[])
    comparison_project=project or (index.class_projects[owner_paths[0]] if len(owner_paths)==1 else (next(iter(visible)) if len(visible)==1 else None))
    inventory=classpath
    classpath=classpath_for_project(inventory,comparison_project)
    components=[];reasons={}
    for name in sorted(roots):
        path=resolve_indexed_source(index,name,project)
        if path:
            if any(p.startswith('jar:') for p in classpath.classes.get(name,[])):raise ValueError('Ambiguous source/JAR class: '+name)
            raw=Path(path).read_bytes();components.append(ConversionComponent(kind='ibm_java',logical_id=name,source_file=path,
                source_hash=hashlib.sha256(raw).hexdigest(),source_content=read_java_text(path),origin='configured element/framework initialization'))
            reasons[name]='configured element or framework initialization'
        elif len(classpath.classes.get(name,[]))!=1:raise ValueError('Required class has no unique source/JAR: '+name)
    graph={}
    from tools.java_analysis_tools.source_dependencies.parser import parse_source_references
    checked,problems=check_java_dependencies(components,index,inventory,dependency_graph=graph,source_parser=lambda paths:parse_source_references(paths,strip_bom=True))
    if problems:raise ValueError('; '.join(p.detail for p in problems))
    if len(checked)>spec.max_sources or sum(len(Path(c.source_file).read_bytes()) for c in checked)>spec.max_source_bytes:
        raise ValueError('Composer unit dependency limit exceeded; no dependencies dropped')
    originals=dict(unit.get('configuration_revisions',{}));sources=[]
    for c in checked:
        if any(p.startswith('jar:') for p in classpath.classes.get(c.logical_id,[])):raise ValueError('Ambiguous source/JAR class: '+c.logical_id)
        raw=Path(c.source_file).read_bytes();h=hashlib.sha256(raw).hexdigest()
        if h!=c.source_hash:raise ValueError('Source changed during dependency discovery: '+c.source_file)
        originals[c.source_file]=h
        text=read_java_text(c.source_file,strip_bom=True,expected_hash=h,preserve_line_endings=True)
        sources.append(dict(identity=c.logical_id,content=text,content_hash=hashlib.sha256(text.encode()).hexdigest(),
            original_path=c.source_file,original_byte_hash=h))
        reasons.setdefault(c.logical_id,'Java dependency of '+', '.join(owner for owner,targets in graph.items() if c.logical_id in targets))
    # An incomplete old snapshot is a seed, never authority to hide changed original evidence.
    for old in spec.unit.get('sources',[]):
        if hashlib.sha256(old['content'].encode()).hexdigest()!=old['content_hash']:raise ValueError('Supplied source hash mismatch')
        matches=[s for s in sources if s['content']==old['content'] or s['content'].lstrip('\ufeff')==old['content'].lstrip('\ufeff')]
        if not matches:raise ValueError('Retained original source differs from configured workspace: '+old['identity'])
    unit['sources']=sources
    unit['original_input_types']=list(spec.input_types)
    libraries=ordered_library_paths(inventory,comparison_project)
    originals.update({path:value for path,value in inventory.metadata_fingerprints.items() if value is not None})
    for jar in libraries:originals[jar]=hashlib.sha256(Path(jar).read_bytes()).hexdigest()
    return unit,dict(roots=sorted(roots),included=reasons,edges={k:sorted(v) for k,v in graph.items()},originals=originals,libraries=libraries,
        classpath_metadata=inventory.metadata_fingerprints)
