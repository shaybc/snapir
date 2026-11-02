"""IBM names in data are allowed; actual Java dependencies and reflection remain blocked."""
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.side_road_policy import ForbiddenFrameworkDependency
from tools.validation_tools.ibm_dependency_guard_tool import scan_source,scan_for_ibm_dependencies
from tools.validation_tools.java_comments import mask_java_non_code


def bundle(body='',imports=''):
    return NativeUnitBundle(files=[dict(path='src/main/java/com/company/generated/Step.java',
        content='package com.company.generated;\n'+imports+'\npublic class Step {\n'+body+'\n}')])


def test_bundle_accepts_original_names_in_configuration_comments_and_text_blocks(tmp_path):
    value=bundle('''/** Original implClass="com.ibm.dse.Legacy". */
// com.ibm.dse.Legacy
/* com.ibm.dse.Legacy */
public static final String IMPL_CLASS = "com.ibm.dse.Legacy";
private String xml = """
<opStep implClass="com.ibm.dse.Legacy" />
""";
private String escaped = "\\\"/* com.ibm.dse.Legacy */\\\" // data";
private char delimiter = '/';
public String getImplClass() { return IMPL_CLASS; }''')
    validate_bundle(value)
    source=value.files[0].content
    path=tmp_path/'Step.java';path.write_text(source,encoding='utf-8')
    assert scan_source(source,['com.ibm'])==[]
    assert scan_for_ibm_dependencies(str(path),['com.ibm'])==[]
    masked=mask_java_non_code(source)
    assert len(masked)==len(source) and masked.count('\n')==source.count('\n')
    assert 'com.ibm' not in masked


@pytest.mark.parametrize('declaration',[
    'private com.ibm.dse.Legacy field;',
    'public com.ibm.dse.Legacy getValue() { return null; }',
    'public void setValue(com.ibm.dse.Legacy value) {}',
    'public void work() { com.ibm.dse.Legacy value = null; }',
    'private java.util.List<com.ibm.dse.Legacy> values;',
    'private com.ibm.dse.Legacy[] values;',
    'public void work() { new com.ibm.dse.Legacy(); }',
    'public void work() { com.ibm.dse.Legacy.execute(); }',
    'private Class<?> type = com.ibm.dse.Legacy.class;',
    'private Runnable run = com.ibm.dse.Legacy::execute;',
    '@com.ibm.dse.Legacy public void work() {}',
])
def test_actual_type_and_executable_references_still_fail(declaration):
    value=bundle(declaration)
    with pytest.raises(ForbiddenFrameworkDependency,match='line:pattern 4:com.ibm'):
        validate_bundle(value)


@pytest.mark.parametrize('imports',[
    'import com.ibm.dse.Legacy;',
    'import com.ibm.dse.*;',
    'import static com.ibm.dse.Legacy.execute;',
    'import static com.ibm.dse.Legacy.*;',
])
def test_ibm_import_variants_still_fail(imports):
    with pytest.raises(ForbiddenFrameworkDependency):validate_bundle(bundle(imports=imports))


@pytest.mark.parametrize('inheritance',['extends com.ibm.dse.Legacy','implements com.ibm.dse.Legacy'])
def test_inheritance_and_interface_dependencies_still_fail(inheritance):
    value=bundle();value.files[0].content=value.files[0].content.replace('class Step','class Step '+inheritance)
    with pytest.raises(ForbiddenFrameworkDependency):validate_bundle(value)


def test_declaration_in_ibm_package_still_fails():
    value=NativeUnitBundle(files=[dict(path='src/main/java/com/ibm/dse/Step.java',
        content='package com.ibm.dse; public class Step {}')])
    with pytest.raises(ValueError,match='legacy IBM packages must be replaced'):validate_bundle(value)


@pytest.mark.parametrize('body',[
    'public void load() throws Exception { Class.forName("com.ibm.dse.Legacy"); }',
    'private String name="com.ibm.dse.Legacy"; public void load() throws Exception { Class.forName(name); }',
    'private ClassLoader loader;',
    'public void load() { java.lang.reflect.Proxy.newProxyInstance(null,null,null); }',
])
def test_string_masking_cannot_bypass_production_reflection_guard(body):
    with pytest.raises(ValueError,match='Reflection is forbidden'):validate_bundle(bundle(body))


def test_literals_do_not_hide_real_code_on_the_same_line_or_change_diagnostics(tmp_path):
    source='String note="com.ibm.doc"; /* documentation */ com.ibm.dse.Legacy value;\n'
    path=tmp_path/'Step.java';path.write_text(source,encoding='utf-8')
    assert scan_for_ibm_dependencies(str(path),['com.ibm'])==[f'{path}:1:com.ibm']
    assert scan_source(source,['com.ibm'],include_locations=True)==['1:com.ibm']


def test_masking_preserves_crlf_and_escaped_text_block_delimiters():
    source='String value = """\r\ncom.ibm.data \\""" com.ibm.more\r\n""";\r\ncom.ibm.dse.Legacy field;'
    masked=mask_java_non_code(source)
    assert len(masked)==len(source) and masked.count('\r\n')==source.count('\r\n')
    assert scan_source(source,['com.ibm'],include_locations=True)==['4:com.ibm']
