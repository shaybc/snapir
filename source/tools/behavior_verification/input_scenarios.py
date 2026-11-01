"""Bounded context domains and unit-scoped controlled replay scenarios."""
import hashlib
import json
import random
import re
from copy import deepcopy
from models.boundary_case import BoundaryCase
from tools.behavior_verification.controlled_inputs import generate_boundary_cases
from tools.behavior_verification.input_domains import domain_sampler
from tools.behavior_verification.structured_inputs import generate_xml_cases,VERSION


def generate_input_scenarios(unit,boundary,settings):
    """Generate inputs only; both JVMs receive identical retained controls and fixtures."""
    if unit['kind']=='request_unformat':cases,report=generate_xml_cases(unit,boundary,settings)
    else:cases,report=_context_scenarios(unit,boundary,settings)
    if unit['kind']=='request_unformat' and cases and getattr(boundary,'configuration_preparation',{}):
        # Vary request data before execution; never alter the configured component tree.
        case=cases[0].model_copy(deep=True)
        case.input_xml='\n'+case.input_xml
        case.labels=[*case.labels,'configured-preparation:leading-xml-whitespace']
        case.case_id=_identity(case.model_dump(mode='json',exclude={'case_id'}))
        if not any(old.input_xml==case.input_xml for old in cases):cases.append(case)
        report['configuration_preparation_version']=boundary.configuration_preparation['version']
    for case in cases:case.external_responses=deepcopy(settings.replays.get(unit['unit_id'],[]))
    for fixture in settings.fixtures.get(unit['unit_id'],[]):
        data=fixture.model_dump(mode='json')
        data['labels']=[*data['labels'],'controlled_fixture:'+data['case_id']]
        data['case_id']=_identity(data)
        cases.append(BoundaryCase.model_validate(data))
    if len(cases)>settings.max_cases:raise ValueError('Combined generated/fixture case budget exceeded')
    if len({case.case_id for case in cases})!=len(cases):raise ValueError('Input scenarios have duplicate identities')
    if any(len(case.model_dump_json())>settings.max_case_chars for case in cases):raise ValueError('Controlled input/replay size budget exceeded')
    return cases,dict(report,generated_cases=len(cases)-len(settings.fixtures.get(unit['unit_id'],[])),
        fixture_cases=len(settings.fixtures.get(unit['unit_id'],[])),seed=settings.seed,clock_millis=settings.clock_millis)


def _context_scenarios(unit,boundary,settings):
    fields={};definitions={d['definition_id']:d for d in unit.get('referenced_definitions',[])}
    def visit(node,active=frozenset(),depth=0):
        if depth>64:raise ValueError('Context input nesting budget exceeded')
        reference=node.get('reference_definition_id')
        if reference:
            if reference in active or reference not in definitions:raise ValueError('Unavailable/cyclic context format reference')
            visit(definitions[reference],active|{reference},depth+1);return
        if node.get('collection_kind')=='indexed':raise ValueError('Indexed context structure needs an explicit supported observer')
        children=node.get('children',[]);name=node.get('attributes',{}).get('dataName')
        if name and not children:
            if name in fields:raise ValueError('Repeated context dataName paths cannot be inferred as one flat key')
            fields[name]=node['attributes']
        for child in children:visit(child,active,depth+1)
    visit(unit['effective_configuration'])
    flat={**unit,'effective_configuration':dict(children=[dict(attributes=attributes) for attributes in fields.values()])}
    baseline=generate_boundary_cases(flat,boundary,seed=settings.seed,random_cases=0,baseline_only=True)[0].initial_context
    domains={};omitted=0
    sample=domain_sampler(boundary.parser_checklist,settings.max_domain_values)
    for key in baseline:
        field_baseline,values,truncated=sample(fields.get(key,{}))
        attributes=fields.get(key,{})
        if not attributes.get('pattern'):baseline[key]=field_baseline
        if attributes.get('pattern'):
            millis=baseline[key]['$date_millis']
            points=[millis,millis-1,millis+1,*[int(v) for v in values if re.fullmatch(r'-?\d{1,19}',v)]]
            values=[{'$date_millis':v} for v in dict.fromkeys(points) if -(2**63)<=v<2**63]
        elif attributes.get('type','').rsplit(':',1)[-1]=='boolean':
            baseline[key]=True;values=[True,False]
        domains[key]=values;omitted+=truncated
    def rows():
        yield 'baseline',baseline
        for key,values in domains.items():
            for value in [None,*values]:yield key,{**baseline,key:value}
            yield key+':missing',{name:value for name,value in baseline.items() if name!=key}
        rng=random.Random(settings.seed)
        for _ in range(settings.random_cases):yield 'seeded_combination',{key:rng.choice([None,*values]) for key,values in domains.items()}
    seen=set();cases=[]
    for label,row in rows():
        encoded=json.dumps(row,sort_keys=True)
        if len(encoded)>settings.max_case_chars:raise ValueError('Context input size budget exceeded')
        if encoded in seen:continue
        seen.add(encoded)
        data=dict(initial_context=deepcopy(row),random_seed=settings.seed,clock_millis=settings.clock_millis,labels=[label,VERSION])
        cases.append(BoundaryCase(case_id=_identity(data),**data))
        if len(cases)>settings.max_cases:raise ValueError('Context input case budget exceeded')
    return cases,dict(version=VERSION,sampled_paths=len(baseline),collection_paths=0,domain_values_omitted=omitted)


def _identity(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
