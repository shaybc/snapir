"""Adapter configuration recovery preserves trusted partition evidence and frozen payloads."""
from copy import deepcopy
import pytest
from runtime.behavior_conversion.adapter_configuration import resolve_configuration
from runtime.component_conversion.scope import partition_task
from runtime.component_conversion.partition_requests import partition_request
from test_component_partitions import original_request


@pytest.mark.parametrize('kind',['request_unformat','response_format'])
@pytest.mark.parametrize('selector',[[],[0],[0,2]])
def test_resolves_original_configuration_without_mutating_projection(kind,selector):
    original=original_request();original['configured_format']['kind']=kind
    tree=original['configured_format']['effective_configuration']
    request=partition_request(original,tree,selector,{})
    before=deepcopy(request)
    with partition_task(request['group_id'],request,original):
        unit,context=resolve_configuration(request)
    expected=tree
    for index in selector:expected=expected['children'][index]
    assert unit['effective_configuration']==expected
    assert context==request['format_partition']
    assert ('configuration_xml' in unit)==(not selector)
    unit['effective_configuration']['tag']='changed'
    assert request==before and original['configured_format']['effective_configuration']==tree


def test_partition_requires_trusted_context_and_rejects_tampering():
    original=original_request();tree=original['configured_format']['effective_configuration']
    request=partition_request(original,tree,[],{})
    with pytest.raises(ValueError,match='active trusted'):resolve_configuration(request)
    with partition_task(request['group_id'],request,original):
        changed=deepcopy(request);changed['format_partition']['configuration_hash']='wrong'
        with pytest.raises(ValueError,match='active trusted'):resolve_configuration(changed)
    request['format_partition']['configuration_hash']='wrong'
    with partition_task(request['group_id'],request,original):
        with pytest.raises(ValueError,match='identity or hash'):resolve_configuration(request)


def test_ordinary_configuration_is_detached_and_missing_evidence_rejected():
    request=original_request();unit,context=resolve_configuration(request)
    assert unit==request['configured_format'] and unit is not request['configured_format'] and context is None
    with pytest.raises(ValueError,match='XML evidence'):resolve_configuration({'kind':'response_format'})


def test_frozen_child_projection_does_not_replace_original_xml():
    original=original_request();tree=original['configured_format']['effective_configuration']
    children={(0,):dict(group_id='child',contract_revision='contract',result_revision='result')}
    request=partition_request(original,tree,[],children)
    with partition_task(request['group_id'],request,original):
        unit,context=resolve_configuration(request)
    assert unit['effective_configuration']==tree
    assert context['tree']['children'][0]['native_subtree']['result_revision']=='result'
