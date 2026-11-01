"""A paired model experiment cannot silently change instructions, evidence or baseline settings."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from tools.component_inventory_tools.identity import stable_id
from tools.behavior_verification.frozen_model_request import SETTINGS,verify_request


@pytest.mark.parametrize('changed',['instruction','evidence','settings'])
def test_frozen_fingerprint_rejects_changed_comparison_inputs(changed):
    values={name:None for name in SETTINGS};values.update(model_name='gemini/gemini-3.5-flash-lite',java_version=25)
    profile=SimpleNamespace(**values);prompt='Frozen instructions';request={'sources':[{'content':'original'}]}
    fingerprint=stable_id('staged_implementation',prompt,request,values,'behavior-v1')
    verify_request(profile,prompt,request,fingerprint)
    if changed=='instruction':prompt+=' extra rules'
    elif changed=='evidence':request=deepcopy(request);request['sources'][0]['content']='different'
    else:profile.model_name='different baseline'
    with pytest.raises(ValueError,match='fingerprint cannot be reproduced'):verify_request(profile,prompt,request,fingerprint)
