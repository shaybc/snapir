"""CF6 partitions configured trees, never Java text, and retains whole-format verification."""
import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from tools.conversion_tools.component_partition import (subtree_at, partition_tree, parent_configuration,
    partition_identity, splittable_children)
from runtime.component_conversion.partition_requests import partition_request, fits_partition
from runtime.component_conversion.partition_runner import convert_partitioned_format
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from test_component_formats import format_case, boundary_tool, request_for, fixture_tree, candidate, XML


def original_request():
    tree = dict(tag='fmtDef', attributes={'id':'Reply'}, children=[dict(tag='CCXML',
        attributes={'dataName':'Reply', 'namespace':'urn:bank'}, decorators=[{'java_class':'example.Decorator'}],
        children=[dict(tag='Field', occurrence_id=str(index), attributes={'dataName':'same','value':str(index)*1000})
                  for index in range(8)])])
    return dict(group_id='group-format', kind='format_composition', native_package='com.company.generated.format',
        configured_format=dict(unit_id='reply', kind='response_format', configuration_xml='<complete/>',
            effective_configuration=tree, referenced_definitions=[]),
        components={'root':dict(configuration={'configuration_xml':'<complete/>'})}, sources=[dict(identity='source',content='FULL JAVA SOURCE')],
        source_entry_points={'root':['format(Context)']}, parser_checklist=[dict(id='branch-1')],
        prerequisite_components=[dict(group_id='native', sources={'Java.java':'FULL NATIVE SOURCE'},contracts={'native':{'apis':[]}})],
        requirements={'preserve':'Preserve behavior'}, known_dependencies=[], configuration_evidence_ids=['definition'])


def test_occurrence_paths_preserve_order_repeats_ancestors_and_original_bytes():
    request=original_request();tree=request['configured_format']['effective_configuration'];before=deepcopy(tree)
    children={(0,1):dict(group_id='converted-second',contract_revision='frozen')}
    result=partition_tree(tree,(0,),children)
    assert tree==before
    assert result['children'][0]==tree['children'][0]['children'][0]
    assert result['children'][1]['original_selector']==[0,1]
    assert result['children'][1]['configuration_hash']==digest(tree['children'][0]['children'][1])
    assert result['children'][2]==tree['children'][0]['children'][2]
    assert parent_configuration(tree,(0,2))[1]['configuration']['decorators']==tree['children'][0]['decorators']
    assert subtree_at(tree,(0,2))['occurrence_id']=='2'
    assert partition_identity('group',tree,(0,1))!=partition_identity('group',tree,(0,2))
    assert splittable_children({'reference_definition_id':'shared','children':[{}]},())==[]


def test_partition_projection_keeps_source_checklist_and_reference_evidence():
    original=original_request();original['configured_format']['referenced_definitions']=[{'definition_id':'shared','children':[]}]
    tree=original['configured_format']['effective_configuration']
    request=partition_request(original,tree,(0,2),{})
    assert request['sources']==original['sources'] and request['parser_checklist']==original['parser_checklist']
    assert request['format_partition']['referenced_definitions']==original['configured_format']['referenced_definitions']
    assert request['format_partition']['tree']==subtree_at(tree,(0,2))
    assert 'sources' not in request['prerequisite_components'][0]
    assert original['prerequisite_components'][0]['sources']
    assert 'configured_format' not in request
    root=partition_request(original,tree,(),{})
    assert root['configured_format']['unit_id']=='reply'
    assert 'effective_configuration' not in root['configured_format']


def test_format_root_exports_extracted_sources_without_claiming_shared_prerequisites(tmp_path):
    from runtime.component_conversion.validation import owned_component_sources
    root={'src/main/java/Root.java':'root','src/test/java/RootTest.java':'test'}
    dependencies={'src/main/java/Part.java':'part','src/main/java/Shared.java':'shared'}
    assert owned_component_sources(root,dependencies,['src/main/java/Part.java'])==[
        'src/main/java/Part.java','src/main/java/Root.java']
    assert owned_component_sources(root,dependencies)==['src/main/java/Root.java']
    with pytest.raises(ValueError,match='ownership'):
        owned_component_sources(root,dependencies,['src/main/java/Missing.java'])
    with pytest.raises(ValueError,match='ownership'):
        owned_component_sources(root,dependencies,['src/test/java/RootTest.java'])
    from runtime.component_conversion.requests import prerequisite_sources
    owned=owned_component_sources(root,dependencies,['src/main/java/Part.java'])
    for name,content in {**root,**dependencies}.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
    (tmp_path/'report.json').write_text(json.dumps(dict(owned_sources=owned,dependencies=[])))
    exported,_=prerequisite_sources({'root':SimpleNamespace(artifact_root=str(tmp_path),validation_report='report.json',files={**root,**dependencies})})
    assert exported=={'src/main/java/Root.java':'root','src/main/java/Part.java':'part'}


