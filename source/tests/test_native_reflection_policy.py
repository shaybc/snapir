"""Generated production must use typed calls, including unused compatibility helpers."""
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.native_reflection_policy import reject_native_reflection


@pytest.mark.parametrize('code', [
    'import java.lang.reflect.Method;',
    'import java.lang.invoke.MethodHandles;',
    'Class.forName("SomeType");',
    'Class<?> target = String.class; target.getMethod("value");',
    'SomeType.class.getDeclaredConstructor().newInstance();',
    'target.getClass().getMethod("value");',
    'getClass().getDeclaredMethod("value");',
    'var target = String.class; target.getMethod("value");',
    'var target = obj.getClass(); target.getDeclaredFields();',
    'java.beans.Introspector.getBeanInfo(Type.class);',
    'ClassLoader loader;',
    'java.lang.reflect.Proxy.newProxyInstance(loader, types, handler);',
    'Class<?> target; var lookup = target::getDeclaredMethods;',
])
def test_rejects_production_reflection_even_outside_selected_method(code):
    with pytest.raises(ValueError, match='Reflection is forbidden'):
        reject_native_reflection('src/main/java/Work.java', code)


@pytest.mark.parametrize('code', [
    'result = dispatcher.invoke(input);',
    'String value = dto.getName(); Class<?> kind = dto.getClass();',
    '// java.lang.reflect.Method\nString note = "Class.forName";',
    'return switch (kind) { case "a" -> new First(); default -> new Second(); };',
])
def test_allows_ordinary_typed_code_and_non_code_text(code):
    reject_native_reflection('src/main/java/Work.java', code)


def test_test_harness_sources_are_not_production_sources():
    reject_native_reflection('src/test/java/WorkTest.java', 'import java.lang.reflect.Method;')


def test_bundle_validation_enforces_rule_before_build():
    bundle = NativeUnitBundle(files=[dict(path='src/main/java/com/company/generated/Work.java',
        content='package com.company.generated; import java.lang.reflect.Method; public class Work {}')])
    with pytest.raises(ValueError, match='Reflection is forbidden'):
        validate_bundle(bundle)


def test_all_implementation_prompt_paths_require_typed_replacement():
    from agents.behavior_conversion.native_instructions import COMMON_INSTRUCTION
    from agents.behavior_conversion.staged_instructions import IMPLEMENTATION
    from agents.behavior_conversion.side_road_instructions import BASELINE, SIMPLIFY
    for instruction in (COMMON_INSTRUCTION, IMPLEMENTATION, BASELINE, SIMPLIFY):
        assert 'must not use reflection' in instruction
        assert 'factory/dispatcher' in instruction
        assert 'unresolved' in instruction
