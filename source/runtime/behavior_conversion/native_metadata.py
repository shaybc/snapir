"""Inspect native Java with JavaParser and resolve imports through pinned artifact inventories."""
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from runtime.java_toolchain import run_java
from runtime.behavior_conversion.method_contracts import java_type_resolver, _parameters
from models.operation_data_contract import NativeApiContract
from models.maven_dependency import MavenDependency
from tools.behavior_verification.java_tool import default_tool_path


def inspect_native(files, tool=None, original_sources=()):
    """Run the application-owned JavaParser inspector; never execute candidate code."""
    jar=Path(tool or default_tool_path()).resolve()
    with TemporaryDirectory(prefix='snapir-native-api-') as folder:
        root=ET.Element('sources')
        for file in files:
            ET.SubElement(root,'file',path=file.path).text=file.content
        for source in original_sources:
            ET.SubElement(root,'original',identity=source['identity']).text=source['content']
        source=Path(folder)/'input.xml'; output=Path(folder)/'output.xml'
        ET.ElementTree(root).write(source,encoding='utf-8',xml_declaration=True)
        result=run_java(['java','-cp',str(jar),'il.co.dcd.verification.NativeApiInspection',str(source),str(output)],
            capture_output=True,text=True,timeout=90,check=False)
        if result.returncode:
            raise ValueError('Native JavaParser inspection failed: '+result.stderr[-2000:])
        parsed=ET.parse(output).getroot()
    types={};imports=[];apis=[];calls=[]
    by_path={file.path:file.content for file in files}
    known=[node.get('name') for node in parsed.iter('type')]
    for file in parsed.findall('file'):
        resolve=java_type_resolver(by_path[file.get('path')],known)
        for call in file.findall('test-call'):
            calls.append(dict(call.attrib,receiver_type=resolve(call.get('receiver_type'))))
        for node in file.findall('import'):
            imports.append(dict(node.attrib))
        for node in file.iter('type'):
            variables=[p.get('name') for p in node.findall('type-parameter')]
            resolve=java_type_resolver(by_path[file.get('path')],known,type_variables=variables)
            generic_resolve=java_type_resolver(by_path[file.get('path')],known,type_variables=variables,
                                             preserve_type_arguments=True)
            item=dict(node.attrib,methods=[],constructors=[],fields=[])
            item['type_parameters']=variables
            item['parents']=[]
            for parent in node.findall('parent'):
                text=parent.get('type')
                arguments=_parameters(text[text.index('<')+1:text.rindex('>')]) if '<' in text else []
                item['parents'].append(dict(type=resolve(text),arguments=[resolve(arg) for arg in arguments]))
            for tag,target in [('method','methods'),('constructor','constructors')]:
                for member in node.findall(tag):
                    data=dict(member.attrib,parameters=[dict(p.attrib,type=resolve(p.get('type'))) for p in member.findall('parameter')])
                    if member.get('returns'):data['returns']=resolve(member.get('returns'))
                    if member.get('returns'):data['generic_returns']=generic_resolve(member.get('returns'))
                    for parameter, original in zip(data['parameters'], member.findall('parameter')):
                        parameter['generic_type']=generic_resolve(original.get('type'))
                    item[target].append(data)
            item['fields']=[dict(field.attrib,type=resolve(field.get('type'))) for field in node.findall('field')]
            types[item['name']]=item
    from runtime.behavior_conversion.native_inheritance import resolve_methods
    resolve_methods(types)
    types={name:item for name,item in types.items() if item.get('public','true')=='true'}
    for item in types.values():
        apis.append(NativeApiContract(type_name=item['name'],method_signatures=[
            member['signature'] for member in [*item['constructors'],*item['methods']] if member.get('signature')]))
    originals={source['identity']:source['content'] for source in original_sources}
    original_methods=[]
    for method in parsed.findall('original-method'):
        resolve=java_type_resolver(originals[method.get('source')])
        original_methods.append(dict(target=method.get('target'),parameters=[resolve(p.get('type')) for p in method.findall('parameter')]))
    return dict(types=types,imports=imports,calls=calls,apis=[api.model_dump(mode='json') for api in apis],original_methods=original_methods,
                context_keys=[dict(key.attrib) for key in parsed.findall('context-key')],
                evidence_ranges=[dict(span.attrib) for span in parsed.findall('evidence-range')])


def resolve_dependencies(metadata, known, proposed=()):
    """Resolve supported imports from verified inventory; never infer Maven coordinates from a package name."""
    inventory={}
    for value in [*known,*proposed]:
        item=MavenDependency.model_validate(value)
        key=(item.group_id,item.artifact_id)
        if key in inventory and (inventory[key].version,inventory[key].scope)!=(item.version,item.scope):
            raise ValueError('Dependency proposal changed a pinned dependency: '+':'.join(key))
        if item.group_id.startswith('com.ibm') or any(name.startswith('com.ibm.') for name in item.required_classes):
            raise ValueError('IBM dependencies are forbidden')
        inventory[key]=item
    selected={};unknown=[]
    for imp in metadata['imports']:
        name=imp['name']
        if name.startswith(('java.','javax.xml.','javax.crypto.','javax.net.','org.w3c.dom.','org.xml.sax.')):
            continue
        if name in metadata['types'] or any(name.startswith(owner+'.') for owner in metadata['types']):continue
        matches=[item for item in inventory.values() if any(name==cls or name.startswith(cls+'.') or (
            imp['wildcard']=='true' and cls.startswith(name+'.')) for cls in item.required_classes)]
        direct_owner=bool(matches)
        if not matches:
            # Select only an already pinned artifact, never invent coordinates from a package.
            # The managed compiler/verifier must still prove that it supplies the imported class.
            matches=[item for item in inventory.values() if name.startswith(item.group_id+'.')]
        if len(matches)!=1:
            from runtime.dependency_policy import import_owner
            actual=import_owner(imp,matches or list(inventory.values()))
            if actual is not None:matches=[actual];direct_owner=True
        if len(matches)!=1:
            unknown.append(name)
        else:
            item=matches[0].model_copy(deep=True)
            imported_class=name.rsplit('.',1)[0] if imp['static']=='true' and imp['wildcard']!='true' else name
            if direct_owner and (imp['wildcard']!='true' or imp['static']=='true'):
                item.required_classes=sorted(set([*item.required_classes,imported_class]))
            previous=selected.get((item.group_id,item.artifact_id))
            if previous:item.required_classes=sorted(set([*previous.required_classes,*item.required_classes]))
            selected[(item.group_id,item.artifact_id)]=item
    return list(selected.values()),sorted(set(unknown))
