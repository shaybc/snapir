"""Build passive component plans beneath unchanged scoped units and effective format trees."""
from models.component_conversion_plan import ComponentConversionPlan
from models.planned_conversion_component import PlannedConversionComponent
from tools.conversion_tools.component_java_graph import ComponentJavaGraph
from tools.conversion_tools.component_order import order_component_groups
from tools.conversion_tools.component_source_evidence import attach_supporting_sources
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def build_component_plan(operations, *, step_mappings=None):
    """Use existing qualified evidence only; no source search, AI call or native acceptance."""
    plan=ComponentConversionPlan()
    for operation,prepared in sorted(operations.items()):
        if prepared['status']!='prepared':
            plan.issues.append(dict(operation=operation,reason='Operation preparation is blocked; components are not scheduled'))
            continue
        java=ComponentJavaGraph(prepared['behavior_request']['java_origins'],plan.components,
                                prepared['behavior_request'].get('external_dependencies',[]))
        for unit in sorted(prepared['units'],key=lambda item:item['unit_id']):
            if unit['unit_id'] in plan.unit_roots: raise ValueError('Configured unit identity occurs more than once')
            builder=_ConfiguredGraph(plan,java,unit,operation,(step_mappings or {}).get(operation))
            builder.build()
    attach_supporting_sources(plan.components)
    for key,node in sorted(plan.components.items()):
        node.roles=sorted(node.roles or (['utility'] if node.kind=='java_implementation' else []))
        node.unit_ids.sort();node.operations.sort();node.issues.sort()
        # Java source dependency order is not an execution order. Configured child/decorator order stays intact.
        if node.kind in {'java_implementation','external_dependency','unresolved_dependency'}: node.dependencies.sort()
        for issue in node.issues: plan.issues.append(dict(component_id=key,reason=issue))
    plan.components=dict(sorted(plan.components.items()))
    plan.unit_roots=dict(sorted(plan.unit_roots.items()))
    plan.groups=order_component_groups(plan.components)
    plan.issues=sorted(plan.issues,key=digest)
    plan.status='incomplete' if plan.issues else 'planned'
    plan.fingerprint=digest(plan.model_dump(mode='json',exclude={'fingerprint'}))
    return plan


class _ConfiguredGraph:
    """Retain occurrence configuration and ordered format/decorator prerequisites for one unit."""
    def __init__(self,plan,java,unit,operation,step_mapping):
        self.plan,self.java,self.unit,self.operation=plan,java,unit,operation
        self.step_mapping=step_mapping
        self.definitions={item['definition_id']:item for item in unit.get('referenced_definitions',[])}
        self.definitions.setdefault(unit['source_definition_id'],unit['effective_configuration'])
        self.seen={}
        self.visiting=set()

    def node(self,kind,label,configuration,selector):
        identity='component-configured-'+digest(dict(unit_id=self.unit['unit_id'],unit_fingerprint=self.unit['fingerprint'],
            kind=kind,selector=selector,configuration=configuration))
        node=PlannedConversionComponent(component_id=identity,kind=kind,label=label,status='source_recorded',
            unit_ids=[self.unit['unit_id']],operations=[self.operation],configuration=configuration,
            provenance=dict(operation_identity=self.unit['operation_identity'],source_definition_id=self.unit['source_definition_id'],
                unit_fingerprint=self.unit['fingerprint'],selector=selector))
        self.plan.components[identity]=node
        return node

    def edge(self,node,target,reason):
        if target not in node.dependencies: node.dependencies.append(target)
        if reason not in node.dependency_reasons.setdefault(target,[]): node.dependency_reasons[target].append(reason)

    def implementation(self,node,name,role):
        if name:
            self.edge(node,self.java.attach(name,self.unit,self.operation,role),role)
        else: node.issues.append('Configured implementation binding is absent')

    def build(self):
        step=self.unit['kind']=='configured_step'
        configuration=self.unit['effective_configuration']
        root=self.node('configured_step' if step else 'format_composition',self.unit['logical_id'],
            configuration if step else dict(direction=self.unit['kind'],configuration_xml=self.unit['configuration_xml']), 'unit')
        self.plan.unit_roots[self.unit['unit_id']]=root.component_id
        if step:
            implementation=configuration.get('attributes',{}).get('implClass') or self.step_mapping
            root.provenance['resolved_implementation']=implementation
            self.implementation(root,implementation,'step_implementation')
            for index,call in enumerate(self.unit.get('operation_calls',[])):
                contract={key:value for key,value in call.items() if key not in {'status'}}
                target=self.node('operation_contract',call.get('callee','called operation'),contract,'call:'+str(index))
                target.status='external_recorded'
                self.edge(root,target.component_id,'resolved called-operation contract; not sibling step code')
        else:
            self.edge(root,self.format_node(configuration,'root'),'complete configured format')

    def format_node(self,node,path):
        # Referenced definitions are memoized before walking to preserve cycles, not recursively expand them.
        marker=node.get('occurrence_id') or node.get('source_selector') or path
        if marker in self.seen:
            if marker in self.visiting:
                self.plan.components[self.seen[marker]].issues.append('Cyclic configured format reference requires the existing closure resolution')
            return self.seen[marker]
        configuration={key:value for key,value in node.items() if key!='children'}
        result=self.node('format_node',node.get('tag','format'),configuration,path)
        self.seen[marker]=result.component_id
        self.visiting.add(marker)
        if node.get('java_class'):
            self.implementation(result,node['java_class'],'format_wrapper' if node.get('children') or node.get('reference_definition_id') else 'format_leaf')
        elif node.get('tag') not in {'fmtDef','refFmt'} and not node.get('reference_definition_id'):
            result.issues.append('Format tag has no resolved implementing class')
        for index,decorator in enumerate(node.get('decorators',[])):
            self.implementation(result,decorator.get('java_class'),'decorator')
            if decorator.get('java_class'):
                target=self.java.identity(decorator['java_class'])
                result.dependency_reasons[target].append('decorator index '+str(index)+'; attributes and ordering retained in configuration')
        for index,child in enumerate(node.get('children',[])):
            self.edge(result,self.format_node(child,path+'/child:'+str(index)),'ordered child '+str(index))
        reference=node.get('reference_definition_id')
        if reference:
            target=self.definitions.get(reference)
            if target is None: result.issues.append('Referenced format definition is absent: '+reference)
            else: self.edge(result,self.format_node(target,'definition:'+reference),'resolved refFmt definition '+reference)
        self.visiting.remove(marker)
        return result.component_id
