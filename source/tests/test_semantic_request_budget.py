"""Keep executable semantic requests under the run budget, independently of checklist limits."""
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_component_bundle import NativeComponentBundle
from runtime.behavior_conversion import metadata_semantics
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete


class RequestReached(Exception):
    """Observe a budget-checked request without issuing an AI call."""


@pytest.mark.parametrize('mode,size,allowed', [
    ('executable_boundary_v1',100000,True),
    ('executable_boundary_v1',130000,False),
    ('checklist_v1',100000,False),
])
def test_semantic_budget_respects_selected_verification_mode(monkeypatch,mode,size,allowed):
    profile=PipelineConfiguration(behavior_context_chars=120000)
    profile.executable_verification.mode=mode
    monkeypatch.setattr(metadata_semantics,'semantic_request',lambda *args: {'evidence':'x'*size})
    def ask(*args,**kwargs):
        assert kwargs['request_limit']==120000
        raise RequestReached()
    tasks=SimpleNamespace(profile=profile,ask=ask)
    with pytest.raises(RequestReached if allowed else VerificationIncomplete):
        metadata_semantics.describe(tasks,{},None,None,NativeComponentBundle,lambda _:None)


def test_conversion_chain_metadata_is_explicit_and_receives_accepted_apis(monkeypatch):
    from models.native_format_component_bundle import NativeFormatComponentBundle
    profile=PipelineConfiguration()
    profile.executable_verification.mode='conversion_checklist_v1'
    payload=dict(format_chain_policy='configured-format-chains-v1',format_chains=[dict(
        occurrence_id='occurrence',class_name='Chain',direction='format',attributes={},operations=[],inactive_decorators=[])],
        prerequisite_components=[dict(contracts={'basic':dict(apis=[dict(type_name='accepted.Basic',method_signatures=['public String format(String value)'])])})])
    request=metadata_semantics.semantic_request(payload,SimpleNamespace(files=[]),dict(apis=[]))
    assert 'prerequisite_apis' not in request
    assert 'format_chains' not in request
    monkeypatch.setattr(metadata_semantics,'semantic_request',lambda *args:request)
    def ask(stage,supplied,instruction,schema,check,**kwargs):
        assert 'format_chain_bindings' not in instruction
        assert 'format_chain_bindings' not in schema.model_fields
        raise RequestReached()
    with pytest.raises(RequestReached):
        metadata_semantics.describe(SimpleNamespace(profile=profile,ask=ask),payload,None,None,NativeFormatComponentBundle,lambda _:None)
