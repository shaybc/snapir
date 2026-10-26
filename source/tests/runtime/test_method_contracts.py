"""Verify semantic API matching and replay the failed live format response."""

import json
from pathlib import Path
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.method_contracts import has_method_contract


@pytest.mark.parametrize("signature", [
    "public static demo.Result parse(java.lang.String)",
    "public static Result parse(String request)",
])
def test_short_types_and_parameter_names_are_equivalent(signature):
    source = "package demo; public class Mapper { public static Result parse(String xml) throws Exception { return null; } }"
    assert has_method_contract(source, signature, {'demo.Result', 'demo.Mapper'})


def test_imports_generics_arrays_varargs_and_constructors():
    source = '''package demo;
import java.util.List;
import other.Result;
public class Mapper {
 public Mapper(final String name) {}
 public List<Result[]> map(final String... values) { return null; }
}'''
    assert has_method_contract(source, "public Mapper(java.lang.String)")
    assert has_method_contract(source, "public java.util.List<other.Result[]> map(java.lang.String[])")


@pytest.mark.parametrize('constructor', ['ValidationFailedStep', 'demo.ValidationFailedStep'])
@pytest.mark.parametrize('parameters', ['', 'java.lang.String, java.lang.String'])
def test_qualified_and_simple_constructor_contracts_match_source(constructor, parameters):
    source = '''package demo; public class ValidationFailedStep {
 public ValidationFailedStep() {}
 public ValidationFailedStep(final String category, String number) {}
 public int execute() { return 0; }
}'''
    assert has_method_contract(source, f'public {constructor}({parameters})')
    assert has_method_contract(source, 'public int execute()')


@pytest.mark.parametrize('signature', [
    'public other.ValidationFailedStep(java.lang.String, java.lang.String)',
    'public demo.OtherStep(java.lang.String, java.lang.String)',
    'public demo.ValidationFailedStep()',
    'public demo.ValidationFailedStep(java.lang.String)',
    'public demo.ValidationFailedStep(int, java.lang.String)',
    'public static demo.ValidationFailedStep(java.lang.String, java.lang.String)',
    'public void ValidationFailedStep(java.lang.String, java.lang.String)',
])
def test_constructor_normalization_rejects_wrong_owner_overload_and_method(signature):
    source = '''package demo; public class ValidationFailedStep {
 public ValidationFailedStep(String category, String number) {}
}'''
    assert not has_method_contract(source, signature)


@pytest.mark.parametrize('declaration', [
    'private ValidationFailedStep(String value) {}',
    'protected ValidationFailedStep(String value) {}',
    'ValidationFailedStep(String value) {}',
    'public void ValidationFailedStep(String value) {}',
    'public demo.ValidationFailedStep(String value) {}',
    'public class Nested { public Nested(String value) {} }',
    '// public ValidationFailedStep(String value) {}',
])
def test_qualified_constructor_requires_a_real_public_constructor(declaration):
    source = 'package demo; public class ValidationFailedStep {\n' + declaration + '\n}'
    assert not has_method_contract(source, 'public demo.ValidationFailedStep(java.lang.String)')


def test_live_validation_failed_constructor_shape_passes_bundle_validation():
    owner = 'com.company.generated.units.ua834d3c4f785.ValidationFailedStep'
    source = '''package com.company.generated.units.ua834d3c4f785;
public class ValidationFailedStep {
 private final String category;
 private final String number;
 public ValidationFailedStep() { this("10", "2"); }
 public ValidationFailedStep(String category, String number) {
  this.category = category; this.number = number;
 }
 public String execute() { return category + "_" + number; }
}'''
    bundle = NativeUnitBundle(files=[dict(path='src/main/java/' + owner.replace('.', '/') + '.java', content=source)],
        unit_contract=dict(unit_id='logged-constructor-regression', requirements={'constructor': 'Match declared constructors'},
            evidence_ids=['logged-source'], apis=[dict(type_name=owner, method_signatures=[
            'public ' + owner + '()', 'public ' + owner + '(java.lang.String, java.lang.String)',
            'public java.lang.String execute()'])]))
    assert validate_bundle(bundle, bundle.unit_contract.apis)
    bundle.files[0].content = source.replace('ValidationFailedStep(String category, String number)',
                                           'ValidationFailedStep(int category, String number)')
    with pytest.raises(ValueError, match='Native method contract is missing'):
        validate_bundle(bundle, bundle.unit_contract.apis)


@pytest.mark.parametrize("signature", [
    "public static other.Result parse(String)",
    "public static demo.Result parse(int)",
    "public static demo.Result parse(String, int)",
    "public demo.Result parse(String)",
    "public static demo.Result missing(String)",
])
def test_different_return_parameter_arity_static_or_name_is_rejected(signature):
    source = "package demo; public class Mapper { public static Result parse(String xml) { return null; } }"
    assert not has_method_contract(source, signature, {'demo.Result'})


