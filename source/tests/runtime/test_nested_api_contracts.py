"""Check nested API ownership without weakening missing-type or method validation."""

import pytest

from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.java_api_types import public_api_types

PACKAGE = 'com.company.generated.example'


def bundle(body):
    return NativeUnitBundle(files=[dict(path='src/main/java/' + PACKAGE.replace('.', '/') + '/Step.java',
        content='package ' + PACKAGE + '; public class Step { ' + body + ' }')])


def validate(value, name, signatures=()):
    from models.operation_data_contract import NativeApiContract
    return validate_bundle(value, [NativeApiContract(type_name=PACKAGE + '.' + name,
                                                   method_signatures=list(signatures))])


@pytest.mark.parametrize('name', ['Step.Result', 'Step$Result'])
def test_nested_type_and_qualified_constructor_match_their_own_methods(name):
    value = bundle('''public static class Result {
        public Result(String value) {}
        @Deprecated /* layout */ public String getValue() { return "value"; }
    } public Result execute() { return new Result("value"); }''')
    validate(value, name, ['public ' + PACKAGE + '.' + name + '(java.lang.String)',
                           'public java.lang.String getValue()'])
    validate(value, 'Step', ['public ' + PACKAGE + '.Step.Result execute()'])


@pytest.mark.parametrize('body', [
    'private static class Result { public String getValue() { return ""; } }',
    'protected static class Result { public String getValue() { return ""; } }',
    'static class Result { public String getValue() { return ""; } }',
    'public void work() { class Result { public String getValue() { return ""; } } }',
    '// public static class Result {}\n',
    'public String text = "public static class Result {}";',
    'public static class Other {}',
])
def test_missing_or_inaccessible_nested_type_is_rejected(body):
    with pytest.raises(ValueError, match='Planned native API is missing'):
        validate(bundle(body), 'Step$Result')


@pytest.mark.parametrize('declaration', [
    '', 'private String getValue() { return ""; }',
    'public int getValue() { return 1; }',
    'public String getValue(int value) { return ""; }',
    'public static String getValue() { return ""; }',
])
def test_parent_or_sibling_method_cannot_satisfy_nested_contract(declaration):
    value = bundle('public String getValue() { return ""; } '
        'public static class Other { public String getValue() { return ""; } } '
        'public static class Result { ' + declaration + ' }')
    with pytest.raises(ValueError, match='Native method contract is missing'):
        validate(value, 'Step.Result', ['public java.lang.String getValue()'])


def test_nested_method_cannot_satisfy_parent_contract():
    with pytest.raises(ValueError, match='Native method contract is missing'):
        validate(bundle('public static class Result { public String getValue() { return ""; } }'),
                 'Step', ['public java.lang.String getValue()'])


def test_multilevel_public_interface_members_and_visibility_chain():
    value = bundle('public interface Results { interface Result { String getValue(); } }')
    validate(value, 'Step$Results$Result', ['public java.lang.String getValue()'])
    value.files[0].content = value.files[0].content.replace('public interface Results', 'private interface Results')
    with pytest.raises(ValueError, match='Planned native API is missing'):
        validate(value, 'Step.Results.Result')


@pytest.mark.parametrize('kind', ['record Result(String value)', 'enum Result', '@interface Result'])
def test_nested_supported_type_kinds_are_identified(kind):
    assert PACKAGE + '.Step.Result' in public_api_types(bundle('public ' + kind + ' {}').files[0].content)


def test_wrong_enclosing_type_and_test_only_types_are_rejected():
    value = bundle('public static class Result {}')
    with pytest.raises(ValueError, match='Planned native API is missing'):
        validate(value, 'Other.Result')
    value.files[0].path = value.files[0].path.replace('/main/', '/test/')
    with pytest.raises(ValueError, match='Planned native API is missing'):
        validate(value, 'Step.Result')
