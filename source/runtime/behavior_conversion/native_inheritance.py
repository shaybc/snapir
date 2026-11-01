"""Resolve effective public methods using only parser-recorded native source ancestry."""
import re
from copy import deepcopy
from runtime.behavior_conversion.method_contracts import _signature, java_type_resolver


def resolve_methods(types):
    """Keep declaration provenance, apply overrides and never inherit constructors."""
    complete, active = set(), set()
    def visit(name):
        if name in complete:
            return
        if name in active:
            raise ValueError('Cyclic native type inheritance: ' + name)
        active.add(name)
        item = types[name]
        own = item['methods']
        chosen = {(m['name'], tuple(p['type'] for p in m['parameters'])): m for m in own}
        for method in own:
            method.setdefault('declaring_type', name)
        for parent in item.get('parents', []):
            base = types.get(parent['type'])
            if base is None:
                continue  # Missing/external ancestry is not invented; compilation must resolve it.
            visit(parent['type'])
            variables = base.get('type_parameters', [])
            arguments = parent.get('arguments', [])
            if variables and len(arguments) != len(variables):
                continue  # Raw/unresolved generics cannot prove a substituted public API.
            replacements = dict(zip(variables, arguments))
            def substitute(value):
                return re.sub(r'\b[A-Za-z_$][\w$]*\b', lambda m: replacements.get(m.group(), m.group()), value)
            for original in base['methods']:
                if base['kind'] == 'ClassOrInterfaceDeclaration' and base.get('interface') == 'true' and original.get('static') == 'true':
                    continue
                method = deepcopy(original)
                method['returns'] = substitute(method['returns'])
                if 'generic_returns' in method:
                    method['generic_returns'] = substitute(method['generic_returns'])
                for parameter in method['parameters']:
                    parameter['type'] = substitute(parameter['type'])
                    if 'generic_type' in parameter:
                        parameter['generic_type'] = substitute(parameter['generic_type'])
                key = (method['name'], tuple(p['type'] for p in method['parameters']))
                if key in chosen:
                    continue
                method['inherited'] = True
                method['signature'] = 'public ' + ('static ' if method.get('static') == 'true' else '') + method.get('generic_returns', method['returns']) + ' ' + method['name'] + '(' + ', '.join(p.get('generic_type', p['type']) for p in method['parameters']) + ')'
                chosen[key] = method
        item['methods'] = list(chosen.values())
        active.remove(name)
        complete.add(name)
    for name in types:
        visit(name)


def has_resolved_method(inventory, owner, signature, source):
    """Match exact resolved parameter/return/static types on a public native owner."""
    item = inventory['types'].get(owner)
    if item is None:
        return False
    resolve = java_type_resolver(source, inventory['types'])
    expected = _signature(signature, resolve)
    return expected is not None and any(_signature(m.get('signature', ''), resolve) == expected for m in item['methods'])
