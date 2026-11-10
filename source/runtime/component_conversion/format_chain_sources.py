"""Read decorator hooks from supplied Java evidence without executing original code."""
import re
from tools.validation_tools.java_comments import mask_java_non_code


def source_types(sources):
    """Index source-owned classes and their exact method bodies; ambiguous evidence fails closed."""
    result={}
    for source in sources:
        text=source['content'];code=mask_java_non_code(text)
        package=re.search(r'\bpackage\s+([\w.]+)\s*;',code)
        classes=list(re.finditer(r'\bclass\s+(\w+)(?:\s+extends\s+([\w.]+))?',code))
        if len(classes)!=1:continue
        declaration=classes[0];name=(package[1]+'.' if package else '')+declaration[1]
        methods={};overloads={}
        pattern=r'\b(?:public|protected|private)\s+(?:(?:static|final|synchronized|abstract)\s+)*[\w<>?,.\[\] ]+?\s+(\w+)\s*\([^{};]*\)\s*(?:throws\s+[\w., ]+)?\s*\{'
        for match in re.finditer(pattern,code):
            start=match.end();depth=1;end=start
            while end<len(code) and depth:
                depth+=(code[end]=='{')-(code[end]=='}');end+=1
            if depth:raise ValueError('Unclosed original method evidence: '+name)
            method=dict(code=code[start:end-1],excerpt=text[match.start():end],declaration=text[match.start():match.end()-1].strip(),source_identity=source['identity'],source_hash=source['content_hash'])
            overloads.setdefault(match[1],[]).append(method)
            methods[match[1]]=None if match[1] in methods else method
        result[name]=dict(parent=declaration[2],methods=methods,overloads=overloads,source=text)
    return result


def resolve_method(types,owner,name,signature=None):
    """Resolve a hook through supplied inheritance only, rejecting an ambiguous parent."""
    seen=set()
    while owner in types and owner not in seen:
        seen.add(owner);entry=types[owner]
        if name in entry['methods']:
            if signature:
                from runtime.behavior_conversion.method_contracts import _signature,java_type_resolver
                resolve=java_type_resolver(entry['source'],list(types))
                expected=_signature(signature,resolve)
                selected=[method for method in entry['overloads'].get(name,[]) if expected and _signature(method['declaration'],resolve)==expected]
                if len(selected)!=1:raise ValueError('Native chain signature is absent or ambiguous: '+signature)
                return selected[0]
            if entry['methods'][name] is None:raise ValueError('Ambiguous overloaded format hook: '+owner+'.'+name)
            return entry['methods'][name]
        parent=entry['parent']
        matches=[key for key in types if key==parent or key.rsplit('.',1)[-1]==parent]
        if len(matches)>1:raise ValueError('Ambiguous format parent evidence: '+str(parent))
        owner=matches[0] if matches else None
    return None


def reachable_hooks(types,owner,direction):
    """Follow same-object source calls; child formatter calls remain in their own scope."""
    found={};pending=[direction]
    while pending:
        name=pending.pop()
        if name in found:continue
        method=resolve_method(types,owner,name)
        if method is None:continue
        found[name]=method
        pending.extend(re.findall(r'(?<![\w$.])(?:this\.|super\.)?(\w+)\s*\(',method['code']))
    return found


def decorator_scope(types,owner):
    """Distinguish attribute production from value transformation using original APIs."""
    if resolve_method(types,owner,'formatXmlAttributes'):return 'xml_attributes'
    if resolve_method(types,owner,'addDecoration') and resolve_method(types,owner,'removeDecoration'):return 'value'
    raise ValueError('Decorator scope lacks complete original API evidence: '+owner)


def resolved_lifecycle_hooks(types, boundary, direction):
    """Read hook bodies from verified lifecycle graph provenance, including delegated owners."""
    found = {}
    lifecycle = boundary.get('format_lifecycle') or {}
    names = {call['method'] for call in lifecycle.get('invocations', [])}
    names.update({'applyDecorators', 'removeDecorators', 'formatXmlAttributes'})
    for node in (boundary.get('reachable_slice') or {}).get('nodes', []):
        if node['kind'] != 'method':
            continue
        name = node['signature'].split('(', 1)[0].rsplit('.', 1)[-1]
        if name not in names:
            continue
        candidates = types.get(node['declaring_class'], {}).get('overloads', {}).get(name, [])
        candidates = [method for method in candidates if method['source_identity'] == node['source_identity']
                      and method['source_hash'] == node['source_hash'] and method['excerpt'].strip() == node['excerpt'].strip()]
        if len(candidates) != 1:
            raise ValueError('Format hook body is absent or ambiguous in resolved lifecycle: ' + node['signature'])
        if name in found and found[name] != candidates[0]:
            raise ValueError('Multiple delegated format hook bodies require explicit resolution: ' + name)
        found[name] = candidates[0]
    invocations = lifecycle.get('invocations', [])
    if invocations and invocations[-1]['method'] in found:
        found[direction] = found[invocations[-1]['method']]
    return found
