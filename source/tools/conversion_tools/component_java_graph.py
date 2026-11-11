"""Plan only the qualified Java dependency closure requested by a configured component."""
from models.planned_conversion_component import PlannedConversionComponent
from tools.conversion_tools.scoped_reuse.fingerprints import digest


class ComponentJavaGraph:
    """Resolve per-operation source choices; node keys also bind transitive resolution choices."""
    def __init__(self, origins, components, external=()):
        self.origins={}
        for origin in origins:
            records=self.origins.setdefault(origin['fqcn'],[])
            if origin not in records: records.append(origin)
        for record in external:
            if record['class_name'] not in self.origins:
                self.origins[record['class_name']]=[dict(fqcn=record['class_name'],status='explicit_external',evidence=record)]
        self.components=components
        self.keys={}

    def description(self,name):
        """Keep missing/competing origins explicit rather than choosing one by class name."""
        candidates=self.origins.get(name,[])
        if len(candidates)!=1:
            return dict(fqcn=name,status='unresolved',candidates=sorted(candidates,key=digest),
                        required_classes=sorted({dependency for item in candidates for dependency in item.get('required_classes',[])}))
        origin=candidates[0]
        result={key:origin[key] for key in ('fqcn','status','definition_id','source_hash','source_file','source_project',
            'profile_project','location','evidence','dependencies','required_classes') if key in origin}
        if 'required_classes' in result: result['required_classes']=sorted(set(result['required_classes']))
        return result

    def identity(self,name):
        """Bind an implementation to its complete recorded resolution, including cycle members."""
        if name not in self.keys:
            pending,seen=[name],{}
            while pending:
                current=pending.pop()
                if current in seen: continue
                item=self.description(current);seen[current]=item
                pending.extend(sorted(set(item.get('required_classes',[]))))
            self.keys[name]='component-java-'+digest(dict(root=name,resolution=sorted(seen.values(),key=lambda item:item['fqcn'])))
        return self.keys[name]

    def attach(self,name,unit,operation,role):
        """Attach prerequisites iteratively; source text remains in existing unit evidence."""
        sources={source['identity']:source for source in unit['sources']}
        pending,visited=[(name,role)],set()
        while pending:
            current,current_role=pending.pop()
            key=self.identity(current)
            item=self.description(current)
            node=self.components.get(key)
            if node is None:
                status=item['status']
                source=status=='verified_source'
                from tools.framework_boundaries.inventory import owner
                framework = owner(current) if not source else None
                external=bool(framework) or status in {'verified_platform','verified_retention','explicit_replacement','explicit_external','evidence_dependency'}
                node=PlannedConversionComponent(component_id=key,kind='java_implementation' if source else
                    'external_dependency' if external else 'unresolved_dependency',label=current,
                    status='source_recorded' if source else 'external_recorded' if external else 'unresolved',provenance=item)
                if source and 'required_classes' not in item: node.issues.append('Recorded Java dependency graph is missing')
                if not source and not external: node.issues.append('Qualified Java origin is missing, competing or unresolved')
                if framework:
                    node.provenance = dict(item, framework_boundary=dict(class_name=current, **framework))
                self.components[key]=node
            if current_role and current_role not in node.roles: node.roles.append(current_role)
            if unit['unit_id'] not in node.unit_ids: node.unit_ids.append(unit['unit_id'])
            if operation not in node.operations: node.operations.append(operation)
            if item['status']=='verified_source':
                source=sources.get(item.get('definition_id'))
                if source is None or source['content_hash']!=item.get('source_hash'):
                    message='Unit '+unit['unit_id']+' lacks matching original implementation evidence'
                    if message not in node.issues: node.issues.append(message)
                else: node.source_characters=len(source['content'])
            if key in visited: continue
            visited.add(key)
            if node.provenance.get('framework_boundary'):
                continue  # The framework is an original-runtime boundary, not another source conversion closure.
            for dependency in sorted(set(item.get('required_classes',[]))):
                target=self.identity(dependency)
                if target not in node.dependencies: node.dependencies.append(target)
                node.dependency_reasons[target]=['recorded required_classes; conservative syntax dependency, not a proven runtime call']
                pending.append((dependency,''))
        return self.identity(name)
