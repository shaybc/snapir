"""Void original request boundaries compare projected fields without serializing the DTO."""
from types import SimpleNamespace
import pytest
from models.native_verification_binding import NativeVerificationBinding
from runtime.behavior_conversion.verification_binding import project_context_only


def binding():
    return NativeVerificationBinding(owner_type='com.company.generated.RequestFormat',method_name='parse',
        output='result',context_writes=[dict(context_key='ClientId',source='result',
            getters=['getClientId'],presence_getters=['isClientIdWritten'])])


@pytest.mark.parametrize('getters',[[],['getClientId']])
def test_void_request_preserves_projections_and_removes_only_separate_return(getters):
    value=binding();value.output_getters=getters;before=value.model_dump(mode='json')
    boundary=SimpleNamespace(kind='request_unformat',legacy_method=SimpleNamespace(return_type='void'))
    result=project_context_only(value,boundary)
    assert result.output=='none' and result.output_getters==[]
    assert result.context_writes==value.context_writes
    assert result.model_dump(mode='json')=={**before,'output':'none','output_getters':[]}
    assert value.model_dump(mode='json')==before
    assert project_context_only(result,boundary)==result


@pytest.mark.parametrize('kind,returns,projections',[
    ('response_format','java.lang.String',True),('configured_step','int',True),
    ('response_format','void',True),('configured_step','void',True),
    ('request_unformat','java.lang.String',True),('request_unformat','void',False),
    ('request_unformat',None,True),
])
def test_other_returns_or_missing_evidence_are_not_suppressed(kind,returns,projections):
    value=binding()
    if not projections:value.context_writes=[]
    boundary=SimpleNamespace(kind=kind,legacy_method=SimpleNamespace(return_type=returns) if returns else None)
    assert project_context_only(value,boundary) is value
