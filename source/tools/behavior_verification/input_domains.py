"""Bounded deterministic input samples; parser literals are inputs, never expected answers."""
import re
from decimal import Decimal,InvalidOperation
from tools.behavior_verification.controlled_inputs import _pattern_value


def scalar_domain(attributes,checklist,limit=32):
    """Keep empty, ordinary and source-boundary samples with explicit sampling limits."""
    kind=attributes.get('type','').rsplit(':',1)[-1]
    pattern=attributes.get('pattern')
    baseline=_pattern_value(pattern) if pattern else ('true' if kind=='boolean' else '123')
    bounds={name:_number(attributes.get(name,'')) for name in ('minInclusive','maxInclusive')}
    if not pattern and kind!='boolean':
        value=Decimal(123)
        if bounds['minInclusive'] is not None:value=max(value,bounds['minInclusive'])
        if bounds['maxInclusive'] is not None:value=min(value,bounds['maxInclusive'])
        if bounds['minInclusive'] is not None and bounds['maxInclusive'] is not None and bounds['minInclusive']>bounds['maxInclusive']:
            raise ValueError('Inconsistent configured numeric bounds')
        baseline=format(value,'f')
    values=[baseline,'','true','false',' ','0','1','-1','0005',' 123 ','a&<b>','20240102','invalid']
    numbers=set()
    for name in ('minInclusive','maxInclusive'):
        number=bounds[name]
        if number is not None:numbers.update({number-1,number,number+1})
    for item in checklist.items if checklist is not None else ():
        value=item.properties.get('value','')
        if (item.kind=='literal' and getattr(item,'detail','')=='StringLiteralExpr' and len(value)<=128
            and all(char in '\t\n\r' or 32<=ord(char)<=0xd7ff or 0xe000<=ord(char)<=0xfffd or 0x10000<=ord(char)<=0x10ffff for char in value)):
            values.append(value)
        number=_number(value)
        if item.kind=='literal' and number is not None:
            values.append(value.replace('_','').rstrip('lLfFdD'))
            numbers.update({number-1,number,number+1,-number-1,-number,-number+1})
    values+=[format(number,'f') for number in sorted(numbers)]
    values=list(dict.fromkeys(values))
    return baseline,values[:limit],max(0,len(values)-limit)


def _number(value):
    """Recognize finite decimal Java/XML literals without allocating huge exponent expansions."""
    if len(value)>32:return None
    text=value.replace('_','').rstrip('lLfFdD')
    if not re.fullmatch(r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',text):return None
    try:number=Decimal(text)
    except InvalidOperation:return None
    return number if -18<=number.adjusted()<=18 else None


def domain_sampler(checklist,limit):
    """Scan shared parser literals once per distinct declared scalar shape."""
    cache={};names=('type','pattern','minInclusive','maxInclusive')
    def sample(attributes):
        key=tuple(attributes.get(name,'') for name in names)
        if key not in cache:cache[key]=scalar_domain(dict(zip(names,key)),checklist,limit)
        return cache[key]
    return sample
