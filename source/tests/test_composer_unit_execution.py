"""Run original formats/decorators through automatic packaging and immutable cache reuse."""
import json,shutil
from pathlib import Path
import pytest
from runtime.java_toolchain import java_scope
from runtime.composer_units.selection import standalone
from runtime.composer_units.packaging import prepare
from runtime.composer_units.execution import execute
from runtime.composer_units.cache import verify
from models.composer_unit_specification import ComposerUnitSpecification
from test_composer_unit_discovery import profile


@pytest.fixture(scope='module')
def setup(tmp_path_factory):
    return profile(),tmp_path_factory.mktemp('composer-packages')


def run(setup,owner,action,scenario,attributes=None,kind='format',unit=None):
    p,root=setup;spec=ComposerUnitSpecification(kind=kind,action=action,unit=unit or standalone(owner,attributes))
    result=prepare(spec,p,root/'cache');assert result.status=='package_ready',result
    reused=prepare(spec,p,root/'cache');assert reused.package==result.package
    output=root/('case-'+str(len(list(root.glob('case-*')))))
    observation=execute(result.package,dict(case_id='test',**scenario),p,output)
    assert observation.status=='execution_completed',observation
    verify(result.package)
    return observation.observation,result.package


def test_boolean_both_directions_and_cache(setup):
    result,package=run(setup,'com.ibm.il.dse.cc.format.CCBoolean','format',{'initial_context':{'Flag':True}},{'dataName':'Flag'})
    assert result['output']=='<Flag>true</Flag>'
    result,_=run(setup,'com.ibm.il.dse.cc.format.CCBoolean','unformat',{'input_xml':'<Flag>true</Flag>'},{'dataName':'Flag'})
    assert result['context']['Flag'] is True
    p,root=setup;tampered=root/'tampered';shutil.copytree(package,tampered)
    (tampered/'unit.json').write_text('{}')
    with pytest.raises(ValueError,match='changed'):verify(tampered)
    p,root=setup;occupied=root/'occupied';occupied.mkdir();(occupied/'result.json').write_text('keep')
    assert execute(package,{'case_id':'new'},p,occupied).status=='execution_unavailable'
    assert (occupied/'result.json').read_text()=='keep'
    limited=p.model_copy(deep=True);limited.executable_verification.max_case_chars=1000
    assert execute(package,{'case_id':'huge','initial_context':{'Flag':True,'extra':'x'*5000}},limited,root/'too-large').status=='execution_unavailable'


def test_standalone_value_and_attribute_decorators(setup):
    owner='com.ibm.il.dse.cc.decorator.CCPadding'
    result,package=run(setup,owner,'decorate',{'decorator_value':'12'},{'length':'4'},kind='decorator')
    assert result['output']=='0012'
    p,root=setup
    assert execute(package,{'case_id':'wrong-type','decorator_value':12},p,root/'wrong-type').status=='execution_unavailable'
    result,_=run(setup,owner,'undecorate',{'decorator_value':'0012'},{'length':'4'},kind='decorator')
    assert result['output']=='12'
    result,_=run(setup,'com.ibm.il.dse.cc.decorator.NilDecorator','format_attributes',{'decorator_value':'','initial_context':{'CHANNEL_NAME':'internet','APPLICATION':'test'}},kind='decorator')
    assert isinstance(result['output'],dict)


def test_configured_children_execute_original_chain(setup):
    unit=standalone('com.ibm.il.dse.cc.format.CCXML',{'dataName':'Root'})
    unit['effective_configuration']['children']=[dict(java_class='com.ibm.il.dse.cc.format.CCString',attributes={'dataName':'Text'},
        decorators=[dict(java_class='com.ibm.il.dse.cc.decorator.CCPadding',attributes={'length':'4'})])]
    result,_=run(setup,None,'format',{'initial_context':{'Text':'12'}},unit=unit)
    assert result['output']=='<Root><Text>0012</Text></Root>'
    result,_=run(setup,None,'unformat',{'input_xml':'<Root><Text>0012</Text></Root>'},unit=unit)
    assert result['context']['Text']=='12'


def test_missing_method_does_not_become_a_success(setup):
    p,root=setup
    result=prepare(ComposerUnitSpecification(kind='decorator',action='undecorate',unit=standalone('com.ibm.il.dse.cc.decorator.NilDecorator')),p,root/'cache')
    assert result.status=='preparation_unavailable' and result.issues


