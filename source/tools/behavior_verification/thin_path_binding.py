"""Conservative XML-path/native-getter matching; unknown presence is never silently inferred."""
import os
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from runtime.java_toolchain import run_java
from models.native_boundary_projection import NativeBoundaryProjection


def normalized(name):
    """Case-fold names and remove separators; do not use fuzzy matching."""
    return ''.join(character for character in name.casefold() if character.isalnum())


def configured_fields(unit):
    """Keep full XML dataName paths, including duplicate leaf names under different parents."""
    fields=[]
    definitions={item['definition_id']:item for item in unit.get('referenced_definitions',[])}
    def visit(node, path, active):
        name=node.get('attributes',{}).get('dataName')
        path=path+([name] if name else [])
        if node.get('reference_definition_id'):
            key=node['reference_definition_id']
            if key in active or key not in definitions:raise ValueError('Unavailable/cyclic format field path')
            visit(definitions[key],path,active|{key});return
        children=node.get('children',[])
        if name and not children:fields.append(dict(path=path,context_key=name))
        for child in children:visit(child,path,active)
    visit(unit['effective_configuration'],[],set())
    return fields


def inspect_getters(compiled, binding):
    """Use real compiled signatures; inspect metadata only, never execute getters here."""
    tool=Path(__file__).with_name('ThinPathGetterInventory.java')
    result=run_java(['java','-cp',os.pathsep.join(compiled['classpath']),str(tool),binding.owner_type,binding.method_name,
        *[argument.type_name for argument in binding.arguments]],capture_output=True,text=True,timeout=60,check=False)
    if result.returncode:raise ValueError('Native getter inspection failed: '+result.stderr[-2000:])
    root=ET.fromstring(result.stdout)
    return dict(result_type=root.get('result_type'),types={node.get('name'):[dict(item.attrib) for item in node]
        for node in root.findall('type')})


def _property(getter):
    name=getter['name']
    if name.startswith('get') and len(name)>3:return name[3:]
    if name.startswith('is') and getter['type'] in {'boolean','java.lang.Boolean'}:return name[2:]
    return name


def compatible(native_type, expected):
    """Require exact observable scalar kinds; never coerce text/numbers or unknown object shapes."""
    aliases={'java.lang.String':'string','boolean':'boolean','java.lang.Boolean':'boolean',
        'byte':'integer','short':'integer','int':'integer','long':'integer','java.lang.Byte':'integer',
        'java.lang.Short':'integer','java.lang.Integer':'integer','java.lang.Long':'integer',
        'double':'number','float':'number','java.lang.Double':'number','java.lang.Float':'number',
        'java.math.BigDecimal':'decimal'}
    return bool(expected) and aliases.get(native_type) in expected and expected=={aliases.get(native_type)}


def auto_bind(unit, binding, inventory, expected_types):
    """Build projections only for unique, typed getter chains; preserve limitations explicitly."""
    selected=binding.model_copy(deep=True);selected.output='none';selected.output_getters=[];selected.context_writes=[]
    fields=configured_fields(unit); counts=Counter(normalized(field['context_key']) for field in fields)
    results=[];limitations=[]
    for field in fields:
        path=field['path'];key=field['context_key'];candidates=[]
        # A DTO may represent the named XML root, so both full and root-relative paths are explicit alternatives.
        paths=[path,path[1:]] if len(path)>1 else [path]
        if counts[normalized(key)]==1:paths.append([key])
        for parts in paths:
            if not parts:continue
            owner=inventory['result_type'];chain=[];present=[];failure=False
            for index,part in enumerate(parts):
                getters=inventory['types'].get(owner,[])
                matches=[getter for getter in getters if normalized(_property(getter))==normalized(part)]
                if len(matches)!=1:failure=True;break
                getter=matches[0]
                if index==len(parts)-1:
                    flags=[item['name'] for item in getters if item['type'] in {'boolean','java.lang.Boolean'} and
                        normalized(item['name']) in {'has'+normalized(part),'was'+normalized(part)+'set',
                            'is'+normalized(part)+'set','is'+normalized(part)+'present'}]
                    if len(flags)==1:present=chain+[flags[0]]
                chain.append(getter['name']);owner=getter['type']
            if not failure and (chain,owner,present) not in candidates:candidates.append((chain,owner,present))
        item=dict(**field)
        if len(candidates)!=1:item.update(status='ambiguous_or_missing_getter',candidates=[candidate[0] for candidate in candidates])
        elif not compatible(candidates[0][1],expected_types.get(key,set())):
            item.update(status='incompatible_or_unknown_type',native_type=candidates[0][1])
        elif counts[normalized(key)]>1:
            item.update(status='legacy_path_not_observable',getters=candidates[0][0])
        else:
            getters,kind,presence=candidates[0]
            item.update(status='bound',getters=getters,native_type=kind,presence_observable=bool(presence))
            selected.context_writes.append(NativeBoundaryProjection(context_key=key,source='result',getters=getters,presence_getters=presence))
            if not presence:limitations.append(dict(kind='presence_not_observable',path=path,context_key=key))
        if item['status']!='bound':limitations.append(dict(kind=item['status'],path=path,context_key=key))
        results.append(item)
    from models.native_verification_binding import NativeVerificationBinding
    return NativeVerificationBinding.model_validate(selected.model_dump()),results,limitations
