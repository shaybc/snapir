"""Reuse semantic component identities without retaining another run's evidence identifiers."""
from models.pipeline_configuration import PipelineConfiguration
from models.native_component_bundle import NativeComponentBundle
from runtime.component_conversion.shared_identity import request_identity
from runtime.component_conversion.shared_bindings import request_bindings, replace_bindings, restore_bundle
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def request(identity, source):
    method = 'public int execute()'
    requirement = 'entry-' + digest([identity, method])
    return dict(group_id='group-' + identity, input_revision='run-local-' + identity,
        kind='step_implementation', native_package='com.company.generated.base', java_version=25,
        components={identity: dict(label='example.Base', provenance=dict(source_hash='original-hash'))},
        sources=[dict(component_id=identity, identity=source, content_hash='original-hash', content='original source')],
        source_entry_points={identity: [method]}, requirements={requirement: 'Exercise execute'},
        expected_contract_fields={identity: dict(component_id=identity,evidence_ids=[source])},
        parser_checklist=[dict(id='fact-' + source, source_identity=source, source_hash='original-hash',
                              source_file='C:/workspace/' + source + '.java', fact='return')])


def test_source_scope_relocation_keeps_the_semantic_lookup_identity():
    profile = PipelineConfiguration(source_workspace_id='bank')
    first = request('old-component', 'old-source')
    second = request('new-component', 'new-source')
    assert request_identity(first, profile) == request_identity(second, profile)
    second['sources'][0]['content_hash'] = 'changed-source'
    assert request_identity(first, profile) != request_identity(second, profile)


def test_rebound_citations_do_not_rewrite_generated_java():
    first = request('old-component', 'old-source')
    second = request('new-component', 'new-source')
    old_requirement = next(iter(first['requirements']))
    source = 'package com.company.generated.base; public class Base { public int execute(){return 0;} /* old-source */ }'
    bundle = NativeComponentBundle(contracts={'old-component': dict(component_id='old-component',
        apis=[dict(type_name='com.company.generated.base.Base', method_signatures=['public int execute()'])],
        source_entry_points=['public int execute()'], evidence_ids=['old-source'], configuration_mode='parameterized')},
        files=[dict(path='src/main/java/com/company/generated/base/Base.java', content=source)],
        coverage={old_requirement:['test.java']}, evidence_ids=['old-source'])
    rebound = restore_bundle(bundle, request_bindings(first), second)
    assert set(rebound.contracts) == {'new-component'}
    assert rebound.contracts['new-component'].evidence_ids == ['new-source']
    assert set(rebound.coverage) == set(second['requirements'])
    assert rebound.files[0].content == source


def test_requirement_version_changes_do_not_hit_the_previous_component():
    from models.conversion_requirement import ConversionRequirement
    profile = PipelineConfiguration(source_workspace_id='bank', conversion_requirements=[
        ConversionRequirement(requirement_id='business-rule', version=1, description='Preserve behavior')])
    first = request_identity(request('component', 'source'), profile)
    profile.conversion_requirements[0].version = 2
    assert request_identity(request('component', 'source'), profile) != first