def test_real_budget_includes_schema_manual_checklist_and_source():
    from runtime.behavior_conversion.request_context import encode_request
    from models.native_format_subtree_bundle import NativeFormatSubtreeBundle
    from runtime.behavior_conversion.response_json import JSON_INSTRUCTION
    original=original_request();tree=original['configured_format']['effective_configuration']
    part=partition_request(original,tree,(0,1),{})
    _,encoded=encode_request(dict(part,schema=NativeFormatSubtreeBundle.model_json_schema(),versioned_requirements=[
        dict(requirement_id='preserve',version=1,description='Preserve behavior')]),'instruction\n'+JSON_INSTRUCTION,10**7)
    limit=len(encoded)+len('instruction\n'+JSON_INSTRUCTION)
    profile=SimpleNamespace(behavior_context_chars=limit,conversion_requirements=[])
    assert fits_partition(part,'instruction',profile)
    assert not fits_partition(part,'instruction',SimpleNamespace(behavior_context_chars=limit-1,conversion_requirements=[]))
    assert not fits_partition(partition_request(original,tree,(0,),{}),'instruction',profile)


def scheduling_fixture(monkeypatch, calls, *, fail_root=False):
    """Scheduling-only doubles; real builds/comparison are tested separately."""
    import runtime.component_conversion.partition_runner as runner
    monkeypatch.setattr(runner,'fits_partition',lambda request,*a: request['format_partition']['selector']!=[] or
        bool(request['format_partition']['tree'].get('children',[{}])[0].get('native_subtree')))
    class Part:
        def __init__(self,*args):
            self.request=args[3];self.generated_files={'src/main/java/Part'+digest(self.request['group_id'])[:12]+'.java':'fixture'}
            self.descriptor=dict(group_id=self.request['group_id'],contract_revision='contract',result_revision='result',dependencies=[])
    monkeypatch.setattr(runner,'SubtreeCandidateValidator',Part)
    ownership=[]
    def root_validator(*args,**kwargs):
        ownership.append(kwargs['owned_dependency_sources'])
        return object()
    monkeypatch.setattr('runtime.component_conversion.validation.ComponentCandidateValidator',root_validator)
    def generate(*args,**kwargs):
        calls.append(args[6])
        if fail_root and not args[6]['format_partition']['selector']:
            raise ValueError('Whole-format comparison failed')
    monkeypatch.setattr(runner,'generate',generate)
    return ownership


def test_bottom_up_schedule_parent_receives_frozen_child_and_failure_is_not_accepted(tmp_path,monkeypatch):
    calls=[];scheduling_fixture(monkeypatch,calls,fail_root=True)
    request=original_request();group=SimpleNamespace(group_id=request['group_id'],members=['root'])
    profile=SimpleNamespace(java_version=25)
    with pytest.raises(ValueError,match='Whole-format comparison'):
        convert_partitioned_format(None,None,profile,None,group,request,'instruction',tmp_path,None,None,{},[],units={},boundaries={})
    assert [item['format_partition']['selector'] for item in calls]==[[0],[]]
    assert calls[-1]['format_partition']['tree']['children'][0]['native_subtree']['contract_revision']=='contract'
    report=json.loads(next(tmp_path.rglob('partition-report.json')).read_text())
    assert report['status']=='incomplete' and report['accepted_units']==report['accepted_operations']==0