def test_original_dto_construction_observation_and_byte_freshness(tmp_path):
    from models.native_boundary_value import NativeBoundaryValue
    p=profile();workspace=tmp_path/'workspace';project=workspace/'WSBCC_XML'
    shutil.copytree(Path(p.source_root)/'WSBCC_XML',project);p.source_root=str(workspace)
    folder=project/'src/example';folder.mkdir()
    row=folder/'Row.java';row.write_bytes(b'package example;public class Row {private String name;public Row(String name){this.name=name;}public String getName(){return name;}}\r\n')
    formatter=folder/'Format.java';formatter.write_bytes(('\ufeffpackage example;import com.ibm.dse.base.*;public class Format {public void initializeFrom(Tag t){}public String format(Context c){return "<v>"+((Row)c.getValueAt("Input")).getName()+"</v>";}public void unformat(String xml,Context c){c.setValueAt("Output",new Row(xml.substring(3,xml.length()-4)));}}\r\n').encode())
    spec=ComposerUnitSpecification(unit=standalone('example.Format'),framework={'adapter_class':'il.co.dcd.verification.harness.LegacyBoundaryAdapter','original_context_getters':{'Input':['getName']}})
    package=prepare(spec,p,tmp_path/'cache');assert package.status=='package_ready',package
    recipe=NativeBoundaryValue(type_name='example.Row',source='object',arguments=[dict(type_name='java.lang.String',source='fixture',key='name')])
    result=execute(package.package,{'case_id':'format','original_inputs':{'Input':recipe.model_dump(mode='json')},'test_assets':{'inputs':{'name':'value'}}},p,tmp_path/'formatted')
    assert result.status=='execution_completed' and result.observation['output']=='<v>value</v>',result
    assert result.observation['context']['Input']=='value'
    spec.action='unformat';spec.framework.original_context_getters={'Output':['getName']}
    parsed=prepare(spec,p,tmp_path/'cache');assert parsed.status=='package_ready',parsed
    result=execute(parsed.package,{'case_id':'unformat','input_xml':'<v>parsed</v>'},p,tmp_path/'parsed')
    assert result.status=='execution_completed' and result.observation['context']['Output']=='parsed',result
    assert any(path.read_bytes().startswith(b'\xef\xbb\xbf') for path in (Path(parsed.package)/'sources').rglob('Format.java'))
    row.write_bytes(row.read_bytes()+b'// changed\r\n')
    with pytest.raises(ValueError,match='Original Composer input changed'):verify(parsed.package)


def test_table_format_uses_explicit_database_fixture(setup):
    attributes={'dataName':'Description','fromTable':'T','fromColumn':'V','keyValue':'Key'}
    scenario={'initial_context':{'Key':'k'},'test_assets':{'resources':{'db':{'queries':[{'sql':'SELECT V FROM T WHERE KEY = ?','parameters':['k'],'columns':['V'],'rows':[['found']]}]}},'composer_resource_setters':{'setConnection':'db'}}}
    result,package=run(setup,'com.ibm.il.dse.cc.format.CCTableFormat','format',scenario,attributes)
    assert result['output']=='<Description>found</Description>' and result['resource_events'][0]['operation']=='query'
    p,root=setup;scenario['test_assets']['resources']['db']['queries'][0]['parameters']=['missing']
    result=execute(package,dict(case_id='missing',**scenario),p,root/'missing-query')
    assert result.status=='execution_unavailable' and any('No fixture query' in issue for issue in result.issues)
    parsed,_=run(setup,'com.ibm.il.dse.cc.format.CCTableFormat','unformat',{'input_xml':'<Description>found</Description>'},attributes)
    assert parsed['context']['Description']=='found'


def test_initialization_failure_is_not_a_business_comparison_result(setup):
    p,root=setup
    package=prepare(ComposerUnitSpecification(kind='decorator',action='decorate',unit=standalone('com.ibm.il.dse.cc.decorator.CCPadding',{'length':'bad'})),p,root/'cache')
    assert package.status=='package_ready',package
    result=execute(package.package,{'case_id':'bad-tag','decorator_value':'12'},p,root/'bad-tag')
    assert result.status=='execution_unavailable' and any('initialization failed' in issue for issue in result.issues)
    assert result.observation['invocation_completed'] is False


def test_transparent_xml_fragments_keep_text_and_structure_checks():
    from models.boundary_observation import BoundaryObservation
    from runtime.format_comparison.reporting import compare_case
    left=BoundaryObservation(case_id='fragment',status='completed',output='<a> value </a><b/>')
    right=left.model_copy(update={'output':'<a> value </a><b></b>'})
    settings=profile().format_comparison
    assert compare_case(left,right,'format',settings)['status']=='matched'
    right.output='<a>value</a><b/>'
    assert compare_case(left,right,'format',settings)['status']=='different'


def test_comparison_prepares_each_configuration_variant(tmp_path):
    from models.format_comparison_plan import FormatComparisonPlan
    from models.native_unit_bundle import NativeSourceFile
    from runtime.composer_units.comparison import prepare_comparison
    from runtime.format_comparison.runner import run_comparison
    repo=Path(__file__).resolve().parents[2]
    saved=repo/'outputs/getclientlinks-dependency-alignment-20261103/single-get-client-links/generated/components/7eac14be1092f608-3a8da1719fca/src/main/java/com/company/generated/components/c622aebaba4903b67/CCBoolean.java'
    owner='com.company.generated.components.c622aebaba4903b67.CCBoolean'
    binding=dict(owner_type=owner,method_name='format',constructor_arguments=[dict(type_name='java.lang.String',source='configuration',key='dataName')],
        arguments=[dict(type_name='java.lang.Boolean',source='context',key='Flag')],configuration_setters={
            'setTrueValue':dict(type_name='java.lang.String',source='configuration',key='trueValue')})
    plan=FormatComparisonPlan(label='variant',scope='configured',original_unit=standalone('com.ibm.il.dse.cc.format.CCBoolean',{'dataName':'Flag','trueValue':'true'}),
        native_sources=[NativeSourceFile(path='src/main/java/'+owner.replace('.','/')+'.java',content=saved.read_bytes().decode())],
        entries={'format':dict(direction='format',binding=binding)},cases=[dict(case_id='variant',binding_id='format',initial_context={'Flag':True},configuration_attributes={'dataName':'Flag','trueValue':'YES'})])
    p=profile();prepared=prepare_comparison(plan,p,tmp_path/'packages')
    report=run_comparison(prepared,p,tmp_path/'comparison')
    assert report['counts']['matched']==1,report
    assert report['cases'][0]['legacy']['output']=='<Flag>YES</Flag>'
