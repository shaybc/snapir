"""Automatic configuration roots and transitive Java discovery without supplied class lists."""
from pathlib import Path
import pytest
from runtime.configuration import load_configuration
from runtime.java_toolchain import java_scope
from runtime.composer_units.discovery import discover
from runtime.composer_units.selection import standalone
from models.composer_unit_specification import ComposerUnitSpecification
from test_scoped_vault_identity import scoped_mapper


def profile():
    return load_configuration(Path(__file__).resolve().parents[2]/'bank-demo/getclientlinks-facts-disabled-test.json')


def test_configured_children_and_decorators_are_automatic_roots():
    unit=standalone('com.ibm.il.dse.cc.format.CCXML',{'dataName':'Root'})
    unit['effective_configuration']['children']=[dict(java_class='com.ibm.il.dse.cc.format.CCString',attributes={'dataName':'Text'},
        decorators=[dict(java_class='com.ibm.il.dse.cc.decorator.CCPadding',attributes={'length':'4'})])]
    p=profile()
    with java_scope(p):resolved,report=discover(ComposerUnitSpecification(unit=unit),p)
    names={s['identity'] for s in resolved['sources']}
    assert {'com.ibm.il.dse.cc.format.CCString','com.ibm.il.dse.cc.decorator.CCPadding','com.ibm.il.dse.cc.format.AbstractFormatElement'}<=names
    assert not unit['sources'] and report['included']['com.ibm.il.dse.cc.format.CCString']


def test_fixture_preparation_receives_complete_original_dependency_evidence():
    from runtime.test_assets.original_evidence import complete_format_evidence
    unit=standalone('com.ibm.il.dse.cc.format.CCXML',{'dataName':'Root'})
    unit['effective_configuration']['children']=[dict(java_class='com.ibm.il.dse.cc.format.CCString',attributes={'dataName':'Text'},
        decorators=[dict(java_class='com.ibm.il.dse.cc.decorator.CCPadding',attributes={'length':'4'})])]
    payload=dict(unit=unit,sources=[])
    evidence=complete_format_evidence(payload,unit,profile(),'format')
    names={s['identity'] for s in evidence['sources']}
    assert {'com.ibm.il.dse.cc.format.CCString','com.ibm.il.dse.cc.decorator.CCPadding','com.ibm.il.dse.cc.format.AbstractFormatElement'}<=names
    assert evidence['comparison_dependency_discovery']['included']
    assert payload['sources']==[] and unit['sources']==[]


def test_missing_and_ambiguous_dependencies_and_limits_are_unavailable(tmp_path):
    p=profile()
    with java_scope(p):
        with pytest.raises(ValueError,match='no unique'):discover(ComposerUnitSpecification(unit=standalone('example.Missing')),p)
        with pytest.raises(ValueError,match='limit'):discover(ComposerUnitSpecification(unit=standalone('com.ibm.il.dse.cc.format.CCBoolean'),max_sources=1),p)
        for project in ['a','b']:
            path=tmp_path/project/'src/example/Sample.java';path.parent.mkdir(parents=True);path.write_text('package example;public class Sample {}')
        p.source_root=str(tmp_path)
        with pytest.raises(ValueError,match='Ambiguous'):
            discover(ComposerUnitSpecification(unit=standalone('example.Sample'),framework={'adapter_class':'il.co.dcd.verification.harness.LegacyBoundaryAdapter','context_class':'example.Sample','tag_class':'example.Sample'}),p)
    with pytest.raises(ValueError,match='Operation steps'):ComposerUnitSpecification(unit={'kind':'configured_step'})


def test_single_format_uses_qualified_mapper_closure_without_operation_steps(tmp_path,scoped_mapper):
    from test_scoped_closure import import_workspace
    from runtime.composer_units.selection import select_format,select_element
    conn,root,_=import_workspace(tmp_path,scoped_mapper)
    try:
        count=conn.total_changes
        selected=select_format(conn,'scoped','SME','Flow','Req',root)
        assert conn.total_changes==count
        assert selected['referenced_definitions'] and selected['configuration_revisions']
        text=str(selected['effective_configuration'])+str(selected['referenced_definitions'])
        assert 'example.Work' not in text and 'example.SecondDecorator' in text
        def decorators(node):
            yield from node.get('decorators',[])
            for child in node.get('children',[]):yield from decorators(child)
        decorator=next(decorators(selected['effective_configuration']))
        isolated=select_element(selected,decorator['occurrence_id'])
        assert isolated['effective_configuration']['java_class']==decorator['java_class']
    finally:conn.close()


def test_unrelated_project_classpath_and_original_recipe_validation(tmp_path):
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from models.boundary_case import BoundaryCase
    chosen=tmp_path/'chosen';(chosen/'src').mkdir(parents=True)
    (chosen/'.classpath').write_text('<classpath><classpathentry kind="src" path="src"/></classpath>')
    other=tmp_path/'other';other.mkdir();(other/'.classpath').write_text('<classpath><classpathentry kind="lib" path="missing.jar"/></classpath>')
    with java_scope(profile()):
        assert not discover_java_classpath(str(tmp_path),visible_source_roots=[str(chosen/'src')]).issues
        assert discover_java_classpath(str(tmp_path)).issues
    with pytest.raises(ValueError,match='exactly one input'):
        BoundaryCase(case_id='bad',original_inputs={'value':dict(type_name='java.lang.String',source='fixture',key='text',arguments=[dict(type_name='java.lang.String',source='fixture',key='other')])})
    with pytest.raises(ValueError,match='configuration tree'):ComposerUnitSpecification(unit={})