def test_low_measured_budget_forces_multiple_parts_without_losing_configuration(tmp_path,monkeypatch):
    import runtime.component_conversion.partition_runner as runner
    calls=[];ownership=scheduling_fixture(monkeypatch,calls)
    monkeypatch.setattr(runner,'fits_partition',fits_partition)
    request=original_request();tree=request['configured_format']['effective_configuration']
    for child in tree['children'][0]['children']:
        child['attributes']['value']=child['occurrence_id']*12000
    group=SimpleNamespace(group_id=request['group_id'],members=['root'])
    profile=SimpleNamespace(java_version=25,behavior_context_chars=50000,conversion_requirements=[])
    assert not fits_partition(request,'instruction',profile)
    result=convert_partitioned_format(None,None,profile,None,group,request,'instruction',tmp_path,None,None,{},[],units={},boundaries={})
    assert result['subtree_components']==9
    assert len(ownership)==1 and len(ownership[0])==9
    assert [item['format_partition']['selector'] for item in calls]==[[0,index] for index in range(8)]+[[0],[]]
    assert all(item['parser_checklist']==request['parser_checklist'] and item['sources']==request['sources'] for item in calls)
    assert [item['format_partition']['tree']['attributes']['value'] for item in calls[:8]]==[
        child['attributes']['value'] for child in tree['children'][0]['children']]
    report=json.loads(next(tmp_path.rglob('partition-report.json')).read_text())
    assert report['status']=='whole_format_compared' and report['accepted_units']==report['accepted_operations']==0


def test_indivisible_overflow_stops_without_model_or_truncation(tmp_path,monkeypatch):
    import runtime.component_conversion.partition_runner as runner
    monkeypatch.setattr(runner,'fits_partition',lambda *a:False)
    monkeypatch.setattr(runner,'generate',lambda *a,**k:pytest.fail('Oversized leaf must never reach model'))
    request=original_request();group=SimpleNamespace(group_id=request['group_id'],members=['root'])
    with pytest.raises(ValueError,match='Indivisible oversized format subtree'):
        convert_partitioned_format(None,None,SimpleNamespace(java_version=25),None,group,request,'instruction',tmp_path,None,None,{},[],units={},boundaries={})
    report=json.loads(next(tmp_path.rglob('partition-report.json')).read_text())
    assert report['status']=='incomplete' and request['sources'][0]['content']=='FULL JAVA SOURCE'


def test_subtree_scope_rechecks_exact_projection_and_original_source(format_case):
    from runtime.component_conversion.scope import component_execution,partition_task,require_component_task
    conn,config,profile,preparation,_,_,_=format_case
    _,original,_=request_for(format_case)
    part=partition_request(original,original['configured_format']['effective_configuration'],(0,),{})
    with component_execution(conn,config,profile,None,preparation,include_formats=True):
        with pytest.raises(ValueError,match='unresolved prerequisites'):
            require_component_task(conn,config,profile,part['group_id'],part)
        with partition_task(part['group_id'],part,original):
            require_component_task(conn,config,profile,part['group_id'],part)
            changed=deepcopy(part);changed['format_partition']['parents'][0]['configuration']['tag']='Wrong'
            with pytest.raises(ValueError,match='trusted subtree'):
                require_component_task(conn,config,profile,part['group_id'],changed)
            changed=deepcopy(part);changed['parser_checklist']=[]
            with pytest.raises(ValueError,match='trusted subtree'):
                require_component_task(conn,config,profile,part['group_id'],changed)


