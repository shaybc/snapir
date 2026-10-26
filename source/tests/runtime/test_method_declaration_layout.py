"""Check declaration identity across combinations of non-signature Java syntax."""

import pytest

from runtime.behavior_conversion.java_declaration_text import declaration_text
from runtime.behavior_conversion.method_contracts import has_method_contract


@pytest.mark.parametrize('remark', [
    '', '// Remark before annotation\n',
    '/* Comment with fake public int other() {} */\n',
    '/** Javadoc with @Override and braces { } */\n',
])
@pytest.mark.parametrize('annotations', [
    '', '@Override', '@java.lang.Override',
    '@SuppressWarnings({"unused", "a)b", "@Fake(public)"})\n@Override',
    '@Example(nested=@Inner(values={"(", ")", "}"}))\n@Override',
])
@pytest.mark.parametrize('gap', ['\n', '\r\n\r\n', ' /* Between annotation and method */ ', '\n// Between\n'])
def test_equals_and_hashcode_ignore_combined_declaration_layout(remark, annotations, gap):
    source = ('package demo; public final class Value {\n' + remark + annotations + gap +
        'public /* modifier comment */ boolean\n equals( /* parameter */ final Object renamed) { return this == renamed; }\n' +
        remark + annotations + gap + 'public int hashCode() { return 1; }\n}')
    assert has_method_contract(source, 'public boolean equals(java.lang.Object)')
    assert has_method_contract(source, 'public int hashCode()')
    assert not has_method_contract(source, 'public java.lang.Boolean equals(java.lang.Object)')
    assert not has_method_contract(source, 'public boolean equals(java.lang.String)')


def test_annotations_comments_and_spacing_in_contract_constructor_and_parameters():
    source = '''/* File header */ package demo /* package comment */ . api;
import java /* import comment */ . util . List;
@Deprecated public class Adapter {
 /** Constructor */ @Deprecated(since="1", forRemoval=false)
 public Adapter(/* constructor parameter */ @Example(value={"(", ")"}) final String value) {}
 @Example(nested=@Inner(values={"}", "("}))
 static /* order */ public final java . lang . String []
 convert(@Example(value="public") final List<String> values, String @Example [] suffixes)
 throws IllegalArgumentException { return suffixes; }
}'''
    assert has_method_contract(source, '@Deprecated public demo . api . Adapter(java.lang.String)')
    assert has_method_contract(source, '''/** Metadata comment */ @Example(nested=@Inner(value="("))
        public static java.lang.String[] convert(java.util.List, java.lang.String[]) throws Exception''')
    assert not has_method_contract(source, 'public java.lang.String[] convert(java.util.List, java.lang.String[])')
    assert not has_method_contract(source, 'public static java.lang.String convert(java.util.List, java.lang.String[])')


@pytest.mark.parametrize('visibility', ['private', 'protected', ''])
def test_annotations_cannot_make_nonpublic_class_method_public(visibility):
    source = ('package demo; public class Value {\n @Example(value="public boolean equals(Object)")\n' +
              visibility + ' boolean equals(Object value) { return false; } }')
    assert not has_method_contract(source, 'public boolean equals(java.lang.Object)')


def test_annotated_interface_methods_still_distinguish_private_members():
    source = '''package demo; @FunctionalInterface public interface Mapper {
 @Deprecated String map(@Example final String value);
 @Deprecated private boolean hidden(Object value) { return false; }
}'''
    assert has_method_contract(source, 'public java.lang.String map(java.lang.String)')
    assert not has_method_contract(source, 'public boolean hidden(java.lang.Object)')


def test_comments_literals_and_nested_methods_cannot_satisfy_contract():
    source = '''package demo; public class Value {
 // @Override public boolean equals(Object value) { return true; }
 /* public boolean equals(Object value) { return false; } */
 String text = "@Override public boolean equals(Object value) {}";
 char brace = '}';
 String block = """
 @Override public boolean equals(Object value) { return true; }
 """;
 public class Nested { @Override public boolean equals(Object value) { return true; } }
}'''
    assert not has_method_contract(source, 'public boolean equals(java.lang.Object)')


def test_package_and_imports_resolve_types_instead_of_being_discarded():
    source = '''package demo . api; import other . Result;
public class Mapper { @Deprecated public Result map(Result value) { return value; } }'''
    assert has_method_contract(source, 'public other.Result map(other.Result)', {'other.Result', 'demo.api.Result'})
    assert not has_method_contract(source, 'public demo.api.Result map(other.Result)', {'other.Result', 'demo.api.Result'})


def test_annotation_mask_preserves_offsets_lines_and_original_source():
    source = '/* before\n remark */\n@Example(nested=@Inner(value={"(", "}"}))\npublic int run() { return 0; }'
    masked = declaration_text(source)
    assert len(masked) == len(source)
    assert [i for i, value in enumerate(masked) if value == '\n'] == [i for i, value in enumerate(source) if value == '\n']
    assert masked.index('public int run') == source.index('public int run')
    assert '@Example' in source and '@Example' not in masked
    assert declaration_text('public @interface Marker {}') == 'public @interface Marker {}'


def test_unbalanced_annotation_fails_closed():
    with pytest.raises(ValueError, match='Unbalanced annotation'):
        has_method_contract('public class Value { @Example( public int run() { return 0; } }', 'public int run()')
