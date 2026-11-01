"""Generated unsupported binding types are correctable failures, never permission to invoke them."""
import json
from types import SimpleNamespace
import pytest
from models.native_boundary_value import NativeBoundaryValue
from models.unit_mutation_settings import UnitMutationSettings
from runtime.behavior_conversion.revisions import generate_reviewed_bundle
from runtime.behavior_conversion.verification_ladder import active_verification
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from tools.state_store_tools.behavior_units import snapshot
from test_behavior_verification_boundaries import boundary_tool
from test_verification_pipeline import payload,response,state


def unsupported(data,type_name='java.util.Map'):
    bundle=response(data)
    bundle.files[0].content='package nativefixture; public class Work { public int run('+type_name+' value){return 7;} }'
    bundle.unit_contract.apis[0].method_signatures=['public int run('+type_name+' value)']
    bundle.verification_binding.arguments=[NativeBoundaryValue(type_name=type_name,source='context',key='input')]
    return bundle


@pytest.mark.parametrize('type_name',['java.util.Map','java.sql.Connection','java.io.File'])
def test_generated_unsupported_types_are_retryable_but_still_rejected(type_name):
    data={'unit_id':'unit-configured_step','evidence_ids':['unit-configured_step'],
          'boundary':{'source_manifest_hash':'source','configuration_hash':'configuration'},'checklist':{'items':[]}}
    with pytest.raises(VerificationFailure) as caught: validate_binding(unsupported(data,type_name))
    assert not isinstance(caught.value,VerificationIncomplete)
    feedback=caught.value.verification_feedback
    assert feedback['stage']=='binding' and type_name in feedback['errors'][0]
    assert type_name not in feedback['allowed_types'] and 'java.lang.String' in feedback['allowed_types']


def test_generated_recursive_recipe_is_retryable():
    data={'unit_id':'unit-configured_step','evidence_ids':['unit-configured_step'],
          'boundary':{'source_manifest_hash':'source','configuration_hash':'configuration'},'checklist':{'items':[]}}
    bundle=unsupported(data,'nativefixture.Work')
    recipe=NativeBoundaryValue(type_name='nativefixture.Work',source='object')
    for _ in range(14): recipe=NativeBoundaryValue(type_name='nativefixture.Work',source='object',arguments=[recipe])
    bundle.verification_binding.arguments=[recipe]
    with pytest.raises(VerificationFailure) as caught: validate_binding(bundle)
    assert not isinstance(caught.value,VerificationIncomplete)
    assert 'nesting depth' in str(caught.value)


@pytest.mark.parametrize('corrected',[True,False])
def test_generation_retries_binding_feedback_and_keeps_the_configured_attempt_limit(boundary_tool,tmp_path,corrected):
    conn,config,profile=state(tmp_path)
    profile.unit_mutation_testing=UnitMutationSettings(enabled=False)
    requests=[]
    def model(_,encoded):
        data=json.loads(encoded); requests.append(data)
        return (response(data) if corrected and len(requests)>1 else unsupported(data)).model_dump_json()
    def validator(bundle,cached=False):
        session=active_verification(); session.static(bundle)
        project=tmp_path/('candidate-'+str(len(requests))); project.mkdir()
        for file in bundle.files:
            path=project/file.path;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(file.content)
        session.compare(project,SimpleNamespace(),bundle,build_validation=dict(build_passed=True,tests_passed=True,
            test_count=1,issues=[],fixture='Synthetic build attestation; real JVM boundary comparison runs below'))
    def generate():
        return generate_reviewed_bundle(conn,config,profile,'unit','unit-configured_step','Convert',payload(),validator,
            lambda _:pytest.fail('No AI approval gate'),model_call=model)
    if corrected:
        _,_,review,_=generate()
        assert review.approved and snapshot(conn,'ladder','unit_verification','unit-configured_step')['status']=='accepted'
    else:
        with pytest.raises(VerificationFailure): generate()
        assert snapshot(conn,'ladder','unit_verification','unit-configured_step') is None
        assert not list(tmp_path.glob('candidate-*'))
    assert len(requests)==profile.max_agent_task_retries==2
    assert requests[1]['verification_feedback']['stage']=='binding'
    assert 'java.util.Map' in requests[1]['verification_feedback']['errors'][0]
    attempts=conn.execute("SELECT attempt,error FROM behavior_attempts WHERE category='unit' ORDER BY attempt").fetchall()
    assert len(attempts)==2 and attempts[0]['error']
    conn.close()
