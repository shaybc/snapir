"""Construct unambiguous boundary recipes from parsed APIs and original configured names."""
from models.native_verification_binding import NativeVerificationBinding
from runtime.behavior_conversion.verification_binding import SCALARS
from tools.behavior_verification.thin_path_binding import configured_fields, normalized


class BindingAmbiguous(ValueError):
    """A small mapping-only task is needed; no source behavior or type is guessed."""


def validate_parsed_binding(binding,metadata,controls=()):
    """Verify all constructor, setter, getter and settings selections against parsed declarations."""
    types=metadata['types']
    def method(owner,name,parameters,static=None):
        matches=[m for m in types.get(owner,{}).get('methods',[]) if m['name']==name and
            [p['type'] for p in m['parameters']]==parameters and (static is None or (m.get('static')=='true')==static)]
        if len(matches)!=1:raise ValueError('Binding must select exactly one parsed method: '+owner+'.'+name)
        return matches[0]
    def construct(value):
        if value.source=='context':
            if value.type_name not in SCALARS or value.key not in {key['name'] for key in metadata.get('context_keys',[])}:
                raise ValueError('Context recipes require a known original scalar key; construct native DTOs explicitly')
        if value.source!='object':return
        if value.type_name not in types:raise ValueError('Object recipes require a parsed native DTO')
        parameters=[p.type_name for p in value.arguments]
        if value.factory_method:
            factory=method(value.type_name,value.factory_method,parameters,True)
            if factory['returns']!=value.type_name:raise ValueError('Factory must return its declared native DTO type')
        else:
            constructors=[m for m in types[value.type_name]['constructors'] if [p['type'] for p in m['parameters']]==parameters]
            if len(constructors)!=1:raise ValueError('Binding constructor is missing/ambiguous: '+value.type_name)
        for child in value.arguments:construct(child)
        for name,child in value.properties.items():
            method(value.type_name,name,[child.type_name],False);construct(child)
    method(binding.owner_type,binding.method_name,[p.type_name for p in binding.arguments],binding.static_method)
    if not binding.static_method:
        construct(type('Recipe',(),dict(source='object',type_name=binding.owner_type,
            arguments=binding.constructor_arguments,properties={},factory_method=None))())
    for value in binding.arguments:construct(value)
    expected={item['target'] for item in controls}
    if set(binding.settings_bindings)!=expected:raise ValueError('Settings binding keys must match runtime control IDs: '+str(sorted(expected)))
    for control in controls:
        target=binding.settings_bindings[control['target']]
        if set(target)!={'class','method'}:raise ValueError('Each settings binding must contain exactly class and method')
        originals=[m for m in metadata.get('original_methods',[]) if m['target']==control['target']]
        if len(originals)!=1:raise ValueError('Original setting signature is missing/ambiguous: '+control['target'])
        parameters=originals[0]['parameters']
        method(target['class'],target['method'],parameters,True)
    entry=method(binding.owner_type,binding.method_name,[p.type_name for p in binding.arguments],binding.static_method)
    def getters(owner,names):
        for name in names:owner=method(owner,name,[],False)['returns']
        return owner
    for projection in binding.context_writes:
        owner=entry['returns'] if projection.source=='result' else binding.arguments[projection.argument_index].type_name
        getters(owner,projection.getters)
        if projection.presence_getters and getters(owner,projection.presence_getters) not in {'boolean','java.lang.Boolean'}:
            raise ValueError('Presence accessor must return boolean')
    getters(entry['returns'],binding.output_getters)
    return binding


def build_binding(unit,metadata,controls=()):
    """Match exact normalized names/types only; unsupported observations remain explicit."""
    kinds={'request_unformat':('unformat','parse'), 'response_format':('format','serialize'),
           'configured_step':('execute',)}
    types=metadata['types']; names=kinds[unit['kind']]
    candidates=[(owner,m) for owner,t in types.items() for m in t['methods'] if m['name'] in names and
                owner in metadata.get('owned_types',types)]
    if len(candidates)!=1:raise BindingAmbiguous('Entry method is missing or ambiguous; choose from parsed methods')
    owner,entry=candidates[0]
    keys={field['context_key'] for field in configured_fields(unit)} | {item['name'] for item in metadata.get('context_keys',[])}
    def value(type_name,name,path=(),active=frozenset()):
        if unit['kind']=='request_unformat' and type_name=='java.lang.String' and not path:
            return dict(type_name=type_name,source='xml')
        if type_name in SCALARS:
            matches=[key for key in keys if normalized(key) in {normalized(name),normalized('.'.join((*path,name)))}]
            if len(matches)!=1:raise BindingAmbiguous('No unique original key for '+'.'.join((*path,name)))
            return dict(type_name=type_name,source='context',key=matches[0])
        if type_name not in types or type_name in active:raise BindingAmbiguous('Unsupported/cyclic native input: '+type_name)
        constructors=types[type_name]['constructors']
        if len(constructors)!=1:raise BindingAmbiguous('Constructor selection is ambiguous: '+type_name)
        constructor=constructors[0]
        arguments=[value(p['type'],p['name'],path,active|{type_name}) for p in constructor['parameters']]
        properties={}
        if not arguments:
            for m in types[type_name]['methods']:
                if m['name'].startswith('set') and m.get('static')!='true' and len(m['parameters'])==1:
                    name=m['name'][3:];property_name=name[:1].lower()+name[1:]
                    if m['name'] in properties:raise BindingAmbiguous('Overloaded setter: '+m['name'])
                    properties[m['name']]=value(m['parameters'][0]['type'],property_name,path,active|{type_name})
            if not properties:raise BindingAmbiguous('No unambiguous writable fields: '+type_name)
        return dict(type_name=type_name,source='object',arguments=arguments,properties=properties)
    settings={}
    for control in controls:
        originals=[m for m in metadata.get('original_methods',[]) if m['target']==control['target']]
        if len(originals)!=1:raise BindingAmbiguous('Original settings signature missing/ambiguous')
        parameter_types=originals[0]['parameters'];method_name=control['target'].rsplit('.',1)[1]
        matches=[(name,m) for name,t in types.items() for m in t['methods'] if m.get('static')=='true' and
            m['name']==method_name and [p['type'] for p in m['parameters']]==parameter_types]
        if len(matches)!=1:raise BindingAmbiguous('Runtime-setting method missing/ambiguous: '+control['target'])
        name,m=matches[0];settings[control['target']]={'class':name,'method':m['name']}
    binding=NativeVerificationBinding(owner_type=owner,method_name=entry['name'],static_method=entry.get('static')=='true',
        arguments=[value(p['type'],p['name']) for p in entry['parameters']],
        output='none' if unit['kind']=='request_unformat' else 'result',settings_bindings=settings)
    if unit['kind']=='configured_step':
        raise BindingAmbiguous('Step writes and outcome require explicit mapping unless a trusted projection is supplied')
    return validate_parsed_binding(binding,metadata,controls)
