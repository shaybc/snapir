"""Operation metadata uses verified accepted contracts instead of AI-reconstructed identities."""
from copy import deepcopy
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.native_implementation import NativeImplementation
from models.staged_metadata import metadata_schema
from runtime.behavior_conversion.metadata_semantics import materialize

API=dict(type_name='nativecode.Operation',method_signatures=['public String execute(String value)'])
PRODUCTION=NativeImplementation(files=[dict(path='src/main/java/nativecode/Operation.java',
    content='package nativecode; public class Operation {public String execute(String value){return value;}}')])


def contract(identity):
    return dict(unit_id=identity,apis=[API],requirements={'business':'Preserve the selected unit'},evidence_ids=['source'])


def metadata(units):
    return metadata_schema(NativeUnitBundle,True).model_validate(dict(operation_contract=dict(
        service_api=API,request_type='java.lang.String',success_type='java.lang.String',error_type='java.lang.String',units=units)))


def test_operation_contract_reuses_all_unique_accepted_units_without_model_copying():
    first,second=contract('first'),contract('second')
    payload={'accepted_units':{'entry':{'contract':first},'alias':{'contract':deepcopy(first)},'reply':{'contract':second}}}
    data=materialize(metadata([]),payload,{'apis':[API]},PRODUCTION)
    assert data['operation_contract']['units']==[first,second]
    parsed=metadata_schema(NativeUnitBundle).model_validate(data)
    assert [u.unit_id for u in parsed.operation_contract.units]==['first','second']
    data['operation_contract']['units'][0]['requirements']['business']='changed'
    assert first['requirements']['business']=='Preserve the selected unit'


def test_model_cannot_replace_an_accepted_unit_contract():
    accepted=contract('accepted')
    data=materialize(metadata([contract('invented')]),{'accepted_units':{'step':{'contract':accepted}}},{'apis':[API]},PRODUCTION)
    assert data['operation_contract']['units']==[accepted]


def test_conflicting_aliases_of_an_accepted_unit_are_rejected():
    first=contract('same');changed=deepcopy(first);changed['requirements']['business']='different'
    with pytest.raises(ValueError,match='Conflicting accepted'):
        materialize(metadata([]),{'accepted_units':{'one':{'contract':first},'two':{'contract':changed}}},{'apis':[API]},PRODUCTION)


def test_metadata_without_accepted_checkpoint_keeps_its_existing_contract_path():
    original=contract('planned')
    data=materialize(metadata([original]),{},{'apis':[API]},PRODUCTION)
    assert data['operation_contract']['units'][0]['unit_id']=='planned'


def test_final_operation_contract_still_rejects_an_empty_unaccepted_unit_list():
    data=materialize(metadata([]),{},{'apis':[API]},PRODUCTION)
    with pytest.raises(ValueError,match='at least 1 item'):
        metadata_schema(NativeUnitBundle).model_validate(data)
