"""Reuse byte-equivalent saved JDBC query sets without changing business data or field casing."""
from copy import deepcopy
import re
from models.operation_demo_proposal import OperationDemoProposal,ScenarioFixtureSelection
from models.shared_test_fixture import SharedFixtureBank
from runtime.test_assets.references import resolve
from runtime.fixture_jdbc_tools.releases import digest

PUBLICATION_VERSION='exact-saved-query-reuse-v1'


def reuse_saved_resources(proposal,evidence):
    """Replace duplicate query data with explicit old-bank references and exact pointer rebinding.

    Only the fixture schema's /queries/index segment is rebound. SQL, parameters,
    values, field spelling, expectations and Java are never normalized or repaired.
    """
    data=deepcopy(proposal.model_dump(mode='json'));notes=[]
    candidates=[]
    for bank_id,item in sorted(evidence['saved_banks'].items()):
        bank=SharedFixtureBank.model_validate(item['fixtures'])
        for fixture_id,entry in sorted(bank.fixtures.items()):
            if entry.kind!='database':continue
            queries=resolve(bank,dict(fixture_id=fixture_id))['queries']
            if queries:candidates.append((bank_id,fixture_id,queries))
    if not data['new_fixtures']:return proposal,notes
    original_bank=SharedFixtureBank(fixtures=proposal.new_fixtures)
    def nested_reference(value,name):
        if isinstance(value,dict):return value.get('$fixture')==name or any(nested_reference(v,name) for v in value.values())
        return isinstance(value,list) and any(nested_reference(v,name) for v in value)
    for fixture_id,entry in list(data['new_fixtures'].items()):
        if entry['kind']!='database':continue
        if not isinstance(entry['value'],dict) or not isinstance(entry['value'].get('queries'),list):continue
        if any(nested_reference(other['value'],fixture_id) for key,other in data['new_fixtures'].items() if key!=fixture_id):continue
        direct=[]
        for scenario in data['scenarios']:
            direct.extend([scenario['input_xml'],scenario['expected_xml']])
            direct.extend(ref for link in scenario['links'] for ref in link.values())
        relevant=[ref for ref in direct if ref['bank']=='generated' and ref['fixture_id']==fixture_id]
        if any(not re.fullmatch(r'/queries/(0|[1-9][0-9]*)(/.*)?',ref['pointer']) for ref in relevant):continue
        queries=resolve(original_bank,dict(fixture_id=fixture_id))['queries']
        remaining=set(range(len(queries)));mapping={};selected=[]
        for bank_id,old_id,old_queries in sorted(candidates,key=lambda item:(-len(item[2]),item[0],item[1])):
            indices={digest(query):i for i,query in enumerate(old_queries)}
            available={digest(queries[i]):i for i in remaining}
            if not set(indices)<=set(available):continue
            for query_hash,old_index in indices.items():
                index=available[query_hash];remaining.remove(index)
                mapping[index]=dict(bank=bank_id,fixture_id=old_id,pointer='/queries/'+str(old_index))
            selected.append(dict(bank=bank_id,fixture_id=old_id,pointer=''))
        if not selected:continue
        for new_index,index in enumerate(sorted(remaining)):
            mapping[index]=dict(bank='generated',fixture_id=fixture_id,pointer='/queries/'+str(new_index))
        for ref in relevant:
            match=re.fullmatch(r'/queries/(0|[1-9][0-9]*)(/.*)?',ref['pointer'])
            target=mapping[int(match[1])]
            ref.update(target,pointer=target['pointer']+(match[2] or ''))
        for scenario in data['scenarios']:
            for resource,refs in scenario['resources'].items():
                updated=[]
                for ref in refs:
                    if ref['bank']=='generated' and ref['fixture_id']==fixture_id and not ref['pointer']:
                        if remaining:updated.append(ref)
                        updated.extend(deepcopy(selected))
                    else:updated.append(ref)
                scenario['resources'][resource]=updated
        if remaining:
            entry['value']['queries']=[entry['value']['queries'][i] for i in sorted(remaining)]
        else:data['new_fixtures'].pop(fixture_id)
        notes.append(dict(generated_fixture=fixture_id,reused_query_count=len(queries)-len(remaining),saved_resources=selected))
    result=OperationDemoProposal.model_validate(data)
    # The transformation must preserve every resolved query response for each resource.
    def query_sets(value):
        banks={key:SharedFixtureBank.model_validate(item['fixtures']) for key,item in evidence['saved_banks'].items()}
        if value.new_fixtures:banks['generated']=SharedFixtureBank(fixtures=value.new_fixtures)
        return {(s.scenario_id,key):sorted({digest(q) for ref in refs for q in resolve(banks[ref.bank],
            dict(fixture_id=ref.fixture_id,pointer=ref.pointer))['queries']})
            for s in value.scenarios for key,refs in s.resources.items()}
    if query_sets(result)!=query_sets(proposal):raise ValueError('Saved resource reuse changed a prepared query response')
    return result,notes
