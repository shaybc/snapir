"""Restricted native API recipes and AI proposals; no evaluated Java or business coercion."""
import json
from models.format_comparison_plan import FormatComparisonEntry
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.verification_binding import SCALARS, _member
from runtime.behavior_conversion.api_surface import api_surface
from runtime.managed_conversion_response import _remove_response_fence
from runtime.behavior_conversion.response_json import clean_structural_escapes
from agents.behavior_conversion.format_context_discovery import BINDING


def resolved_binding(entry, unit, native_sources):
    """Resolve configuration-selected keys and validate all recipes before reflection."""
    binding = entry.binding.model_copy(deep=True)
    names = {name for file in native_sources for name in public_api_types(file.content)}
    if any(name.startswith(('il.co.dcd.verification.', 'com.ibm.')) for name in names):
        raise ValueError('Native snapshots cannot replace harness/framework classes')
    if binding.owner_type not in names or not _member(binding.method_name):
        raise ValueError('Entry must select an actual supplied public native type and method')
    attributes = unit['effective_configuration'].get('attributes', {})

    def key(value):
        if value is not None and value.startswith('@configuration:'):
            value = attributes.get(value[len('@configuration:'):])
            if not isinstance(value, str):
                raise ValueError('Configuration-selected context key is unresolved')
        return value

    def recipe(value, depth=0):
        if depth > 12 or value.type_name not in names | SCALARS | {'java.util.List'}:
            raise ValueError('Unsupported recipe type or depth; adapter capability missing')
        if value.factory_method and (value.source != 'object' or not _member(value.factory_method)):
            raise ValueError('Object factory must be an exact public native method')
        if value.source == 'xml' and (value.type_name != 'java.lang.String' or value.key or value.arguments or value.properties or value.factory_method):
            raise ValueError('XML inputs must pass the original String unchanged')
        if value.source in {'context', 'configuration'}:
            value.key = key(value.key) if value.source == 'context' else value.key
            if value.key is None or value.arguments or value.properties or value.factory_method:
                raise ValueError('Input/configuration recipes read one exact key only')
        if value.source == 'object':
            if value.type_name not in names or value.key:
                raise ValueError('Object construction requires a supplied native type')
            for name, child in value.properties.items():
                if not _member(name):
                    raise ValueError('Invalid native setter')
                recipe(child, depth + 1)
            for child in value.arguments:
                recipe(child, depth + 1)
    for value in [*binding.constructor_arguments, *binding.arguments]:
        recipe(value)
    for setter, value in binding.configuration_setters.items():
        if not _member(setter) or value.source != 'configuration' or binding.static_method:
            raise ValueError('Configuration setters require an instance and configuration-only inputs')
        recipe(value)
    for projection in binding.context_writes:
        projection.context_key = key(projection.context_key)
        if projection.source == 'argument' and projection.argument_index >= len(binding.arguments):
            raise ValueError('Projection argument index is outside method arguments')
        if not all(_member(name) for name in [*projection.getters, *projection.presence_getters]):
            raise ValueError('Only exact public getter paths may project observations')
    if len({item.context_key for item in binding.context_writes}) != len(binding.context_writes):
        raise ValueError('Duplicate output projection key')
    if not all(_member(name) for name in binding.output_getters):
        raise ValueError('Invalid output accessor')
    if entry.direction == 'unformat' and binding.context_writes:
        binding.output = 'none'
        binding.output_getters = []
    return binding


def missing_binding_inputs(binding, case):
    """Missing values are diagnostic inputs only when explicitly marked intentionally absent."""
    missing = []
    def visit(value):
        if value.source == 'context' and value.key not in case.initial_context and value.key not in case.intentionally_absent:
            missing.append('Native input requires an unresolved context value: ' + value.key)
        for child in [*value.arguments, *value.properties.values()]:
            visit(child)
    for value in [*binding.arguments, *binding.constructor_arguments]:
        visit(value)
    return missing


def propose_bindings(unit, native_sources, model_call, settings, directory):
    """Offer an AI mapping-only fallback; unresolved wiring is never guessed or implemented."""
    payload = dict(original_configuration=unit['effective_configuration'],
                   original_sources=unit['sources'],
                   native_apis=api_surface(type('Files', (), {'files': native_sources})()),
                   entry_schema=FormatComparisonEntry.model_json_schema())
    encoded = json.dumps(payload, ensure_ascii=True)
    if len(BINDING) + len(encoded) > settings.discovery_request_chars:
        return {}, [f'Binding proposal exceeds the configured character budget: total_chars={len(BINDING) + len(encoded)}, limit_chars={settings.discovery_request_chars}']
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'request.json').write_text(encoded, encoding='utf-8')
    (directory / 'instruction.txt').write_text(BINDING, encoding='utf-8')
    try:
        response = model_call(BINDING, encoded)
        (directory / 'response.txt').write_text(response, encoding='utf-8')
        decoded = json.loads(clean_structural_escapes(_remove_response_fence(response)))
        entries = {name: FormatComparisonEntry.model_validate(value) for name, value in decoded['entries'].items()}
        for entry in entries.values():
            resolved_binding(entry, unit, native_sources)
        return entries, [str(value) for value in decoded.get('unresolved', [])]
    except (ValueError, KeyError, TypeError, RuntimeError, OSError, TimeoutError) as error:
        return {}, ['Binding proposal unavailable: ' + type(error).__name__]