def test_comments_nested_types_and_private_methods_cannot_satisfy_contract():
    source = '''package demo; public class Mapper {
 // public String parse(String xml) {}
 private String parse(String xml) { return xml; }
 public class Nested { public String parse(String xml) { return xml; } }
}'''
    assert not has_method_contract(source, "public String parse(String)")


def test_same_simple_name_from_other_package_is_not_equivalent():
    source = "package demo; import other.Result; public class Mapper { public Result parse(String xml) { return null; } }"
    assert has_method_contract(source, "public other.Result parse(java.lang.String)")
    assert not has_method_contract(source, "public demo.Result parse(java.lang.String)")


def test_declared_member_record_matches_binary_and_source_type_names():
    source = '''package demo; public class Mapper {
 public record ErrorReply(String message) {}
 public String format(ErrorReply value) { return value.message(); }
 public ErrorReply unformat(String xml) { return new ErrorReply(xml); }
}'''
    assert has_method_contract(source, 'public java.lang.String format(demo.Mapper$ErrorReply)')
    assert has_method_contract(source, 'public java.lang.String format(demo.Mapper.ErrorReply)')
    assert has_method_contract(source, 'public demo.Mapper$ErrorReply unformat(java.lang.String)')
    assert not has_method_contract(source, 'public String format(demo.Other$ErrorReply)')


def test_dollar_in_an_ordinary_type_name_is_not_a_member_separator():
    source = 'package demo; public class Mapper { public String format(Dollar$Reply value) { return null; } }'
    assert has_method_contract(source, 'public String format(demo.Dollar$Reply)')
    assert not has_method_contract(source, 'public String format(demo.Dollar.Reply)')


def test_method_local_record_cannot_change_public_parameter_resolution():
    source = '''package demo; public class Mapper {
 public String format(ErrorReply reply) { record ErrorReply(String value) {} return null; }
}'''
    assert not has_method_contract(source, 'public String format(demo.Mapper$ErrorReply)')


def test_interface_methods_and_wildcard_imported_generic_types():
    source = "package demo;\nimport java.util.*;\npublic interface Mapper {\n List<String> parse(String input);\n}"
    assert has_method_contract(source, "public java.util.List<java.lang.String> parse(java.lang.String)")


def test_replay_latest_failed_request_format_response():
    data = json.loads((Path(__file__).parent / "fixtures/transfer_request_method_contract.json").read_text(encoding="utf-8"))
    bundle = NativeUnitBundle.model_validate(data)
    assert validate_bundle(bundle, bundle.unit_contract.apis)
    mapper = next(item for item in bundle.files if item.path.endswith("Mapper.java"))
    mapper.content = mapper.content.replace("parseWire(String xmlContent)", "parseWire(int xmlContent)")
    with pytest.raises(ValueError, match="Native method contract is missing"):
        validate_bundle(bundle, bundle.unit_contract.apis)


@pytest.mark.parametrize("type_name, arguments", [
    ('java.util.Map', '<String, Object>'),
    ('java.util.HashMap', '<Integer, String>'),
    ('java.util.List', '<Map<String, List<? extends Number>>>'),
    ('demo.Box', '<List<? super Integer>>'),
])
def test_generic_arguments_are_erased_for_any_declared_type(type_name, arguments):
    name = type_name.rsplit('.', 1)[-1]
    source = f'package demo; import {type_name}; public class Step {{ public {name}{arguments} execute({name}{arguments} value) {{ return value; }} }}'
    assert has_method_contract(source, f'public {type_name} execute({type_name})')
    raw_source = f'package demo; import {type_name}; public class Step {{ public {name} execute({name} value) {{ return value; }} }}'
    assert has_method_contract(raw_source, f'public {type_name}{arguments} execute({type_name}{arguments})')


def test_generic_erasure_preserves_distinct_types_arrays_and_parameter_count():
    source = 'package demo; import java.util.HashMap; public class Step { public int execute(HashMap<String, Object>[] values) { return 0; } }'
    assert has_method_contract(source, 'public int execute(java.util.HashMap[])')
    assert not has_method_contract(source, 'public int execute(java.util.Map[])')
    assert not has_method_contract(source, 'public int execute(java.util.HashMap)')
    assert not has_method_contract(source, 'public int execute(java.util.HashMap[], int)')


def test_replay_latest_raw_map_contract_response():
    path = Path(__file__).parent / 'fixtures/latest_generic_method_rejection.json'
    bundle = NativeUnitBundle.model_validate_json(path.read_text(encoding='utf-8'))
    assert bundle.unit_contract.apis[0].method_signatures == ['public int execute(java.util.Map)']
    assert any('execute(Map<String, Object> context)' in file.content for file in bundle.files)
    assert validate_bundle(bundle, bundle.unit_contract.apis)
    method = next(file for file in bundle.files if file.path.startswith('src/main/java/'))
    method.content = method.content.replace('execute(Map<String, Object> context)', 'execute(java.util.HashMap<String, Object> context)')
    with pytest.raises(ValueError, match='Native method contract is missing'):
        validate_bundle(bundle, bundle.unit_contract.apis)
