"""Suggest inputs for recognized uncovered conditions; execution alone establishes outcomes."""
import hashlib
import json
import re
from xml.dom import minidom,Node
from xml.parsers.expat import ExpatError
from tools.behavior_verification.input_domains import _number
from tools.behavior_verification.thin_path_binding import configured_fields

MISSING=object()


def input_identity(case):
    """Deduplicate actual controls, independently of labels and generated case IDs."""
    data=case.model_dump(mode='json',exclude={'case_id','labels'})
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def proposals(unit,boundary,branch,baseline,legacy_binding):
    """Handle direct context reads and System clocks; other predicates remain unsupported."""
    condition=branch.properties.get('condition') or ''
    normalize=lambda text:re.sub(r'"(?:\\.|[^"\\])*"|\s+',lambda match:match[0] if match[0].startswith('"') else '',text)
    group=[item for item in boundary.parser_checklist.items if item.code_node_id==branch.code_node_id]
    literals={item.excerpt:item.properties.get('value','') for item in group if item.kind=='literal' and item.detail=='StringLiteralExpr'}
    calls=[item for item in group if item.kind=='call' and normalize(item.excerpt) in normalize(condition)]
    reader=legacy_binding.context_class+'.'+legacy_binding.context_reader+'('
    keys={literals[item.arguments[0]] for item in calls if item.properties.get('target','').startswith(reader)
        and len(item.arguments)==1 and item.arguments[0] in literals}
    clock=any(item.properties.get('target')=='java.lang.System.currentTimeMillis()' for item in calls)
    if len(keys)!=1 and not (clock and not keys):return None,'condition_has_no_unique_supported_input'
    if clock and keys:return None,'mixed_clock_and_context_condition'
    key=next(iter(keys)) if keys else None
    values=[]
    for item in group:
        if item.kind!='literal' or normalize(item.excerpt) not in normalize(condition):continue
        value=item.properties.get('value','')
        if item.detail=='StringLiteralExpr' and value!=key:values.append(value)
        number=_number(value)
        if number is not None:
            # Neighbor proposals do not claim to solve a predicate. Probes verify each result.
            values.extend(format(n,'f') for n in (number+1,number,number-1,-number-1,-number,-number+1))
    values.extend([None,'',MISSING] if not clock else [])
    if key is not None:values.append(key)
    def candidates():
        for value in values:
            case=baseline.model_copy(deep=True)
            if clock:
                if not isinstance(value,str) or not re.fullmatch(r'-?\d+',value):continue
                timestamp=int(value)
                if not -(2**63)<=timestamp<2**63:continue
                case.clock_millis=timestamp
            elif unit['kind']=='request_unformat':
                xml=_xml_value(unit,case.input_xml,key,value)
                if xml is None:continue
                case.input_xml=xml
            elif value is MISSING:case.initial_context.pop(key,None)
            else:
                previous=case.initial_context.get(key)
                if isinstance(previous,bool) and value is not None:
                    if value not in ('true','false'):continue
                    value=value=='true'
                elif isinstance(previous,int) and value is not None:
                    if not isinstance(value,str) or not re.fullmatch(r'-?\d+',value):continue
                    value=int(value)
                elif isinstance(previous,dict):continue
                case.initial_context[key]=value
            case.labels=[*case.labels,'coverage-expansion',branch.id]
            case.case_id='expanded-'+input_identity(case)[:20]
            yield case
    return candidates(),None


def _xml_value(unit,xml,key,value):
    """Change a unique evidenced path without flattening or renaming XML prefixes."""
    fields=[field for field in configured_fields(unit) if field['context_key']==key]
    if len(fields)!=1 or not xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():return None
    try:document=minidom.parseString(xml)
    except (ExpatError,ValueError):return None
    try:
        path=fields[0]['path'];node=document.documentElement
        if not path or node.tagName!=path[0]:return None
        for name in path[1:]:
            children=[c for c in node.childNodes if c.nodeType==Node.ELEMENT_NODE and c.tagName==name]
            if len(children)!=1:return None
            node=children[0]
        if value is MISSING:
            if node is document.documentElement:return None
            node.parentNode.removeChild(node)
        else:
            while node.firstChild:node.removeChild(node.firstChild)
            namespace='http://www.w3.org/2001/XMLSchema-instance'
            if node.hasAttributeNS(namespace,'nil'):node.removeAttributeNS(namespace,'nil')
            if value is None:
                declarations={};ancestor=node
                while ancestor.nodeType==Node.ELEMENT_NODE:
                    for attribute in ancestor.attributes.values():
                        if attribute.name.startswith('xmlns:'):declarations.setdefault(attribute.name[6:],attribute.value)
                    ancestor=ancestor.parentNode
                prefix=next((name for name,uri in declarations.items() if uri==namespace),None)
                if prefix is None:
                    prefix='xsi';index=0
                    while prefix in declarations:index+=1;prefix='xsi'+str(index)
                    node.setAttribute('xmlns:'+prefix,namespace)
                node.setAttributeNS(namespace,prefix+':nil','true')
            else:node.appendChild(document.createTextNode(str(value)))
        return document.documentElement.toxml()
    finally:document.unlink()