def test_real_maven_subtree_reuse_and_assembled_original_native_comparison(format_case,tmp_path):
    from tests.runtime.test_scoped_native import actual_build
    from runtime.component_conversion.scope import component_execution,partition_task
    from runtime.component_conversion.partition_validation import SubtreeCandidateValidator
    from models.native_component_bundle import NativeComponentBundle
    from models.native_format_component_bundle import NativeFormatComponentBundle
    from runtime.component_conversion.format_verification import format_bundle,session_for
    from models.boundary_harness_binding import BoundaryHarnessBinding
    from tools.behavior_verification.boundary_verification import verify_boundary
    from tools.behavior_verification.controlled_inputs import generate_boundary_cases
    conn,config,profile,preparation,_,boundaries,units=format_case
    _,original,_=request_for(format_case);original,files=fixture_tree(original)
    tree=original['configured_format']['effective_configuration'];part=partition_request(original,tree,(0,),{})
    data=candidate(part);key=next(iter(data['contracts']))
    # The supplied prerequisite is FormatLogic, whose actual public method is format().
    for file in data['files']:
        file['content']=file['content'].replace('().xml()', '().format()')
    for locations in data['checklist_implementations'].values():
        for location in locations:
            location['excerpt']=location['excerpt'].replace('().xml()', '().format()')
    data['contracts'][key].update(configuration_mode='specialized',runtime_inputs={'parent_environment':'No parent state is read by this source-backed fixture'})
    native=NativeComponentBundle.model_validate(data)
    pins=[item for item in original['known_dependencies'] if item['artifact_id']=='junit-jupiter']
    validator=SubtreeCandidateValidator(conn,config,profile,part,tmp_path/'parts',actual_build,files,pins)
    from runtime.behavior_conversion.generation import generate
    from runtime.component_conversion.partition_requests import PART_INSTRUCTION
    model_calls=[]
    def model(instruction,encoded):
        model_calls.append(json.loads(encoded))
        return native.model_dump_json()
    with component_execution(conn,config,profile,None,preparation,include_formats=True),partition_task(part['group_id'],part,original):
        invalid=native.model_copy(deep=True);invalid.contracts[key].runtime_inputs={}
        with pytest.raises(ValueError,match='parent-environment'):
            validator(invalid)
        invalid=native.model_copy(deep=True);invalid.checklist_implementations={}
        with pytest.raises(ValueError,match='missing_item'):
            validator(invalid)
        generate(conn,config,profile,'component_generation',part['group_id'],PART_INSTRUCTION,part,NativeComponentBundle,
            validator=validator,model_call=model)
        first=validator.descriptor.copy()
        generate(conn,config,profile,'component_generation',part['group_id'],PART_INSTRUCTION,part,NativeComponentBundle,
            validator=validator,model_call=lambda *a:pytest.fail('Unchanged subtree must reuse durable generation'))
        assert validator.descriptor==first
        assert len(model_calls)==1
    all_files={**files,**validator.generated_files}
    parent=deepcopy(original);parent['prerequisite_components']=[dict(contracts=native.model_dump(mode='json')['contracts'],sources=all_files)]
    composed=NativeFormatComponentBundle.model_validate(candidate(parent,dependencies=all_files))
    bundle=format_bundle(composed,original,all_files)
    session=session_for(config,profile,units['response'],boundaries['boundaries']['response']);session.static(bundle)
    binding=BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',native_entry=composed.verification_binding,
        sources=[dict(path=file.path,content=file.content) for file in bundle.files if file.path.startswith('src/main/java/')])
    report=verify_boundary(units['response'],session.boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        binding,generate_boundary_cases(units['response'],session.boundary),tmp_path/'comparison',tool=session.tool,candidate_label='deterministic_subtree_fixture')
    assert report.status=='matched_observed_cases',report.model_dump_json(indent=2)
    assert all(case['native']['output']==XML for case in report.cases)
    part_type=next(iter(native.contracts.values())).apis[0].type_name
    assert any(probe['id']=='native:'+part_type+'.format()' for case in report.cases for probe in case['native']['probes'])
    # A wire-prefix defect inside a successfully built part still fails whole-format comparison.
    mutated=binding.model_copy(deep=True)
    for source in mutated.sources:
        if source.path in validator.generated_files:
            target='new com.company.generated.fixture.FormatLogic().format()'
            source.content=source.content.replace(target,json.dumps(XML.replace('xsi:', 'bad:').replace('xmlns:xsi', 'xmlns:bad')))
    failed=verify_boundary(units['response'],session.boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        mutated,generate_boundary_cases(units['response'],session.boundary),tmp_path/'mutation',tool=session.tool,candidate_label='deliberate_subtree_prefix_mutation')
    assert failed.status=='differences_found' and any(case['differences'] for case in failed.cases)
    receipt=next((tmp_path/'parts').glob('*.json'))
    saved=json.loads(receipt.read_text());artifact=tmp_path/'parts'/saved['artifact']
    path=artifact/next(iter(validator.generated_files));path.write_text(path.read_text()+'// tamper',encoding='utf-8')
    with component_execution(conn,config,profile,None,preparation,include_formats=True),partition_task(part['group_id'],part,original),pytest.raises(ValueError,match='changed or disappeared'):
        validator(native,cached=True)
